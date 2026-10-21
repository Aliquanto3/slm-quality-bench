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
  - ``eta`` : fin estimée (maintenant + ``remaining_h``), ``null`` si complète ;
    ``remaining_h`` : heures restantes estimées (0 si complète) ; ``eta_low``, ``eta_high`` :
    fourchette de ``eta`` (quartiles 25 % et 75 % de l'écart réel/prévu des paires de
    calibration, chacune prévue par ``F`` calibré sans elle, appliqués aux paires à venir et,
    atténués, à la paire en cours), ``null`` sous 3 paires de calibration ou si complète ;
    ``eta_method`` : ``"per_usage"`` (voir ci-dessous) ; ``initial_end`` : première
    ligne + prévu total ; ``drift_h``, ``drift_pct`` : ``eta`` - ``initial_end`` en heures et en %
    du prévu total (``null`` si ``eta`` ou ``initial_end`` est inconnu) ;
  - ``error_rate_last50`` : part (0 à 1) de lignes ``error`` ou ``context_exceeded`` parmi les
    50 dernières lignes (``null`` sans ligne).
- ``models`` : un objet par modèle, dans l'ordre du YAML : ``tag``, ``state`` (``"upcoming"`` |
  ``"running"`` | ``"done"``), ``lines_done``, ``lines_expected``, ``percent``, ``wall_h``,
  ``planned_h``, ``remaining_h`` (heures restantes estimées, 0 si fini), ``statuses``,
  ``baseline`` (``"measured"`` si toutes ses pistes sont dans la référence, sinon
  ``"estimated"``), ``tracks`` : liste de ``{track, lines_done,
  lines_expected, planned_h, baseline}``.
- ``log`` : ``{"ollama_unresponsive_warnings": int, "last_unload": {"model": str, "at": iso}
  | null}`` (``log-generate.log``).
- ``alerts`` : liste de ``{"code", "message"}``. Codes : ``stalled`` (dernière ligne plus
  ancienne que ``--stall-minutes`` alors que la campagne n'est pas complète),
  ``generator_stopped`` (verrou libre, campagne incomplète, au moins une ligne),
  ``stop_requested``, ``ollama_unresponsive`` (au moins un avertissement au journal),
  ``baseline_missing``.

Méthode d'estimation (``eta_method`` = ``"per_usage"``). ``generate`` traite les questions d'une
piste par blocs d'usage, et le coût d'une ligne dépend de son usage (``reasoning`` et ``rag``
long coûtent bien plus qu'``abstention``) comme du modèle (verbosité). Pour chaque (modèle,
piste) : prévu par ligne ``p`` (référence, uniforme) ; facteur ``F(piste, usage)`` = médiane, sur
les paires de calibration (référence mesurée, paire terminée ; usage vu sur 5 lignes au moins),
de (durée moyenne d'une ligne de l'usage / ``p``) ; repli : ratio réel/prévu des paires de
calibration de la piste, puis de toutes, puis 1. Une paire en cours ne calibre pas : elle n'a vu
que les premiers blocs d'usage du plan. Reste d'une paire à venir = Σ usages (lignes restantes ×
``p`` × ``F``) ; d'une paire en cours,
idem × un facteur propre rétréci vers 1 (``(n·c + 50)/(n + 50)``), ou sa moyenne observée pour un
usage déjà vu sur 10 lignes ou plus. Une paire sans référence (``estimated``) ne participe pas à
``F`` : son ``p`` est la médiane des moyennes observées des paires terminées de la piste.
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
                    "usage": _usage_of(record, key),
                    "wall_s": float(wall) if isinstance(wall, int | float) else 0.0,
                    "at": _parse_utc(record.get("created_at")),
                }
            )
        return self.rows


def _usage_of(record: Mapping[str, Any], key: str) -> str:
    """Usage de la ligne : champ ``usage``, sinon préfixe de l'id de question de la clé
    (``campagne|modèle|piste|rag/piaf/0027|0`` donne ``rag``)."""
    usage = record.get("usage")
    if isinstance(usage, str) and usage:
        return usage
    parts = key.split("|")
    return parts[3].split("/")[0] if len(parts) >= 5 else "?"


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

Plan = tuple[config.CampaignConfig, dict[str, dict[str, int]], dict[str, dict[str, int]]]


def expected_lines(campaign: str) -> Plan:
    """Configuration de la campagne, lignes attendues ``{tag: {piste: n}}`` (questions du plan
    × k) et, par piste, lignes attendues par usage ``{piste: {usage: n}}`` (ordre du plan), avec
    la même sélection que ``generate``."""
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
    usages = {
        track: dict(Counter(str(question["usage"]) for question in plan[track])) for track in TRACKS
    }
    usages = {track: {u: n * k for u, n in counts.items()} for track, counts in usages.items()}
    return cfg, result, usages


def _iso(moment: datetime | None, tz: Any) -> str | None:
    """``tz`` ``None`` : fuseau local à l'instant même (heure d'été ou d'hiver selon la date)."""
    return None if moment is None else moment.astimezone(tz).isoformat(timespec="seconds")


def _display_tz(now: datetime) -> Any:
    """Fuseau d'affichage : ``None`` (local à chaque instant) si ``now`` est à l'heure locale,
    sinon le fuseau de ``now`` (tests). Un décalage fixe capté à ``now`` décalerait d'une heure
    toute heure située après un changement d'heure."""
    return None if now.utcoffset() == now.astimezone().utcoffset() else now.tzinfo


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
            else:  # aucune référence : durées observées de la piste, sinon références des
                # autres pistes ; 0 seulement sans aucune référence ni ligne
                walls = [r["wall_s"] for (_, t), rs in done.items() if t == track for r in rs]
                others = [s for values in known.values() for s in values]
                value = statistics.median(walls or others) if walls or others else 0.0
                result[(tag, track)] = (value, "estimated")
    return result


CALIBRATION_USAGE_LINES = 5  # lignes d'un usage minimales pour entrer dans la médiane de F
OWN_USAGE_LINES = 10  # lignes d'un usage à partir desquelles la paire se fie à sa moyenne
SHRINK_LINES = 50  # poids du rétrécissement du facteur propre vers 1
MIN_RANGE_PAIRS = 3  # paires de calibration minimales pour une fourchette
ETA_METHOD = "per_usage"

Pair = tuple[str, str]


@dataclass
class Estimate:
    """Secondes restantes : centrale, bornes de la fourchette (``None`` sans assez de paires
    observées) et par modèle."""

    remaining_s: float = 0.0
    low_s: float | None = None
    high_s: float | None = None
    by_model: dict[str, float] = field(default_factory=dict)


def _sum_by_usage(rows: list[dict[str, Any]]) -> dict[str, tuple[int, float]]:
    totals: dict[str, tuple[int, float]] = {}
    for row in rows:
        n, wall = totals.get(row["usage"], (0, 0.0))
        totals[row["usage"]] = (n + 1, wall + row["wall_s"])
    return totals


def estimate_remaining(
    expected: Mapping[str, Mapping[str, int]],
    usages: Mapping[str, Mapping[str, int]],
    per_line: Mapping[Pair, tuple[float, str]],
    done: Mapping[Pair, list[dict[str, Any]]],
    rest_override: Mapping[Pair, Mapping[str, int]] | None = None,
) -> Estimate:
    """Temps restant estimé par usage (voir la docstring du module). ``usages`` : lignes
    attendues ``{piste: {usage: n}}`` ; ``per_line`` : prévu par ligne et nature de la référence
    de chaque paire ; ``done`` : lignes faites de chaque (modèle, piste) ; ``rest_override`` :
    horizon borné pour les rétro-tests, ``{paire: {usage: lignes}}`` exactement (les paires
    absentes ne comptent pas)."""
    by_usage = {pair: _sum_by_usage(rows) for pair, rows in done.items()}
    measured = {pair for pair, (_, kind) in per_line.items() if kind == "measured"}
    # Calibration sur les paires mesurées terminées seulement : une paire en cours n'a vu que les
    # premiers blocs d'usage du plan (souvent les moins coûteux) et ferait sauter F à chaque tour.
    calibration = [
        pair
        for pair in measured
        if per_line[pair][0] > 0 and len(done.get(pair, ())) >= max(expected[pair[0]][pair[1]], 1)
    ]

    def ratio(pairs: list[Pair]) -> float | None:
        wall = sum(r["wall_s"] for pair in pairs for r in done.get(pair, ()))
        planned = sum(per_line[pair][0] * len(done.get(pair, ())) for pair in pairs)
        return wall / planned if planned > 0 else None

    def factors(excluded: Pair | None) -> Any:
        """``F(piste, usage)`` calibré sans la paire ``excluded`` (validation croisée)."""
        samples: dict[tuple[str, str], list[float]] = {}
        for pair in calibration:
            if pair == excluded:
                continue
            for usage, (n, wall) in by_usage[pair].items():
                if n >= CALIBRATION_USAGE_LINES:
                    samples.setdefault((pair[1], usage), []).append(wall / n / per_line[pair][0])
        observed = [pair for pair in calibration if pair != excluded]
        global_ratio = ratio(observed) or 1.0
        track_ratio = {
            track: ratio([pair for pair in observed if pair[1] == track]) or global_ratio
            for track in {pair[1] for pair in per_line}
        }

        def factor(track: str, usage: str) -> float:
            values = samples.get((track, usage))
            return statistics.median(values) if values else track_ratio.get(track, global_ratio)

        return factor

    factor = factors(None)
    mixes: dict[str, float] = {}

    def mix(track: str) -> float:
        if track not in mixes:
            counts = usages.get(track, {})
            total = sum(counts.values())
            weighted = sum(n * factor(track, u) for u, n in counts.items())
            mixes[track] = weighted / total if total and weighted > 0 else 1.0
        return mixes[track]

    # Prévu par ligne d'une paire sans référence : médiane des moyennes observées des paires
    # terminées de la piste, sinon la valeur de ``per_line``.
    finished: dict[str, list[float]] = {}
    for pair, rows in done.items():
        if pair in per_line and rows and len(rows) >= expected.get(pair[0], {}).get(pair[1], 1):
            finished.setdefault(pair[1], []).append(sum(r["wall_s"] for r in rows) / len(rows))

    def base(pair: Pair, usage: str) -> float:
        """Secondes attendues pour une ligne de cet usage, avant facteur propre de la paire."""
        p, kind = per_line[pair]
        if kind == "measured":
            return p * factor(pair[1], usage)
        if pair[1] in finished:
            p = statistics.median(finished[pair[1]])
        return p * factor(pair[1], usage) / mix(pair[1])

    def pair_ratio(pair: Pair) -> float | None:
        planned = sum(n * base(pair, u) for u, (n, _) in by_usage.get(pair, {}).items())
        wall = sum(w for _, w in by_usage.get(pair, {}).values())
        return wall / planned if planned > 0 else None

    # Fourchette : écart réel/prévu de chaque paire calibrée, prévue par F calibré sans elle
    # (validation croisée : un écart mesuré sur la paire qui a fixé F serait proche de 1).
    held_out = []
    for pair in calibration:
        loo = factors(pair)
        planned = sum(
            n * per_line[pair][0] * loo(pair[1], u) for u, (n, _) in by_usage[pair].items()
        )
        if planned > 0:
            held_out.append(sum(w for _, w in by_usage[pair].values()) / planned)
    quartiles = None
    if len(held_out) >= MIN_RANGE_PAIRS:
        q = statistics.quantiles(held_out, n=4, method="inclusive")
        quartiles = (q[0], q[2])

    estimate = Estimate()
    low = high = 0.0
    for tag, track_lines in expected.items():
        model_s = 0.0
        for track, n in track_lines.items():
            pair = (tag, track)
            if pair not in per_line:
                continue
            rows = done.get(pair, [])
            seen = by_usage.get(pair, {})
            if rest_override is not None:
                rest = {u: float(c) for u, c in rest_override.get(pair, {}).items()}
            else:
                left = n - len(rows)
                if left <= 0:
                    continue
                rest = {
                    u: float(max(c - seen.get(u, (0, 0.0))[0], 0))
                    for u, c in usages.get(track, {}).items()
                }
                total = sum(rest.values())
                if total != left:  # usages inconnus ou plan changé : ramène au nombre de lignes
                    rest = {u: c * left / total for u, c in rest.items()} if total else {"?": left}
            weight = 1.0  # part du reste qui dépend encore de F (1 pour une paire à venir)
            shrunk = 1.0
            if rows and (own := pair_ratio(pair)) is not None:
                weight = SHRINK_LINES / (len(rows) + SHRINK_LINES)
                shrunk = (len(rows) * own + SHRINK_LINES) / (len(rows) + SHRINK_LINES)
            seconds = 0.0
            for usage, count in rest.items():
                n_seen, wall_seen = seen.get(usage, (0, 0.0))
                if n_seen >= OWN_USAGE_LINES:
                    seconds += count * wall_seen / n_seen
                else:
                    seconds += count * base(pair, usage) * shrunk
            model_s += seconds
            if quartiles:
                low += seconds * (1 + (quartiles[0] - 1) * weight)
                high += seconds * (1 + (quartiles[1] - 1) * weight)
        estimate.remaining_s += model_s
        estimate.by_model[tag] = model_s
    if quartiles:
        estimate.low_s = min(low, estimate.remaining_s)
        estimate.high_s = max(high, estimate.remaining_s)
    return estimate


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
    tz = _display_tz(now)
    cfg, expected, usages = plan or expected_lines(campaign)
    rows = cache.update()
    baseline = load_baseline(baseline_path)

    done: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        done.setdefault((str(row["model"]), str(row["track"])), []).append(row)
    per_line = _per_line_seconds(expected, baseline, done)

    models: list[dict[str, Any]] = []
    total_statuses: Counter[str] = Counter()
    lines_done = lines_expected = 0
    planned_total = planned_done = wall_total = 0.0
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

    estimate = estimate_remaining(expected, usages, per_line, done)
    for model in models:
        done_state = model["state"] == "done"
        model["remaining_h"] = (
            0.0 if done_state else round(_hours(estimate.by_model[model["tag"]]), 4)
        )
    complete = lines_expected > 0 and lines_done >= lines_expected
    ratio = wall_total / planned_done if planned_done > 0 and rows else 1.0
    times = [row["at"] for row in rows if row["at"] is not None]
    first = min(times) if times else None
    last = max(times) if times else None
    age_min = (now - last).total_seconds() / 60.0 if last else None
    elapsed_end = last if complete and last else now
    elapsed_h = _hours((elapsed_end - first).total_seconds()) if first else 0.0
    eta = eta_low = eta_high = initial_end = None
    if first is not None:
        initial_end = datetime.fromtimestamp(first.timestamp() + planned_total, UTC)
        if not complete:
            eta = datetime.fromtimestamp(now.timestamp() + estimate.remaining_s, UTC)
            if estimate.low_s is not None and estimate.high_s is not None:
                eta_low = datetime.fromtimestamp(now.timestamp() + estimate.low_s, UTC)
                eta_high = datetime.fromtimestamp(now.timestamp() + estimate.high_s, UTC)
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
            "eta_low": _iso(eta_low, tz),
            "eta_high": _iso(eta_high, tz),
            "eta_method": ETA_METHOD,
            "remaining_h": 0.0 if complete else round(_hours(estimate.remaining_s), 4),
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
_STATUS_ABBR = {"truncated": "tr", "context_exceeded": "ctx", "error": "err"}
_STATE_ICON = {"upcoming": "⬜", "running": "⏳", "done": "✅"}
LATE_PCT = 10.0  # même seuil que le premier palier de toast de dérive
EARLY_PCT = -5.0
ERROR_WARN, ERROR_BAD = 0.05, 0.20
BAR_WIDTH = 30
RULE = "━" * 72

# Codes ANSI : vert, orange (jaune), rouge, cyan, gras, atténué.
_SGR = {"green": "32", "orange": "33", "red": "31", "cyan": "36", "bold": "1", "dim": "2"}


class _Paint:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def __call__(self, text: str, *styles: str) -> str:
        if not self.enabled or not styles:
            return text
        return f"\033[{';'.join(_SGR[style] for style in styles)}m{text}\033[0m"


def _num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _count(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _when(iso: str | None) -> str:
    if not iso:
        return "?"
    moment = datetime.fromisoformat(iso)
    return f"{_DAYS[moment.weekday()]} {moment:%d/%m} à {moment:%H:%M}"


def _span(hours: float) -> str:
    """Durée lisible d'un coup d'œil : « 2 j 3 h », « 5 h 20 », « 12 min »."""
    minutes = max(0, round(hours * 60))
    days, rest = divmod(minutes, 24 * 60)
    h, m = divmod(rest, 60)
    if days:
        return f"{days} j {h} h"
    if h:
        return f"{h} h {m:02d}"
    return f"{m} min"


def _bar(percent: float, width: int = BAR_WIDTH) -> str:
    filled = round(max(0.0, min(100.0, percent)) / 100 * width)
    return "█" * filled + "░" * (width - filled)


def verdict(status: Mapping[str, Any]) -> tuple[str, str, str]:
    """(icône, libellé, couleur) de l'état de santé global, en tête de la synthèse."""
    o = status["overall"]
    codes = {a["code"] for a in status["alerts"]}
    if o["state"] == "complete":
        return "🏁", "TERMINÉE", "green"
    if o["state"] == "not_started":
        return "⚪", "PAS COMMENCÉE", "dim"
    if codes & {"stalled", "generator_stopped", "ollama_unresponsive"}:
        label = "ARRÊTÉE" if "generator_stopped" in codes else "BLOQUÉE"
        return "🔴", f"{label}, À VÉRIFIER", "red"
    if "stop_requested" in codes:
        return "⏸️", "PAUSE DEMANDÉE", "orange"
    drift = o["drift_pct"]
    if drift is not None and drift >= LATE_PCT:
        return "🟠", "EN RETARD", "orange"
    if drift is not None and drift <= EARLY_PCT:
        return "🟢", "EN AVANCE", "green"
    return "🟢", "DANS LES TEMPS", "green"


def _gap(o: Mapping[str, Any], paint: _Paint) -> str | None:
    drift_h, drift_pct = o["drift_h"], o["drift_pct"]
    if drift_h is None or drift_pct is None:
        return None
    if abs(drift_h) < 0.5:
        return paint("✔ à l'heure", "green")
    if drift_h < 0:
        return paint(f"⚡ {_span(-drift_h)} d'avance ({drift_pct:+.0f} %)", "green", "bold")
    colour = "red" if drift_pct >= 2 * LATE_PCT else "orange" if drift_pct >= LATE_PCT else "green"
    return paint(f"⏰ {_span(drift_h)} de retard ({drift_pct:+.0f} %)", colour, "bold")


def _health(status: Mapping[str, Any], paint: _Paint) -> str | None:
    o = status["overall"]
    age = o["last_line_age_min"]
    if age is None:
        return None
    stalled = "stalled" in {a["code"] for a in status["alerts"]}
    text = paint(f"dernière réponse il y a {age:.0f} min", "red" if stalled else "green")
    rate = o["error_rate_last50"]
    if rate is not None:
        icon, colour = "✅", "green"
        if rate >= ERROR_BAD:
            icon, colour = "🔴", "red"
        elif rate >= ERROR_WARN:
            icon, colour = "⚠️", "orange"
        text += " · " + paint(
            f"{icon} {rate * 100:.0f} % d'échecs sur les {RECENT_LINES} dernières", colour
        )
    return f"   💓 {text}"


def _summary(status: Mapping[str, Any], paint: _Paint) -> list[str]:
    o = status["overall"]
    models = status["models"]
    done = sum(m["state"] == "done" for m in models)
    icon, label, colour = verdict(status)
    title = (
        f"🧪 BENCHMARK {status['campaign']} · {len(models)} modèles · "
        f"{_count(o['lines_expected'])} réponses"
    )
    lines = [paint(RULE, "cyan"), paint(title, "bold"), paint(RULE, "cyan"), ""]
    lines += [f"   {icon}  {paint(label, colour, 'bold')}", ""]
    percent = paint(f"{_num(o['percent'], 0)} %", "bold")
    lines.append(f"   📊 Avancement   {paint(_bar(o['percent']), colour)}  {percent}")
    lines.append(
        f"                   {done}/{len(models)} modèles terminés · "
        f"{_count(o['lines_done'])}/{_count(o['lines_expected'])} réponses"
    )
    generated = datetime.fromisoformat(status["generated_at"])
    if o["state"] == "complete":
        lines.append(
            f"   ⏱️  Durée totale  {_span(o['elapsed_h'] or 0)} (prévu {_span(o['planned_h'])})"
        )
    elif o["eta"]:
        remaining = (datetime.fromisoformat(o["eta"]) - generated).total_seconds() / 3600
        eta = paint(_when(o["eta"]), "bold")
        lines.append(f"   🏁 Fin estimée  {eta}  (dans {_span(remaining)})")
        if o.get("eta_low") and o.get("eta_high"):
            low, high = _when(o["eta_low"]), _when(o["eta_high"])
            lines.append(f"                   entre {low} et {high}")
        gap = _gap(o, paint)
        if gap:
            lines.append(f"   📅 Prévu au départ {_when(o['initial_end'])}  → {gap}")
        lines.append(
            f"   ⏱️  Écoulé {_span(o['elapsed_h'] or 0)} · "
            f"vitesse ×{_num(o['speed_ratio'], 2)} du prévu"
        )
    current = next((m for m in models if m["state"] == "running"), None)
    following = next((m for m in models if m["state"] == "upcoming"), None)
    if current or following:
        now_text = "aucun"
        if current:
            now_text = f"{paint(current['tag'], 'bold')} ({_num(current['percent'], 0)} %)"
        after = f" · ensuite {following['tag']}" if following else ""
        lines.append(f"   ▶️  En cours      {now_text}{after}")
    health = _health(status, paint)
    if health:
        lines.append(health)
    if status["alerts"]:
        lines.append("")
        lines += [paint(f"   🚨 {a['message']}"[:100], "red", "bold") for a in status["alerts"]]
    lines.append("")
    return lines


def _speed_colour(model: Mapping[str, Any]) -> str | None:
    """Vert si le modèle tient sa durée prévue au prorata des lignes faites, orange au-delà de
    +10 %, rouge au-delà de +25 %."""
    if not model["lines_done"] or not model["planned_h"] or not model["lines_expected"]:
        return None
    planned_so_far = model["planned_h"] * model["lines_done"] / model["lines_expected"]
    ratio = model["wall_h"] / planned_so_far
    if ratio > 1.25:
        return "red"
    if ratio > 1.10:
        return "orange"
    return "green"


def _details(status: Mapping[str, Any], paint: _Paint) -> list[str]:
    header = (
        f"   {'modèle':<27} {'avancement':<12} {'%':>4}  {'réel/prévu':>12}  {'reste':>8}  hors ok"
    )
    lines = [paint("Détail par modèle", "bold"), paint(header, "dim")]
    for model in status["models"]:
        state = model["state"]
        flag = "~" if model["baseline"] == "estimated" else " "
        extra = " ".join(
            f"{_STATUS_ABBR.get(s, s)} {n}" for s, n in model["statuses"].items() if s != "ok"
        )
        timing = f"{_num(model['wall_h'])}/{_num(model['planned_h'])} h{flag}"
        speed = _speed_colour(model)
        timing = paint(f"{timing:>12}", speed) if speed else f"{timing:>12}"
        left = model.get("remaining_h")
        reste = f"~{_span(left)}" if state != "done" and left is not None else ""
        row = (
            f"{_STATE_ICON[state]} {model['tag'][:27]:<27} {_bar(model['percent'], 12)} "
            f"{_num(model['percent'], 0):>4}  {timing}  {reste:>8}  {extra}"
        ).rstrip()
        style = {"upcoming": ("dim",), "running": ("bold",)}.get(state, ())
        lines.append(paint(row, *style))
    lines.append(
        paint(
            "✅ terminé · ⏳ en cours · ⬜ à venir · réel/prévu : vert, orange (> +10 %), "
            "rouge (> +25 %) · ~ estimé",
            "dim",
        )
    )
    return lines


def render_text(status: Mapping[str, Any], *, color: bool = False) -> str:
    """Synthèse de direction en tête (état, avancement, fin estimée, dérive), puis le détail
    par modèle. Sans couleur, 100 colonnes au plus ; ``color`` ajoute les codes ANSI."""
    paint = _Paint(color)
    return "\n".join(_summary(status, paint) + _details(status, paint))
