"""Toasts Windows de ``status --watch --notify`` : transitions seulement, état en mémoire.

Un toast ne porte jamais de contenu de question ou de réponse (dépôt public, données privées) :
seulement des tags de modèle, des compteurs et des heures. Un échec du toast est un
avertissement au journal, jamais une erreur de sortie.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Mapping
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Identifiant d'application qui affiche un toast sans enregistrement préalable.
TOAST_APP_ID = "Microsoft.Windows.Shell.RunDialog"
TITLE_ENV = "QB_TOAST_TITLE"
BODY_ENV = "QB_TOAST_BODY"
# Texte transmis par variables d'environnement (jamais interpolé dans le script) et échappé en
# XML côté PowerShell.
TOAST_SCRIPT = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$title = [System.Security.SecurityElement]::Escape($env:{TITLE_ENV})
$body = [System.Security.SecurityElement]::Escape($env:{BODY_ENV})
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$title</text><text>$body</text></binding></visual></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{TOAST_APP_ID}').Show($toast)
"""


class Notifier(Protocol):
    def notify(self, title: str, message: str) -> None: ...


class ToastNotifier:
    """Toast via ``powershell -NoProfile`` et l'API WinRT, sans module externe."""

    def __init__(self, timeout_s: float = 30.0) -> None:
        self.timeout_s = timeout_s

    def notify(self, title: str, message: str) -> None:
        env = {**os.environ, TITLE_ENV: title, BODY_ENV: message}
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", TOAST_SCRIPT],
                env=env,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Toast non affiché (%s) : %s", type(exc).__name__, title)
            return
        if result.returncode != 0:
            logger.warning("Toast non affiché (powershell, code %d) : %s", result.returncode, title)


DRIFT_STEP_PCT = 10.0
# Hystérésis : un palier n'est quitté vers le bas qu'une fois l'écart passé sous palier - 5 points,
# pour qu'un écart qui oscille autour d'un seuil ne déclenche pas un toast à chaque passage.
DRIFT_HYSTERESIS_PCT = 5.0


def drift_level(drift_pct: float | None) -> int | None:
    """0 sous +10 %, puis 1 par palier de 10 % ; ``None`` si l'écart est inconnu."""
    if drift_pct is None:
        return None
    return int(drift_pct // DRIFT_STEP_PCT) if drift_pct >= DRIFT_STEP_PCT else 0


class Transitions:
    """Détecte les événements marquants entre deux états ``qb.status/1`` successifs. La première
    observation sert de référence et ne notifie rien."""

    def __init__(self) -> None:
        self._previous: Mapping[str, Any] | None = None
        self._level = 0

    def events(self, status: Mapping[str, Any]) -> list[tuple[str, str]]:
        previous, self._previous = self._previous, status
        level = drift_level(status["overall"]["drift_pct"])
        if previous is None:
            self._level = level or 0
            return []
        campaign = status["campaign"]
        o, old = status["overall"], previous["overall"]
        out: list[tuple[str, str]] = []

        was_done = {m["tag"] for m in previous["models"] if m["state"] == "done"}
        for model in status["models"]:
            if model["state"] == "done" and model["tag"] not in was_done:
                out.append(
                    (
                        f"{campaign} : modèle terminé",
                        f"{model['tag']} : {model['lines_done']}/{model['lines_expected']} lignes, "
                        f"{model['wall_h']:.1f} h actives. Campagne à {o['percent']:.1f} %.",
                    )
                )
        if o["complete"] and not old["complete"]:
            out.append(
                (
                    f"{campaign} : campagne terminée",
                    f"{o['lines_done']} lignes, {o['wall_h']:.1f} h actives, "
                    f"{o['elapsed_h']:.1f} h écoulées.",
                )
            )
        stalled = _has_alert(status, "stalled")
        if stalled and not _has_alert(previous, "stalled"):
            out.append(
                (
                    f"{campaign} : campagne bloquée ?",
                    f"Aucune ligne depuis {o['last_line_age_min'] or 0:.0f} min "
                    f"({o['lines_done']}/{o['lines_expected']}).",
                )
            )
        if level is not None and level < self._level:
            # Descente seulement sous le palier courant moins l'hystérésis.
            level = min(self._level, drift_level(o["drift_pct"] + DRIFT_HYSTERESIS_PCT) or 0)
        if level is not None and level != self._level:
            if level > self._level:
                out.append(
                    (
                        f"{campaign} : fin estimée en retard",
                        f"Écart de {o['drift_pct']:+.0f} % ({o['drift_h']:+.1f} h) "
                        "sur la fin initiale.",
                    )
                )
            elif level == 0:
                out.append(
                    (
                        f"{campaign} : retard résorbé",
                        f"Écart revenu sous +10 % ({o['drift_pct']:+.1f} %).",
                    )
                )
            self._level = level
        if (
            previous["generator"]["lock_held"]
            and not status["generator"]["lock_held"]
            and not o["complete"]
        ):
            out.append(
                (
                    f"{campaign} : générateur arrêté",
                    f"Verrou libéré à {o['lines_done']}/{o['lines_expected']} lignes.",
                )
            )
        warnings = status["log"]["ollama_unresponsive_warnings"]
        if warnings > previous["log"]["ollama_unresponsive_warnings"]:
            out.append(
                (
                    f"{campaign} : Ollama ne répond plus",
                    f"{warnings} avertissement(s) au journal.",
                )
            )
        return out


def _has_alert(status: Mapping[str, Any], code: str) -> bool:
    return any(alert["code"] == code for alert in status["alerts"])


def dispatch(notifier: Notifier, events: list[tuple[str, str]]) -> None:
    """Envoie les toasts ; une exception du notifier n'interrompt jamais le suivi."""
    for title, message in events:
        try:
            notifier.notify(title, message)
        except Exception as exc:  # noqa: BLE001 - un toast raté ne doit jamais faire échouer
            logger.warning("Toast non affiché (%s) : %s", type(exc).__name__, title)
