"""Lanceur du pilote, en une commande reprenable :

    python -m slm_quality_bench.run_pilot --campaign pilot-20261017

Il enchaîne, **chacune dans son propre processus** (les phases ne communiquent que par fichiers,
AD-1 : ce lanceur n'est pas une sous-commande du banc et n'appelle aucune phase en mémoire) :

1. ``precheck`` : contrôles d'avant campagne en lecture seule ;
2. ``generate`` du pilote, puis ``generate`` du rejeu ``<c>-replay`` ;
3. ``grade`` du pilote, puis du rejeu ;
4. ``pilot --campaign <c> --replay <c>-replay`` : le rapport.

Il s'arrête au premier code de sortie non nul, qu'il rend tel quel. Il ne lance pas le juge
(étape séparée et payante, voir ``docs/LANCER-LE-PILOTE.md``). Relancer la même commande reprend
là où l'on s'est arrêté : ``generate`` reprend sans doublon, ``grade`` et ``pilot`` réécrivent
leurs sorties à l'identique.

Un arrêt propre de ``generate`` (Ctrl+C, fichier ``STOP``) sort avec le code 0 : le lanceur le
distingue d'une campagne complète par le journal de la campagne et s'arrête alors lui aussi
(code 3), sans corriger de génération incomplète. Ctrl+C pendant une étape la laisse se terminer
proprement, puis le lanceur sort avec le code 130.

Codes de sortie : 0 (rapport écrit) ; code de la première étape refusée (1 ou 2) ; 3 (arrêt
propre de la génération) ; 130 (interruption).
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Callable, Sequence

from .common import paths
from .common.logs import setup_logging
from .generation.commands import COMPLETE_MESSAGE, STOPPED_MESSAGE
from .ollama.client import DEFAULT_BASE_URL
from .precheck import EXPECTED_OLLAMA_VERSION

logger = logging.getLogger(__name__)

COMMAND = "run-pilot"
EXIT_STOPPED = 3
EXIT_INTERRUPTED = 130


class InterruptedStepError(Exception):
    """Ctrl+C reçu pendant une étape, qui s'est terminée proprement."""


def run_subprocess(arguments: Sequence[str]) -> int:
    """Lance ``python -m slm_quality_bench <arguments>`` et attend sa fin. Ctrl+C atteint aussi
    l'étape (même console), qui s'arrête proprement : on l'attend, puis ``InterruptedStepError``."""
    process = subprocess.Popen(
        [sys.executable, "-m", "slm_quality_bench", *arguments]
    )  # noqa: S603
    interrupted = False
    while True:
        try:
            code = process.wait()
            break
        except KeyboardInterrupt:
            interrupted = True
    if interrupted:
        raise InterruptedStepError(code)
    return code


# Point d'injection des tests : lance une étape et rend son code de sortie.
RUN_STEP: Callable[[Sequence[str]], int] = run_subprocess


def generation_completed(campaign: str) -> bool:
    """Vrai si la dernière exécution de ``generate`` de la campagne s'est terminée complète
    (dernier message du journal), faux après un arrêt propre ou sans journal."""
    path = paths.log_path(campaign, "generate")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    complete = text.rfind(COMPLETE_MESSAGE % campaign)
    stopped = text.rfind(STOPPED_MESSAGE % campaign)
    return complete > stopped


def steps(
    campaign: str, replay: str, ollama_url: str, ollama_version: str
) -> list[tuple[str, list[str]]]:
    """Étapes dans l'ordre : (libellé, arguments de ``python -m slm_quality_bench``)."""
    ollama = ["--ollama-url", ollama_url]
    return [
        (
            "contrôles d'avant campagne",
            [
                "precheck",
                "--campaign",
                campaign,
                "--replay",
                replay,
                *ollama,
                "--ollama-version",
                ollama_version,
            ],
        ),
        (f"génération {campaign}", ["generate", "--campaign", campaign, *ollama]),
        (f"génération du rejeu {replay}", ["generate", "--campaign", replay, *ollama]),
        (f"correction {campaign}", ["grade", "--campaign", campaign]),
        (f"correction du rejeu {replay}", ["grade", "--campaign", replay]),
        (
            "rapport du pilote",
            ["pilot", "--campaign", campaign, "--replay", replay],
        ),
    ]


def run_pilot(
    campaign: str,
    replay: str | None = None,
    ollama_url: str = DEFAULT_BASE_URL,
    ollama_version: str = EXPECTED_OLLAMA_VERSION,
) -> int:
    """Enchaîne les étapes ; rend le code de sortie du lanceur."""
    replay = replay or f"{campaign}-replay"
    plan = steps(campaign, replay, ollama_url, ollama_version)
    for index, (label, arguments) in enumerate(plan, start=1):
        logger.info("=== Étape %d/%d : %s ===", index, len(plan), label)
        try:
            code = RUN_STEP(arguments)
        except InterruptedStepError:
            logger.warning(
                "Interrompu pendant « %s » : relancer la même commande pour reprendre", label
            )
            return EXIT_INTERRUPTED
        if code != 0:
            logger.error(
                "Étape « %s » refusée ou en échec (code %d) : arrêt. Corriger puis relancer la "
                "même commande (reprise sans doublon).",
                label,
                code,
            )
            return code
        if arguments[0] == "generate":
            target = arguments[2]
            if not generation_completed(target):
                logger.warning(
                    "Génération de %s arrêtée avant la fin (arrêt propre) : relancer la même "
                    "commande pour reprendre ; ni correction ni rapport pour l'instant",
                    target,
                )
                return EXIT_STOPPED
    logger.info(
        "Pilote terminé : rapport sous %s (le juge reste à lancer, voir docs/LANCER-LE-PILOTE.md)",
        paths.pilot_report_path(campaign, ".md"),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m slm_quality_bench.run_pilot",
        description=(
            "Lance le pilote de bout en bout, sans le juge : precheck, generate (pilote puis "
            "rejeu), grade (idem), rapport du pilote. Reprenable : relancer la même commande."
        ),
    )
    parser.add_argument(
        "--campaign", required=True, help="campagne du pilote, p. ex. pilot-20261017"
    )
    parser.add_argument(
        "--replay", default=None, help="campagne de rejeu (défaut : <campagne>-replay)"
    )
    parser.add_argument("--ollama-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--ollama-version", default=EXPECTED_OLLAMA_VERSION)
    args = parser.parse_args(argv)
    setup_logging(COMMAND, None)
    try:
        paths.check_id(args.campaign, "campagne")
        if args.replay is not None:
            paths.check_id(args.replay, "campagne de rejeu")
    except ValueError as exc:
        logger.error("Lancement refusé : %s", exc)
        return 2
    try:
        return run_pilot(args.campaign, args.replay, args.ollama_url, args.ollama_version)
    except KeyboardInterrupt:
        logger.warning("Interrompu : relancer la même commande pour reprendre")
        return EXIT_INTERRUPTED


if __name__ == "__main__":
    sys.exit(main())
