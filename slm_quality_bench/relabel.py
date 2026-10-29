"""Sous-commande ``relabel-machine --campaign <c> --label <libellé> [--dry-run]`` : donne après
coup le libellé public de la machine à une campagne lancée sans ``$QUALITY_BENCH_MACHINE``
(son manifeste porte alors le nom d'hôte, que ``export-release`` refuse de publier, AD-6).

``blocking.machine`` entre dans l'empreinte ``blocking_hash`` que portent les lignes ; changer le
libellé impose donc de réécrire, ensemble et sans toucher au reste :

- ``manifest.json`` : ``blocking.machine`` ; ``informative.relabels`` reçoit l'opération (ancien
  libellé haché seulement, jamais en clair) ;
- ``generation.jsonl``, ``warmups.jsonl``, ``memory.jsonl`` : champ ``manifest`` ;
- ``grading.jsonl`` : ``generation_manifest`` et, s'il n'est pas nul, ``judgment_manifest`` ;
- pour chaque ``judgment-<juge>/`` de cette génération : ``manifest.json`` (``blocking.machine``,
  ``blocking.generation_manifest``, ``informative.relabels``), ``judgment.jsonl`` et
  ``batches.jsonl`` (champ ``manifest``).

Les exports déjà écrits (``benchmarks/quality/<c>/``, rapports du pilote et de calibration)
portent l'ancienne empreinte : ``report`` (et les autres) les réécrivent. Les reprises de
``generate`` et ``judge`` comparent ``blocking.machine`` au libellé de l'environnement : lancer
ensuite avec ``$env:QUALITY_BENCH_MACHINE`` défini à ce libellé.

Refus (code 1, rien n'est écrit) : verrou de génération ou de jugement tenu, libellé identique à
l'actuel, fichier incohérent (ligne d'un autre manifeste, ligne illisible ou fragment final,
schéma invalide), sauvegarde ``.avant-relabel`` déjà présente. Tout est préparé dans des fichiers
temporaires, sauvegardé en ``<fichier>.avant-relabel``, puis remplacé ; un échec en cours de
remplacement restaure les fichiers déjà remplacés.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import json
import logging
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .common import paths
from .common.canonical import canonical_bytes, pretty_bytes, sha256_hex, utc_now
from .common.locks import FileLock, LockBusyError
from .common.logs import setup_logging
from .common.manifest import blocking_hash, clean_machine_label
from .common.schemas import SchemaValidationError, validate

logger = logging.getLogger(__name__)

COMMAND = "relabel-machine"
LOG_COMMAND = "relabel"
BACKUP_SUFFIX = ".avant-relabel"
TMP_SUFFIX = ".relabel.tmp"

# Point d'injection des tests : horodatage UTC de l'opération.
NOW: Callable[[], str] = utc_now


class RelabelError(RuntimeError):
    """Relabel refusé : rien n'a été écrit."""


@dataclass
class Change:
    path: Path
    data: bytes
    lines: int | None  # None pour un manifeste


@dataclass
class Plan:
    changes: list[Change] = field(default_factory=list)
    locks: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _read_json(path: Path, what: str) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate(manifest)
    except (OSError, ValueError, SchemaValidationError) as exc:
        raise RelabelError(f"{what} illisible ou invalide ({type(exc).__name__})") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != "qb.manifest/1":
        raise RelabelError(f"{what} : pas un manifeste qb.manifest/1")
    return manifest


def _relabeled_manifest(manifest: dict[str, Any], label: str, now: str) -> dict[str, Any]:
    """Copie du manifeste au nouveau libellé, avec l'opération consignée (ancien libellé haché)."""
    new = copy.deepcopy(manifest)
    new["blocking"]["machine"] = label
    informative = new["informative"]
    informative["relabels"] = [
        *informative.get("relabels", []),
        {"from_hash": sha256_hex(manifest["blocking"]["machine"]), "to": label, "at": now},
    ]
    return new


def _rewritten_lines(
    path: Path, what: str, schema: str, fields: dict[str, Callable[[Any], Any]]
) -> Change | None:
    """Lignes de ``path`` dont chaque champ de ``fields`` est transformé (la fonction lève
    ``RelabelError`` pour une valeur étrangère) ; ``None`` si le fichier n'existe pas."""
    if not path.exists():
        return None
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise RelabelError(
            f"{what} : fragment final sans retour à la ligne (écriture interrompue) ; relancer "
            "la commande qui l'écrit pour le tronquer, puis recommencer"
        )
    out = bytearray()
    count = 0
    for line_no, chunk in enumerate(raw.split(b"\n")[:-1], start=1):
        where = f"{what} ligne {line_no}"
        try:
            record = json.loads(chunk.decode("utf-8"))
        except ValueError:
            raise RelabelError(f"{where} : ligne illisible") from None
        if not isinstance(record, dict):
            raise RelabelError(f"{where} : pas un objet JSON")
        try:
            name = validate(record)
        except SchemaValidationError as exc:
            raise RelabelError(f"{where} : {exc}") from None
        if name != schema:
            raise RelabelError(f"{where} : schéma {name} au lieu de {schema}")
        for field_name, convert in fields.items():
            try:
                record[field_name] = convert(record[field_name])
            except RelabelError as exc:
                raise RelabelError(f"{where} : {field_name} {exc}") from None
        out += canonical_bytes(record) + b"\n"
        count += 1
    return Change(path, bytes(out), count)


def _expect(old: Any, new: Any, allow_null: bool = False) -> Callable[[Any], Any]:
    def convert(value: Any) -> Any:
        if allow_null and value is None:
            return None
        if value != old:
            raise RelabelError("d'un autre manifeste que le manifeste courant")
        return new

    return convert


def _probe_lock(lock: Path, what: str) -> None:
    """``RelabelError`` si ``lock`` est tenu (sonde non bloquante, relâchée aussitôt)."""
    if not lock.exists():
        return
    try:
        with FileLock(lock):
            pass
    except LockBusyError as exc:
        raise RelabelError(f"{what} en cours ({exc}) : relancer une fois la phase finie") from None


def build_plan(campaign: str, label: str, *, probe: bool = True) -> Plan:
    """Prépare toutes les réécritures en mémoire (rien n'est écrit) ; ``RelabelError`` au
    premier fichier incohérent."""
    now = NOW()
    manifest_path = paths.generation_manifest_path(campaign)
    if not manifest_path.exists():
        raise RelabelError(f"manifeste de génération absent : {manifest_path}")
    if probe:
        _probe_lock(paths.generation_lock_path(campaign), "génération")
    manifest = _read_json(manifest_path, "manifeste de génération")
    if manifest["phase"] != "generation" or manifest["campaign"] != campaign:
        raise RelabelError(f"manifest.json n'est pas le manifeste de génération de {campaign}")
    if manifest["blocking"]["machine"] == label:
        raise RelabelError(f"la campagne porte déjà le libellé {label!r}")
    new_manifest = _relabeled_manifest(manifest, label, now)
    old_hash, new_hash = blocking_hash(manifest), blocking_hash(new_manifest)

    plan = Plan()
    plan.locks.append(paths.generation_lock_path(campaign))
    plan.changes.append(Change(manifest_path, pretty_bytes(new_manifest), None))
    swap_generation = _expect(old_hash, new_hash)
    for path, schema, field_name in (
        (paths.generation_path(campaign), "qb.generation/1", "manifest"),
        (paths.warmups_path(campaign), "qb.warmup/1", "manifest"),
        (paths.memory_path(campaign), "qb.memory/1", "manifest"),
    ):
        change = _rewritten_lines(path, path.name, schema, {field_name: swap_generation})
        if change is not None:
            plan.changes.append(change)

    # Jugements de cette génération : empreinte de leur manifeste ancienne → nouvelle.
    judgment_hashes: dict[str, str] = {}
    campaign_dir = paths.campaign_dir(campaign)
    for directory in sorted(campaign_dir.glob("judgment-*")):
        if not directory.is_dir():
            continue
        judge = directory.name.removeprefix("judgment-")
        where = f"judgment-{judge}"
        if probe:
            _probe_lock(directory / "judgment.lock", f"jugement {judge}")
        plan.locks.append(directory / "judgment.lock")
        path = directory / "manifest.json"
        if not path.exists():
            if (directory / "judgment.jsonl").exists() or (directory / "batches.jsonl").exists():
                raise RelabelError(f"{where} : lignes de jugement sans manifest.json")
            continue
        judgment = _read_json(path, f"manifeste de jugement {judge}")
        if judgment["phase"] != "judgment" or judgment["blocking"]["judge"]["id"] != judge:
            raise RelabelError(f"{where} : manifeste d'un autre juge ou d'une autre phase")
        if judgment["blocking"]["generation_manifest"] != old_hash:
            # Jugement d'une autre génération : déjà écarté partout, laissé tel quel.
            plan.skipped.append(f"{where} (jugement d'un autre manifeste de génération)")
            continue
        new_judgment = _relabeled_manifest(judgment, label, now)
        new_judgment["blocking"]["generation_manifest"] = new_hash
        judgment_hashes[blocking_hash(judgment)] = blocking_hash(new_judgment)
        plan.changes.append(Change(path, pretty_bytes(new_judgment), None))
        swap = _expect(blocking_hash(judgment), blocking_hash(new_judgment))
        for name, schema in (("judgment.jsonl", "qb.judgment/1"), ("batches.jsonl", "qb.batch/1")):
            change = _rewritten_lines(
                directory / name, f"{where}/{name}", schema, {"manifest": swap}
            )
            if change is not None:
                plan.changes.append(change)

    def swap_judgment(value: Any) -> Any:
        if value not in judgment_hashes:
            raise RelabelError("ne désigne aucun manifeste de jugement de cette génération")
        return judgment_hashes[value]

    change = _rewritten_lines(
        paths.grading_path(campaign),
        "grading.jsonl",
        "qb.grading/1",
        {
            "generation_manifest": swap_generation,
            "judgment_manifest": lambda v: None if v is None else swap_judgment(v),
        },
    )
    if change is not None:
        plan.changes.append(change)

    for item in plan.changes:
        backup = item.path.with_name(item.path.name + BACKUP_SUFFIX)
        if backup.exists():
            raise RelabelError(
                f"sauvegarde déjà présente : {backup.name} (relabel antérieur ? la déplacer ou "
                "la supprimer d'abord)"
            )
    return plan


def _fsync_write(path: Path, data: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def apply_plan(plan: Plan) -> None:
    """Écrit tout dans des fichiers temporaires, sauvegarde les originaux, puis remplace ; un
    échec restaure les fichiers déjà remplacés."""
    tmps: list[tuple[Change, Path, Path]] = []
    replaced: list[tuple[Path, Path]] = []
    try:
        for change in plan.changes:
            tmp = change.path.with_name(change.path.name + TMP_SUFFIX)
            _fsync_write(tmp, change.data)
            tmps.append((change, tmp, change.path.with_name(change.path.name + BACKUP_SUFFIX)))
        for change, _tmp, backup in tmps:
            shutil.copy2(change.path, backup)
        for change, tmp, backup in tmps:
            os.replace(tmp, change.path)
            replaced.append((change.path, backup))
    except BaseException:
        for path, backup in replaced:
            restore = path.with_name(path.name + TMP_SUFFIX)
            shutil.copy2(backup, restore)
            os.replace(restore, path)
        raise
    finally:
        for _change, tmp, _backup in tmps:
            with contextlib.suppress(OSError):
                tmp.unlink()


@contextlib.contextmanager
def _held(locks: list[Path]) -> Iterator[None]:
    """Verrous de génération et de jugement existants, tenus pendant la réécriture."""
    with contextlib.ExitStack() as stack:
        for lock in locks:
            if lock.exists():
                try:
                    stack.enter_context(FileLock(lock))
                except LockBusyError as exc:
                    raise RelabelError(f"phase en cours ({exc})") from None
        yield


def relabel(campaign: str, label: str, *, dry_run: bool = False) -> Plan:
    """Relabel d'une campagne ; ``RelabelError`` si refusé. Rend le plan appliqué (ou, en
    ``dry_run``, le plan seul)."""
    label = clean_machine_label(label)
    if not label:
        raise RelabelError("libellé vide")
    plan = build_plan(campaign, label)
    if dry_run:
        return plan
    with _held(plan.locks):
        # Plan recalculé sous verrou : rien n'a pu changer entre la lecture et la réécriture.
        plan = build_plan(campaign, label, probe=False)
        apply_plan(plan)
    return plan


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign", required=True, help="identifiant de la campagne")
    parser.add_argument(
        "--label",
        required=True,
        help="libellé public de la machine (celui de $QUALITY_BENCH_MACHINE, par exemple "
        "tour-rtx3050)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="liste les fichiers et le nombre de lignes concernés, sans rien écrire",
    )


def _run(args: argparse.Namespace) -> int:
    label = clean_machine_label(args.label)
    try:
        log_file = None if args.dry_run else paths.log_path(args.campaign, LOG_COMMAND)
        paths.campaign_dir(args.campaign)
    except ValueError as exc:
        setup_logging(LOG_COMMAND, None)
        logger.error("%s", exc)
        return 2
    setup_logging(LOG_COMMAND, log_file)
    if not label:
        logger.error("Libellé vide : donner le libellé public de la machine")
        return 2
    if not paths.campaign_dir(args.campaign).is_dir():
        logger.error("Campagne %s absente : %s", args.campaign, paths.campaign_dir(args.campaign))
        return 1
    try:
        plan = relabel(args.campaign, label, dry_run=args.dry_run)
    except RelabelError as exc:
        logger.error("Relabel refusé, rien n'est écrit : %s", exc)
        return 1
    except OSError as exc:
        logger.error(
            "Relabel échoué (%s) : fichiers restaurés si le remplacement avait commencé", exc
        )
        return 1
    verb = "à réécrire" if args.dry_run else "réécrit"
    for change in plan.changes:
        size = "manifeste" if change.lines is None else f"{change.lines} ligne(s)"
        logger.info(
            "%s %s : %s", change.path.relative_to(paths.campaign_dir(args.campaign)), verb, size
        )
    for item in plan.skipped:
        logger.warning("%s : laissé tel quel", item)
    total = sum(change.lines or 0 for change in plan.changes)
    if args.dry_run:
        logger.info(
            "Simulation : %d fichier(s), %d ligne(s) concernés vers le libellé %s ; rien écrit",
            len(plan.changes),
            total,
            label,
        )
    else:
        logger.info(
            "Campagne %s : libellé de machine changé en %s, %d fichier(s), %d ligne(s) ; "
            "sauvegardes *%s ; relancer report puis export-release, et définir "
            "$env:QUALITY_BENCH_MACHINE=%s pour toute reprise de generate ou judge",
            args.campaign,
            label,
            len(plan.changes),
            total,
            BACKUP_SUFFIX,
            label,
        )
    return 0


RELABEL_MACHINE = (
    COMMAND,
    "Donne après coup le libellé public de la machine à une campagne (réécrit manifestes et "
    "empreintes, avec sauvegardes) ; --dry-run n'écrit rien",
    _configure,
    _run,
)
