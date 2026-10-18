"""Calcul et rendu de l'avancement d'une campagne de génération (commande ``status``).

Strictement en lecture seule : aucun fichier créé ou modifié, ``generation.lock`` jamais pris
(sa détention est sondée par une simple lecture), aucun appel réseau. Un ``generation.jsonl`` en
cours d'écriture est toléré : un fragment final sans ``\\n`` et toute ligne illisible sont
ignorés sans erreur. Aucun contenu de question ou de réponse n'est lu ni affiché.

Sortie ``status --json`` : objet ``{"schema": "qb.status/1", ...}``, stable ; un champ n'est ni
retiré ni renommé dans ``qb.status/1`` (des champs peuvent s'ajouter). Horodatages en ISO 8601
local avec décalage (``2026-10-20T14:30:00+02:00``), ``null`` si inconnus ; durées en heures
(float) ; pourcentages de 0 à 100 (float, arrondis à 0,01).

- ``schema`` : ``"qb.status/1"``.
- ``campaign``, ``set`` : identifiants ; ``k`` : essais par question ; ``generated_at`` : instant
  du calcul.
- ``baseline`` : ``{"path": str, "found": bool}`` (référence de durée prévue).
- ``generator`` : ``{"lock_held": bool, "stop_requested": bool}``. ``lock_held`` : le verrou
  ``generation.lock`` est détenu par un processus (générateur actif) ; ``stop_requested`` : le
  fichier ``STOP`` existe.
- ``overall`` :
  - ``state`` : ``"not_started"`` | ``"running"`` | ``"complete"`` ; ``complete`` : bool ;
  - ``lines_done``, ``lines_expected``, ``percent`` ;
  - ``statuses`` : ``{statut: nombre}`` des lignes faites ;
  - ``wall_h`` : temps actif (Σ ``wall_s``) ; ``elapsed_h`` : de la première ligne à maintenant
    (ou à la dernière ligne si complète), chauffes et pauses incluses ; ``planned_h`` : durée
    prévue totale ;
  - ``first_line_at``, ``last_line_at`` ; ``last_line_age_min`` (minutes depuis la dernière
    ligne) ;
  - ``speed_ratio`` : Σ ``wall_s`` des lignes faites / Σ prévu de ces lignes (1 sans ligne) ;
  - ``eta`` : fin estimée (maintenant + ratio × prévu restant), ``null`` si complète ;
    ``initial_end`` : première ligne + prévu total ; ``drift_h``, ``drift_pct`` : ``eta`` -
    ``initial_end`` en heures et en % du prévu total (``null`` si ``eta`` ou ``initial_end``
    est inconnu) ;
  - ``error_rate_last50`` : part (0 à 1) de lignes ``error`` ou ``context_exceeded`` parmi les
    50 dernières lignes (``null`` sans ligne).
- ``models`` : un objet par modèle, dans l'ordre du YAML : ``tag``, ``state`` (``"upcoming"`` |
  ``"running"`` | ``"done"``), ``lines_done``, ``lines_expected``, ``percent``, ``wall_h``,
  ``planned_h``, ``statuses``, ``baseline`` (``"measured"`` si toutes ses pistes sont dans la
  référence, sinon ``"estimated"``), ``tracks`` : liste de ``{track, lines_done,
  lines_expected, planned_h, baseline}``.
- ``log`` : ``{"ollama_unresponsive_warnings": int, "last_unload": {"model": str, "at": iso}
  | null}`` (``log-generate.log``).
- ``alerts`` : liste de ``{"code", "message"}``. Codes : ``stalled`` (dernière ligne plus
  ancienne que ``--stall-minutes`` alors que la campagne n'est pas complète),
  ``generator_stopped`` (verrou libre, campagne incomplète, au moins une ligne),
  ``stop_requested``, ``ollama_unresponsive`` (au moins un avertissement au journal),
  ``baseline_missing``.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..common import config, paths
from ..common.schemas import TRACKS
from ..generation.commands import load_set
from ..generation.runner import build_plan

SCHEMA = "qb.status/1"
DEFAULT_BASELINE = "campaigns/pilot-20261017/pilot-report.json"
DEFAULT_STALL_MINUTES = 30.0
RECENT_LINES = 50
ERROR_STATUSES = ("error", "context_exceeded")
UNRESPONSIVE_MARKER = "Ollama ne répond plus"
_UNLOAD_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) \S+ \[[^\]]*\] \S+ : (.+?) : modèle déchargé"
)
_LOCK_OFFSET = 0x7FFFFFFE  # octet verrouillé par common/locks.py sous Windows


class StatusError(RuntimeError):
    """Campagne, configuration ou jeu introuvable : code de sortie 2."""


def local_now() -> datetime:
    return datetime.now().astimezone()


# -- Lecture de generation.jsonl ---------------------------------------------------------------


@dataclass
class RowCache:
    """Lignes de ``generation.jsonl`` (champs utiles seulement), lues de façon incrémentale :
    en mémoire du processus, jamais sur disque."""

    path: Path
    offset: int = 0
    keys: set[str] = field(default_factory=set)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def _reset(self) -> None:
        self.offset, self.keys, self.rows = 0, set(), []

    def update(self) -> list[dict[str, Any]]:
        try:
            size = self.path.stat().st_size
        except OSError:
            self._reset()
            return self.rows
        if size < self.offset:  # fichier remplacé : tout relire
            self._reset()
        try:
            with open(self.path, "rb") as handle:
                handle.seek(self.offset)
                chunk = handle.read()
        except OSError:
            return self.rows
        end = chunk.rfind(b"\n")
        if end < 0:
            return self.rows  # fragment final seul : ignoré
        self.offset += end + 1
        for raw in chunk[: end + 1].splitlines():
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            key = record.get("key")
            if not isinstance(key, str) or key in self.keys:
                continue
            self.keys.add(key)
            wall = record.get("wall_s")
            self.rows.append(
                {
                    "key": key,
                    "model": record.get("model"),
                    "track": record.get("track"),
                    "status": str(record.get("status")),
                    "wall_s": float(wall) if isinstance(wall, int | float) else 0.0,
                    "at": _parse_utc(record.get("created_at")),
                }
            )
        return self.rows


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


# -- Référence de durée, journal, verrou -------------------------------------------------------


def load_baseline(path: Path) -> dict[str, dict[str, float]]:
    """``{tag: {piste: heures}}`` des modèles connus de ``projection.models[]`` ; vide si le
    fichier est absent ou illisible."""
    try:
        with open(path, encoding="utf-8") as handle:
            models = json.load(handle)["projection"]["models"]
        result: dict[str, dict[str, float]] = {}
        for entry in models:
            if not entry.get("known"):
                continue
            hours = {}
            for track in TRACKS:
                value = entry.get(f"{track}_hours")
                if isinstance(value, int | float) and value > 0:
                    hours[track] = float(value)
            result[str(entry["tag"])] = hours
        return result
    except OSError, ValueError, KeyError, TypeError, AttributeError:
        return {}


@dataclass
class LogInfo:
    unresponsive: int = 0
    last_unload: tuple[str, datetime] | None = None


def read_log(path: Path) -> LogInfo:
    info = LogInfo()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return info
    for line in text.splitlines():
        if UNRESPONSIVE_MARKER in line:
            info.unresponsive += 1
        if "modèle déchargé" in line:
            match = _UNLOAD_RE.match(line)
            if match:
                try:
                    when = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").astimezone()
                except ValueError:
                    continue
                info.last_unload = (match.group(2), when)
    return info


def lock_held(path: Path) -> bool:
    """Le verrou est-il détenu par un processus ? Sans le prendre : sous Windows, lecture de
    l'octet verrouillé (refusée tant qu'un autre processus le détient) ; ailleurs, fichier non
    vide (le détenteur y écrit son PID et le vide à la libération)."""
    if not path.exists():
        return False
    if sys.platform == "win32":
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        except OSError:
            return False
        try:
            os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
            os.read(fd, 1)
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        finally:
            os.close(fd)
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


# -- Calcul ------------------------------------------------------------------------------------

Plan = tuple[config.CampaignConfig, dict[str, dict[str, int]]]


def expected_lines(campaign: str) -> Plan:
    """Configuration de la campagne et lignes attendues ``{tag: {piste: n}}`` (questions du plan
    × k), avec la même sélection que ``generate``."""
    config_path = paths.campaign_config_path(campaign)
    if not config_path.exists():
        raise StatusError(f"configuration de campagne absente : {config_path}")
    try:
        cfg = config.load_campaign(config_path)
        questions, tracks, _ = load_set(cfg.set_id)
        plan = build_plan(cfg.generation, questions, tracks)
    except Exception as exc:  # noqa: BLE001 - toute erreur de plan est un refus de lecture
        raise StatusError(f"plan de la campagne {campaign} illisible : {exc}") from None
    k = cfg.generation["request"]["k"]
    result = {
        model["tag"]: {track: len(plan[track]) * k for track in model["tracks"]}
        for model in cfg.generation["models"]
    }
    return cfg, result


def _iso(moment: datetime | None, tz: Any) -> str | None:
    return None if moment is None else moment.astimezone(tz).isoformat(timespec="seconds")


def _hours(seconds: float) -> float:
    return seconds / 3600.0


def _percent(done: int, expected: int) -> float:
    return round(done / expected * 100.0, 2) if expected else 0.0


def _per_line_seconds(
    expected: Mapping[str, Mapping[str, int]],
    baseline: Mapping[str, Mapping[str, float]],
    done: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> dict[tuple[str, str], tuple[float, str]]:
    """Prévu par ligne (secondes) de chaque (modèle, piste) : référence si connue, sinon médiane
    des modèles connus de la même piste (``estimated``)."""
    known: dict[str, list[float]] = {}
    for tag, track_lines in expected.items():
        for track, n in track_lines.items():
            hours = baseline.get(tag, {}).get(track)
            if hours is not None and n > 0:
                known.setdefault(track, []).append(hours * 3600.0 / n)
    result: dict[tuple[str, str], tuple[float, str]] = {}
    for tag, track_lines in expected.items():
        for track, n in track_lines.items():
            hours = baseline.get(tag, {}).get(track)
            if hours is not None and n > 0:
                result[(tag, track)] = (hours * 3600.0 / n, "measured")
            elif known.get(track):
                result[(tag, track)] = (statistics.median(known[track]), "estimated")
            else:  # aucune référence : médiane des durées observées de la piste, sinon 0
                walls = [r["wall_s"] for (_, t), rs in done.items() if t == track for r in rs]
                result[(tag, track)] = (statistics.median(walls) if walls else 0.0, "estimated")
    return result


def compute_status(
    campaign: str,
    *,
    cache: RowCache,
    baseline_path: Path,
    stall_minutes: float = DEFAULT_STALL_MINUTES,
    now: datetime | None = None,
    plan: Plan | None = None,
) -> dict[str, Any]:
    """Objet ``qb.status/1`` (voir la docstring du module). ``now`` est injectable (tests)."""
    now = now or local_now()
    tz = now.tzinfo
    cfg, expected = plan or expected_lines(campaign)
    rows = cache.update()
    baseline = load_baseline(baseline_path)

    done: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        done.setdefault((str(row["model"]), str(row["track"])), []).append(row)
    per_line = _per_line_seconds(expected, baseline, done)

    models: list[dict[str, Any]] = []
    total_statuses: Counter[str] = Counter()
    lines_done = lines_expected = 0
    planned_total = planned_done = planned_remaining = wall_total = 0.0
    for tag, track_lines in expected.items():
        statuses: Counter[str] = Counter()
        track_info = []
        m_done = m_expected = 0
        m_wall = m_planned = 0.0
        for track, n in track_lines.items():
            lines = done.get((tag, track), [])
            seconds, kind = per_line[(tag, track)]
            statuses.update(row["status"] for row in lines)
            m_done += len(lines)
            m_expected += n
            m_wall += sum(row["wall_s"] for row in lines)
            m_planned += seconds * n
            planned_done += seconds * min(len(lines), n)
            planned_remaining += seconds * max(n - len(lines), 0)
            track_info.append(
                {
                    "track": track,
                    "lines_done": len(lines),
                    "lines_expected": n,
                    "planned_h": round(_hours(seconds * n), 4),
                    "baseline": kind,
                }
            )
        wall_total += m_wall
        planned_total += m_planned
        lines_done += m_done
        lines_expected += m_expected
        total_statuses.update(statuses)
        state = "upcoming" if m_done == 0 else "done" if m_done >= m_expected else "running"
        measured = all(t["baseline"] == "measured" for t in track_info)
        models.append(
            {
                "tag": tag,
                "state": state,
                "lines_done": m_done,
                "lines_expected": m_expected,
                "percent": _percent(m_done, m_expected),
                "wall_h": round(_hours(m_wall), 4),
                "planned_h": round(_hours(m_planned), 4),
                "statuses": dict(sorted(statuses.items())),
                "baseline": "measured" if measured else "estimated",
                "tracks": track_info,
            }
        )

    complete = lines_expected > 0 and lines_done >= lines_expected
    ratio = wall_total / planned_done if planned_done > 0 and rows else 1.0
    times = [row["at"] for row in rows if row["at"] is not None]
    first = min(times) if times else None
    last = max(times) if times else None
    age_min = (now - last).total_seconds() / 60.0 if last else None
    elapsed_end = last if complete and last else now
    elapsed_h = _hours((elapsed_end - first).total_seconds()) if first else 0.0
    eta = initial_end = None
    if first is not None:
        initial_end = datetime.fromtimestamp(first.timestamp() + planned_total, tz)
        if not complete:
            eta = datetime.fromtimestamp(now.timestamp() + ratio * planned_remaining, tz)
    drift_h = drift_pct = None
    if eta is not None and initial_end is not None:
        drift_h = _hours((eta - initial_end).total_seconds())
        drift_pct = drift_h / _hours(planned_total) * 100.0 if planned_total > 0 else None

    recent = rows[-RECENT_LINES:]
    error_rate = (
        sum(1 for r in recent if r["status"] in ERROR_STATUSES) / len(recent) if recent else None
    )

    log = read_log(paths.log_path(campaign, "generate"))
    held = lock_held(paths.generation_lock_path(campaign))
    stop = paths.generation_stop_path(campaign).exists()

    alerts: list[dict[str, str]] = []
    if not baseline:
        alerts.append(
            {
                "code": "baseline_missing",
                "message": f"référence de durée absente ou vide : {baseline_path}",
            }
        )
    if not complete and age_min is not None and age_min > stall_minutes:
        alerts.append(
            {
                "code": "stalled",
                "message": f"aucune ligne depuis {age_min:.0f} min (seuil {stall_minutes:g})",
            }
        )
    if not complete and rows and not held:
        alerts.append(
            {
                "code": "generator_stopped",
                "message": "verrou libre : générateur arrêté, campagne incomplète",
            }
        )
    if stop:
        alerts.append({"code": "stop_requested", "message": "fichier STOP présent"})
    if log.unresponsive:
        alerts.append(
            {
                "code": "ollama_unresponsive",
                "message": f"« {UNRESPONSIVE_MARKER} » : {log.unresponsive} avertissement(s)",
            }
        )

    unload = None
    if log.last_unload is not None:
        unload = {"model": log.last_unload[0], "at": _iso(log.last_unload[1], tz)}
    return {
        "schema": SCHEMA,
        "campaign": campaign,
        "set": cfg.set_id,
        "k": cfg.generation["request"]["k"],
        "generated_at": _iso(now, tz),
        "baseline": {"path": str(baseline_path), "found": bool(baseline)},
        "generator": {"lock_held": held, "stop_requested": stop},
        "overall": {
            "state": "complete" if complete else "running" if rows else "not_started",
            "complete": complete,
            "lines_done": lines_done,
            "lines_expected": lines_expected,
            "percent": _percent(lines_done, lines_expected),
            "statuses": dict(sorted(total_statuses.items())),
            "wall_h": round(_hours(wall_total), 4),
            "elapsed_h": round(elapsed_h, 4),
            "planned_h": round(_hours(planned_total), 4),
            "first_line_at": _iso(first, tz),
            "last_line_at": _iso(last, tz),
            "last_line_age_min": None if age_min is None else round(age_min, 2),
            "speed_ratio": round(ratio, 4),
            "eta": _iso(eta, tz),
            "initial_end": _iso(initial_end, tz),
            "drift_h": None if drift_h is None else round(drift_h, 4),
            "drift_pct": None if drift_pct is None else round(drift_pct, 2),
            "error_rate_last50": None if error_rate is None else round(error_rate, 4),
        },
        "models": models,
        "log": {"ollama_unresponsive_warnings": log.unresponsive, "last_unload": unload},
        "alerts": alerts,
    }


# -- Rendu texte -------------------------------------------------------------------------------

_DAYS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")
_STATE_LABEL = {"upcoming": "à venir", "running": "en cours", "done": "terminé"}
_STATUS_ABBR = {"truncated": "tr", "context_exceeded": "ctx", "error": "err"}


def _num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _when(iso: str | None) -> str:
    if not iso:
        return "?"
    moment = datetime.fromisoformat(iso)
    return f"{_DAYS[moment.weekday()]} {moment:%d/%m %H:%M}"


def render_text(status: Mapping[str, Any]) -> str:
    """Tableau compact en français, 100 colonnes au plus."""
    o = status["overall"]
    ratio = _num(o["speed_ratio"], 2)
    lines = [
        f"Campagne {status['campaign']} : {_num(o['percent'])} % "
        f"({o['lines_done']}/{o['lines_expected']} lignes), écoulé {_num(o['elapsed_h'])} h, "
        f"actif {_num(o['wall_h'])} h"
    ]
    if o["complete"]:
        lines.append(f"Terminée ; durée prévue {_num(o['planned_h'])} h, vitesse x{ratio}")
    else:
        drift = ""
        if o["drift_h"] is not None and o["drift_pct"] is not None:
            drift = f", écart {o['drift_h']:+.1f} h ({o['drift_pct']:+.1f} %)".replace(".", ",")
        lines.append(
            f"Fin estimée {_when(o['eta'])} (initiale {_when(o['initial_end'])}){drift}, "
            f"vitesse x{ratio}"
        )
    age = o["last_line_age_min"]
    age_text = "aucune ligne" if age is None else f"il y a {age:.0f} min"
    rate = o["error_rate_last50"]
    rate_text = "n/a" if rate is None else f"{rate * 100:.0f} %"
    gen = "actif" if status["generator"]["lock_held"] else "arrêté"
    lines.append(
        f"Dernière ligne {age_text} ; erreurs/contexte sur {RECENT_LINES} dernières : "
        f"{rate_text} ; générateur {gen}"
    )
    lines.append("")
    lines.append(
        f"{'#':>2} {'modèle':<27} {'état':<8} {'lignes':>11} {'%':>6} {'réel h':>7} "
        f"{'prévu h':>8}  statuts"
    )
    for index, model in enumerate(status["models"], 1):
        flag = "~" if model["baseline"] == "estimated" else " "
        extra = " ".join(
            f"{_STATUS_ABBR.get(s, s)} {n}" for s, n in model["statuses"].items() if s != "ok"
        )
        row = (
            f"{index:>2} {model['tag'][:27]:<27} {_STATE_LABEL[model['state']]:<8} "
            f"{model['lines_done']:>5}/{model['lines_expected']:<5} {_num(model['percent']):>6} "
            f"{_num(model['wall_h']):>7} {_num(model['planned_h']):>7}{flag} {extra}"
        )
        lines.append(row.rstrip()[:100])
    lines.append("(~ : durée prévue estimée, modèle absent de la référence)")
    if status["alerts"]:
        lines.append("")
        lines.extend(f"ALERTE {a['code']} : {a['message']}"[:100] for a in status["alerts"])
    return "\n".join(lines)
