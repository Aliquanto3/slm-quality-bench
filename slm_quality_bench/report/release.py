"""Sous-commande ``export-release --campaign <c>… --version X.Y.Z`` (AD-18, CAP-10) : écrit
``benchmarks/quality/releases/<version>/slm-quality-results.json`` au schéma ``qb.results/1``
(``docs/schemas/qb.results-1.schema.json``), le fichier que wavelocalai récupère en release.

Hors ligne, sans Ollama ni verrou machine. Lit, pour chaque campagne, ``generation.jsonl``,
``grading.jsonl``, ``warmups.jsonl``, ``memory.jsonl`` et les manifestes, réutilise les
statistiques du rapport (``build_summary``, AD-17) et le registre des modèles
(``models.yaml``). JSON canonique d'AD-4 sans retour à la ligne final : même entrée, mêmes
octets, aucun horodatage d'exécution (seulement les dates des lignes des campagnes).

Choix là où AD-18 laisse une marge :

- une campagne incomplète ou discordante est publiée (``status: partial``, ``complete: false`` pour
  les modèles et pistes auxquels il manque des lignes) ; seules les entrées incohérentes refusent ;
- ``machines[]`` : ``id`` et ``label`` = ``blocking.machine`` du manifeste, qui doit figurer dans
  ``PUBLIC_MACHINES`` (libellé public choisi par ``$QUALITY_BENCH_MACHINE``) : sans la variable,
  le manifeste porte le nom d'hôte, qui ne doit pas être publié (AD-6), et l'export refuse ;
  ``gpu`` et ``os`` viennent de cette table ; ``ram_mib`` et ``vram_mib`` = plus grands totaux
  de ``memory.jsonl`` ;
- ``speed`` : ``decode_tok_s`` = tokens générés / temps de décodage cumulés des lignes retenues de
  la piste ; ``prefill_tok_s`` et ``load_time_ms`` = dernière chauffe du palier de référence
  (``REFERENCE_TIER``), commune aux deux pistes ;
- ``memory`` : base de départ = première valeur connue, pointes = maxima des segments de
  ``memory.jsonl`` ; ``model_size_mib`` et ``model_vram_mib`` = ``size`` et ``size_vram`` de la
  chauffe de référence ; ``validated_ctx`` = plus grand ``num_ctx`` d'une ligne de génération du
  modèle qui ne finit ni en ``context_exceeded`` ni en ``error`` (statut de génération ou, pour
  une ligne reclassée par ``grade``, statut noté) ;
- ``energy`` : ``unavailable`` sans aucune puissance relevée ; ``unvalidated`` (valeurs nulles) tant
  que la machine ne figure pas dans ``VALIDATED_ENERGY_MACHINES`` (validation d'admission
  consignée) ; ``measured`` sinon ;
- ``quality.usages.writing.status`` : ``final`` si la campagne est complète, la piste complète et le
  jugement présent, ``provisional`` sinon ;
- ``score`` et intervalles = ceux des unités communes du rapport (``null`` pour un modèle non
  classé : couverture sous le seuil) ; ``context_exceeded_rate`` = lignes ``context_exceeded``
  imputables au modèle / (lignes notées + ces lignes).

Codes de sortie : 0 ; 1 si les entrées sont incohérentes, un modèle est absent du registre, une
machine n'est pas déclarée publique, les campagnes ne partagent pas le même jeu ou l'écriture
échoue ; 2 si une configuration ou le registre est invalide.
Rien de privé (AD-6) : agrégats par modèle seulement.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import tomllib
from collections.abc import Mapping, Sequence
from importlib import metadata
from pathlib import Path
from typing import Any

from ..common import config, paths
from ..common.canonical import canonical_bytes
from ..common.jsonl import JsonlReadError, iter_jsonl
from ..common.logs import setup_logging
from ..common.registry import ModelInfo, load_models
from ..common.schemas import TRACKS, LegacyCampaignError, SchemaValidationError, validate
from .inputs import CampaignInputs, ReportError, load_inputs

logger = logging.getLogger(__name__)

COMMAND = "export-release"
SCHEMA_ID = "qb.results/1"
PACKAGE_NAME = "slm-quality-bench"
# Palier num_ctx de la chauffe qui donne le préremplissage, la durée de chargement et la taille
# du modèle publiés : le plus petit palier par défaut, hors du débordement en RAM partagée.
REFERENCE_TIER = 4096
# Machines dont la mesure de puissance du GPU est validée à l'admission (aucune pour l'instant :
# la RTX 3050 publie une puissance douteuse). Seules elles publient une énergie « measured ».
VALIDATED_ENERGY_MACHINES: frozenset[str] = frozenset()
# Machines publiables (AD-6) : libellé public du manifeste (``$QUALITY_BENCH_MACHINE``) → GPU et
# système publiés. Un libellé absent (nom d'hôte par défaut) refuse l'export.
PUBLIC_MACHINES: dict[str, dict[str, str | None]] = {
    "tour-rtx3050": {"gpu": "NVIDIA GeForce RTX 3050", "os": "Windows 11"},
}
_VERSION_RE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
_MIB = 1024 * 1024
_NO_CONTEXT_STATUSES = ("context_exceeded", "error")


class ReleaseError(RuntimeError):
    """Publication impossible (code 1) : rien n'est écrit."""


# -- Lecture des fichiers d'une campagne -----------------------------------------------------


def _lines(path: Path, schema: str, manifest: str, where: str) -> list[dict[str, Any]]:
    """Lignes validées de ``path`` produites par le manifeste ``manifest`` (fichier absent :
    aucune)."""
    kept = []
    try:
        for line_no, line in enumerate(iter_jsonl(path), start=1):
            try:
                name = validate(line)
            except SchemaValidationError as exc:
                raise ReleaseError(f"{where} ligne {line_no} : {exc}") from None
            if name != schema:
                raise ReleaseError(f"{where} ligne {line_no} : schéma {name} au lieu de {schema}")
            if line["manifest"] == manifest:
                kept.append(line)
    except JsonlReadError as exc:
        raise ReleaseError(str(exc)) from None
    return kept


def _generation_lines(inputs: CampaignInputs) -> list[dict[str, Any]]:
    """Lignes de génération retenues (clé attendue, manifeste concordant)."""
    lines = _lines(
        paths.generation_path(inputs.campaign),
        "qb.generation/1",
        inputs.generation_hash,
        "generation.jsonl",
    )
    return [line for line in lines if line["key"] in inputs.rows]


def _number(value: float | None) -> float | None:
    """``campaign.number`` (12 chiffres significatifs, ``None`` si indéfini) ; import tardif de
    ``campaign`` pour ne pas charger numpy et scipy hors de cette commande."""
    from .campaign import number

    return number(value)


def _max_known(values: Sequence[int | None]) -> int | None:
    known = [value for value in values if value is not None]
    return max(known) if known else None


def _first_known(values: Sequence[int | None]) -> int | None:
    return next((value for value in values if value is not None), None)


def _mib(value: int | None) -> float | None:
    return None if value is None else _number(value / _MIB)


# -- Agrégats par modèle ----------------------------------------------------------------------


def _decode_tok_s(lines: Sequence[Mapping[str, Any]]) -> float | None:
    tokens = 0
    nanoseconds = 0
    for line in lines:
        eval_ns = line["durations_ns"]["eval"]
        if line["status"] in ("ok", "truncated") and eval_ns > 0:
            tokens += line["tokens"]["completion"]
            nanoseconds += eval_ns
    return _number(tokens / (nanoseconds / 1e9)) if tokens and nanoseconds else None


def _reference_warmup(warmups: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    at_tier = [line for line in warmups if line["num_ctx"] == REFERENCE_TIER]
    return at_tier[-1] if at_tier else None


def _memory(
    memories: Sequence[Mapping[str, Any]],
    warmup: Mapping[str, Any] | None,
    generations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    contexts = [
        line["num_ctx"] for line in generations if line["status"] not in _NO_CONTEXT_STATUSES
    ]
    return {
        "ram_baseline_mib": _first_known([m["ram_baseline_mib"] for m in memories]),
        "ram_peak_mib": _max_known([m["ram_peak_mib"] for m in memories]),
        "vram_baseline_mib": _first_known([m["vram_baseline_mib"] for m in memories]),
        "vram_peak_mib": _max_known([m["vram_peak_mib"] for m in memories]),
        "model_size_mib": _mib(None if warmup is None else warmup["size"]),
        "model_vram_mib": _mib(None if warmup is None else warmup["size_vram"]),
        "validated_ctx": max(contexts) if contexts else None,
    }


def _energy(
    machine: str, memories: Sequence[Mapping[str, Any]], generations: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    powered = [
        m for m in memories if m["gpu_power_avg_w"] is not None and m["gpu_power_samples"] > 0
    ]
    result: dict[str, Any] = {
        "status": "unavailable",
        "gpu_power_avg_w": None,
        "gpu_wh_per_1k_tokens": None,
    }
    if not powered:
        return result
    result["status"] = "unvalidated"
    if machine not in VALIDATED_ENERGY_MACHINES:
        return result
    samples = sum(m["gpu_power_samples"] for m in powered)
    average = sum(m["gpu_power_avg_w"] * m["gpu_power_samples"] for m in powered) / samples
    energy = [m["gpu_energy_wh"] for m in memories if m["gpu_energy_wh"] is not None]
    tokens = sum(line["tokens"]["completion"] for line in generations)
    if not energy or not tokens:
        return result
    return {
        "status": "measured",
        "gpu_power_avg_w": _number(average),
        "gpu_wh_per_1k_tokens": _number(sum(energy) / (tokens / 1000)),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return _number(numerator / denominator) if denominator else None


def _scope_quality(entry: Mapping[str, Any]) -> dict[str, Any]:
    exceeded = entry["context_exceeded_model"]
    return {
        "score": entry["mean"],
        "ci_low": entry["ci_low"],
        "ci_high": entry["ci_high"],
        "n_units": entry["n"],
        "coverage": entry["coverage"],
        "truncation_rate": entry["truncation_rate"],
        "context_exceeded_rate": _rate(exceeded, entry["graded"] + exceeded),
    }


def _quality(track_block: Mapping[str, Any], model: str, *, writing_final: bool) -> dict[str, Any]:
    quality: dict[str, Any] = {"global": None, "usages": {}}
    for scope in track_block["scopes"]:
        entry = next(e for e in scope["models"] if e["model"] == model)
        record = _scope_quality(entry)
        if scope["usage"] is None:
            quality["global"] = record
        else:
            if scope["usage"] == "writing":
                record["status"] = "final" if writing_final else "provisional"
            quality["usages"][scope["usage"]] = record
    return quality


# -- Document ---------------------------------------------------------------------------------


def _bench_version() -> str:
    """Version du ``pyproject.toml`` du dépôt (source de vérité : une installation éditable non
    rafraîchie garde l'ancienne dans ses métadonnées), sinon celle du paquet installé."""
    pyproject = paths.REPO_ROOT / "pyproject.toml"
    if pyproject.is_file():
        try:
            project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ReleaseError(f"{pyproject} illisible : {exc}") from None
        if project.get("name") == PACKAGE_NAME and isinstance(project.get("version"), str):
            return project["version"]
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        raise ReleaseError(
            f"paquet {PACKAGE_NAME} non installé : version du banc inconnue"
        ) from None


def _campaign_record(inputs: CampaignInputs, dates: Sequence[str]) -> dict[str, Any]:
    return {
        "id": inputs.campaign,
        "generation_hash": inputs.generation_hash,
        "ollama_version": inputs.manifest["blocking"]["ollama_version"],
        "status": "partial" if inputs.completeness.has_issues else "complete",
        "first_line_at": min(dates) if dates else None,
        "last_line_at": max(dates) if dates else None,
    }


def campaign_results(
    inputs: CampaignInputs,
    machine_totals: dict[str, dict[str, int | None]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Entrée ``campaigns[]`` et lignes ``results[]`` d'une campagne ; complète
    ``machine_totals`` (RAM et VRAM totales relevées sur la machine de la campagne)."""
    campaign = inputs.campaign
    machine = inputs.manifest["blocking"]["machine"]
    if machine not in PUBLIC_MACHINES:
        raise ReleaseError(
            f"{campaign} : machine non déclarée publique (AD-6) ; lancer la campagne avec "
            "$env:QUALITY_BENCH_MACHINE défini à un libellé public et l'ajouter à "
            "PUBLIC_MACHINES (report/release.py)"
        )
    generation = _generation_lines(inputs)
    warmups = _lines(paths.warmups_path(campaign), "qb.warmup/1", inputs.generation_hash, "warmups")
    memories = _lines(paths.memory_path(campaign), "qb.memory/1", inputs.generation_hash, "memory")
    totals = machine_totals.setdefault(machine, {"ram_mib": None, "vram_mib": None})
    for field, source in (("ram_mib", "ram_total_mib"), ("vram_mib", "vram_total_mib")):
        totals[field] = _max_known([totals[field], *(m[source] for m in memories)])

    from .campaign import build_summary

    summary = build_summary(inputs)
    blocks = {block["track"]: block for block in summary["tracks"]}
    campaign_complete = not inputs.completeness.has_issues
    judged = inputs.judgment_hash is not None
    results = []
    for model in inputs.models:
        tag = model["tag"]
        mine_gen = [line for line in generation if line["model"] == tag]
        mine_mem = [m for m in memories if m["model"] == tag]
        warmup = _reference_warmup([w for w in warmups if w["model"] == tag])
        # Statut noté : une ligne reclassée par grade (prompt tronqué en silence) ne valide pas
        # son palier.
        validating = [g for g in mine_gen if inputs.rows[g["key"]].status != "context_exceeded"]
        memory = _memory(mine_mem, warmup, validating)
        energy = _energy(machine, mine_mem, mine_gen)
        speed_common = {
            "prefill_tok_s": None if warmup is None else _number(warmup["prefill_tok_s"]),
            "load_time_ms": None if warmup is None else _number(warmup["load_ns"] / 1e6),
        }
        for track in TRACKS:
            if track not in model["tracks"] or track not in blocks:
                continue
            expected = sum(1 for e in inputs.expected if e.model == tag and e.track == track)
            retained = sum(1 for r in inputs.rows.values() if r.model == tag and r.track == track)
            complete = expected == retained
            results.append(
                {
                    "model": tag,
                    "digest": model["digest"],
                    "machine": machine,
                    "campaign": campaign,
                    "track": track,
                    "complete": complete,
                    "quality": _quality(
                        blocks[track], tag, writing_final=complete and campaign_complete and judged
                    ),
                    "speed": {
                        "decode_tok_s": _decode_tok_s([g for g in mine_gen if g["track"] == track]),
                        **speed_common,
                    },
                    "memory": dict(memory),
                    "energy": dict(energy),
                }
            )
    dates = [line["created_at"] for line in generation]
    return _campaign_record(inputs, dates), results


def build_release(
    campaigns: Sequence[str], registry: Mapping[str, ModelInfo] | None = None
) -> dict[str, Any]:
    """Document ``qb.results/1`` des campagnes nommées (``ReleaseError``, ``ReportError``,
    ``config.ConfigError``)."""
    if not campaigns:
        raise ReleaseError("au moins une campagne attendue")
    if len(set(campaigns)) != len(campaigns):
        raise ReleaseError("campagne nommée deux fois")
    registry = load_models() if registry is None else registry
    loaded = [load_inputs(campaign, partial=True) for campaign in campaigns]
    sets = {(inputs.set_id, inputs.set_hash) for inputs in loaded}
    if len(sets) != 1:
        raise ReleaseError(
            "les campagnes ne partagent pas le même jeu : "
            + ", ".join(f"{inputs.campaign} ({inputs.set_id})" for inputs in loaded)
        )
    machine_totals: dict[str, dict[str, int | None]] = {}
    campaign_records: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    digests: dict[tuple[str, str], None] = {}
    for inputs in loaded:
        record, rows = campaign_results(inputs, machine_totals)
        campaign_records.append(record)
        results.extend(rows)
        for model in inputs.models:
            digests[(model["tag"], model["digest"])] = None
    missing = sorted({tag for tag, _ in digests if tag not in registry})
    if missing:
        raise ReleaseError(
            f"modèle(s) absent(s) du registre models.yaml : {', '.join(missing)} "
            "(ajouter une entrée qb.models/1 avant de publier)"
        )
    set_id, set_hash = next(iter(sets))
    return {
        "schema": SCHEMA_ID,
        "bench_version": _bench_version(),
        "set": {"id": set_id, "set_hash": set_hash},
        "campaigns": sorted(campaign_records, key=lambda c: c["id"]),
        "machines": [
            {
                "id": machine,
                "label": machine,
                "gpu": PUBLIC_MACHINES[machine]["gpu"],
                "vram_mib": totals["vram_mib"],
                "ram_mib": totals["ram_mib"],
                "os": PUBLIC_MACHINES[machine]["os"],
            }
            for machine, totals in sorted(machine_totals.items())
        ],
        "models": [
            {**registry[tag].as_record(), "digest": digest} for tag, digest in sorted(digests)
        ],
        "results": sorted(
            results, key=lambda r: (r["model"], r["machine"], r["campaign"], r["track"])
        ),
    }


def release_bytes(document: Mapping[str, Any]) -> bytes:
    """Octets du fichier publié : JSON canonique d'AD-4, sans retour à la ligne final (son
    ``sha256`` est celui du JSON canonique du document)."""
    return canonical_bytes(document)


def export_release(
    campaigns: Sequence[str], version: str, registry: Mapping[str, ModelInfo] | None = None
) -> Path:
    """Écrit le fichier de la release ``version`` ; rend son chemin. Rien n'est écrit en cas
    d'erreur ; un fichier existant est remplacé."""
    if not _VERSION_RE.fullmatch(version):
        raise ReleaseError(f"version invalide : {version!r} (SemVer X.Y.Z attendu)")
    target = paths.release_path(version)
    data = release_bytes(build_release(campaigns, registry))
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.tmp")
    try:
        with open(staging, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staging, target)
    finally:
        if staging.exists():
            staging.unlink()
    logger.info("Release %s écrite : %s (%d octets)", version, target, len(data))
    return target


# -- Ligne de commande ------------------------------------------------------------------------


def _version_argument(value: str) -> str:
    if not _VERSION_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"version SemVer X.Y.Z attendue, reçu {value!r}")
    return value


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--campaign", nargs="+", required=True, metavar="CAMPAGNE", help="campagnes à publier"
    )
    parser.add_argument(
        "--version",
        required=True,
        type=_version_argument,
        metavar="X.Y.Z",
        help="version SemVer de la release (dossier benchmarks/quality/releases/<version>/)",
    )


def _run(args: argparse.Namespace) -> int:
    setup_logging(COMMAND, None)
    try:
        export_release(args.campaign, args.version)
    except (config.ConfigError, LegacyCampaignError) as exc:
        logger.error("Configuration invalide, rien n'est écrit : %s", exc)
        return 2
    except (ReleaseError, ReportError, ValueError) as exc:
        logger.error("Publication refusée, rien n'est écrit : %s", exc)
        return 1
    except OSError as exc:
        logger.error("Écriture impossible, rien n'est publié : %s", exc)
        return 1
    return 0


EXPORT_RELEASE = (
    COMMAND,
    "Publie slm-quality-results.json (qb.results/1) depuis une ou plusieurs campagnes, sans "
    "réseau ni verrou",
    _configure,
    _run,
)
