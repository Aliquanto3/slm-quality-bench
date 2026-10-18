"""Sous-commande ``status --campaign <c>`` : avancement d'une campagne de génération.

Lecture seule (voir ``monitor/status.py``). Codes de sortie : 0 ; 2 (identifiant invalide,
configuration de campagne ou jeu introuvable ou illisible, option invalide). Ctrl+C pendant
``--watch`` sort proprement (code 0).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from ..common import paths
from ..common.canonical import pretty_bytes
from ..common.logs import setup_logging
from .notify import Notifier, ToastNotifier, Transitions, dispatch
from .status import (
    DEFAULT_BASELINE,
    DEFAULT_STALL_MINUTES,
    RowCache,
    StatusError,
    compute_status,
    expected_lines,
    local_now,
    render_text,
)

logger = logging.getLogger(__name__)

COMMAND = "status"

# Points d'injection des tests : lus à l'appel.
SLEEP: Callable[[float], None] = time.sleep
NOW: Callable[[], datetime] = local_now


def make_notifier() -> Notifier:
    return ToastNotifier()


def _clear_screen() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")


def _use_color() -> bool:
    """Couleurs ANSI dans un terminal seulement, sauf ``NO_COLOR`` (no-color.org). Sous Windows,
    active le traitement des séquences VT de la console (Windows Terminal l'a déjà)."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT_PROCESSING
        except AttributeError, OSError:
            return False
    return True


def run_status(
    campaign: str,
    *,
    baseline: str = DEFAULT_BASELINE,
    stall_minutes: float = DEFAULT_STALL_MINUTES,
    as_json: bool = False,
    watch: float | None = None,
    notify: bool = False,
) -> int:
    plan = expected_lines(campaign)  # StatusError si campagne ou jeu introuvable
    cache = RowCache(paths.generation_path(campaign))
    baseline_path = Path(baseline)
    if not baseline_path.is_absolute():
        baseline_path = paths.data_root() / baseline_path
    transitions = Transitions() if notify and watch else None
    color = not as_json and _use_color()
    notifier = make_notifier() if transitions else None

    def once() -> None:
        status = compute_status(
            campaign,
            cache=cache,
            baseline_path=baseline_path,
            stall_minutes=stall_minutes,
            now=NOW(),
            plan=plan,
        )
        if as_json:
            print(pretty_bytes(status).decode("utf-8"), end="")
        else:
            if watch:
                _clear_screen()
            print(render_text(status, color=color))
        sys.stdout.flush()
        if transitions is not None and notifier is not None:
            dispatch(notifier, transitions.events(status))

    if not watch:
        once()
        return 0
    try:
        while True:
            try:
                once()
            except Exception as exc:  # noqa: BLE001 - un tour raté ne doit pas arrêter le suivi
                logger.warning("Tour de suivi en échec (%s : %s)", type(exc).__name__, exc)
            SLEEP(watch)
    except KeyboardInterrupt:
        return 0


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign", required=True, help="identifiant de la campagne")
    parser.add_argument("--json", action="store_true", help="sortie JSON qb.status/1")
    parser.add_argument(
        "--watch", type=float, default=None, metavar="SECONDES", help="rafraîchit en boucle"
    )
    parser.add_argument(
        "--notify", action="store_true", help="toasts Windows sur transitions (avec --watch)"
    )
    parser.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE,
        help=f"rapport de pilote donnant la durée prévue (défaut : {DEFAULT_BASELINE}, relatif "
        "aux données)",
    )
    parser.add_argument(
        "--stall-minutes",
        type=float,
        default=DEFAULT_STALL_MINUTES,
        help=f"alerte « stalled » au-delà de ce délai sans ligne (défaut : {DEFAULT_STALL_MINUTES:g})",
    )


def _run(args: argparse.Namespace) -> int:
    setup_logging(COMMAND, None)  # console (stderr) seule : rien n'est écrit
    try:
        paths.check_id(args.campaign, "campagne")
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    if args.watch is not None and args.watch <= 0:
        logger.error("--watch attend un nombre de secondes positif")
        return 2
    if args.notify and not args.watch:
        logger.error("--notify demande --watch")
        return 2
    try:
        return run_status(
            args.campaign,
            baseline=args.baseline,
            stall_minutes=args.stall_minutes,
            as_json=args.json,
            watch=args.watch,
            notify=args.notify,
        )
    except StatusError as exc:
        logger.error("%s", exc)
        return 2


STATUS = (
    COMMAND,
    "Avancement d'une campagne de génération (tableau, --json qb.status/1, --watch, --notify) : "
    "lecture seule, sans verrou ni réseau",
    _configure,
    _run,
)
