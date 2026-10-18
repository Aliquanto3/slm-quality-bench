"""Registre des modèles (AD-18, ``qb.models/1``) : ``slm_quality_bench/models.yaml``.

``load_models(path)`` lit le registre avec le même idiome que ``config.load_pilot_settings`` :
clés fermées, valeurs vérifiées, ``ConfigError`` qui nomme le champ fautif. Une valeur inconnue
vaut ``None`` (jamais une clé omise) ; l'entrée la dit à vérifier dans ``sources[].note``.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import ConfigError, _reject_unknown, _require_mapping, read_yaml
from .paths import PACKAGE_DIR

SCHEMA_ID = "qb.models/1"
KNOWN_KEYS = ("name", "editor", "family", "moe", "params_total_b", "params_active_b")
_ENTRY_KEYS = {
    *KNOWN_KEYS,
    "context_length",
    "capabilities",
    "sources",
}
_SOURCE_KEYS = {"ref", "date", "note"}
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class ModelInfo:
    """Une entrée du registre, telle que publiée dans ``models[]`` (hors ``digest``)."""

    tag: str
    name: str
    editor: str
    family: str
    moe: bool
    params_total_b: float | None
    params_active_b: float | None
    context_length: int | None
    capabilities: tuple[str, ...]
    sources: tuple[dict[str, str], ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "editor": self.editor,
            "family": self.family,
            "moe": self.moe,
            "params_total_b": self.params_total_b,
            "params_active_b": self.params_active_b,
            "context_length": self.context_length,
            "capabilities": list(self.capabilities),
            "sources": [dict(source) for source in self.sources],
        }


def models_path() -> Path:
    """Registre versionné : ``slm_quality_bench/models.yaml``."""
    return PACKAGE_DIR / "models.yaml"


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where} : chaîne non vide attendue, reçu {value!r}")
    return value


def _billions(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ConfigError(f"{where} : nombre > 0 (milliards) ou null attendu, reçu {value!r}")
    return float(value)


def _context(value: Any, where: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{where} : entier ≥ 1 ou null attendu, reçu {value!r}")
    return value


def _capabilities(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{where} : liste non vide attendue")
    names = tuple(_text(item, f"{where}[]") for item in value)
    if len(set(names)) != len(names):
        raise ConfigError(f"{where} : capacité en double")
    return names


def _sources(value: Any, where: str) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{where} : au moins une source (fiche et date du relevé) attendue")
    sources = []
    for index, item in enumerate(value):
        here = f"{where}[{index}]"
        entry = _require_mapping(item, here)
        _reject_unknown(entry, _SOURCE_KEYS, here)
        for key in ("ref", "date"):
            if key not in entry:
                raise ConfigError(f"{here}.{key} : obligatoire")
        source = {"ref": _text(entry["ref"], f"{here}.ref")}
        date = entry["date"]
        if not isinstance(date, str) or not _DATE_RE.fullmatch(date):
            raise ConfigError(f"{here}.date : date AAAA-MM-JJ (chaîne) attendue, reçu {date!r}")
        source["date"] = date
        if "note" in entry:
            source["note"] = _text(entry["note"], f"{here}.note")
        sources.append(source)
    return tuple(sources)


def _entry(tag: str, raw: Any) -> ModelInfo:
    where = f"models.{tag}"
    value = _require_mapping(raw, where)
    _reject_unknown(value, _ENTRY_KEYS, where)
    for key in sorted(_ENTRY_KEYS):
        if key not in value:
            raise ConfigError(f"{where}.{key} : obligatoire (null si inconnu)")
    if not isinstance(value["moe"], bool):
        raise ConfigError(f"{where}.moe : booléen attendu, reçu {value['moe']!r}")
    total = _billions(value["params_total_b"], f"{where}.params_total_b")
    active = _billions(value["params_active_b"], f"{where}.params_active_b")
    if total is not None and active is not None and active > total:
        raise ConfigError(f"{where} : params_active_b ({active}) supérieur à params_total_b")
    return ModelInfo(
        tag=tag,
        name=_text(value["name"], f"{where}.name"),
        editor=_text(value["editor"], f"{where}.editor"),
        family=_text(value["family"], f"{where}.family"),
        moe=value["moe"],
        params_total_b=total,
        params_active_b=active,
        context_length=_context(value["context_length"], f"{where}.context_length"),
        capabilities=_capabilities(value["capabilities"], f"{where}.capabilities"),
        sources=_sources(value["sources"], f"{where}.sources"),
    )


def load_models(path: str | os.PathLike[str] | None = None) -> dict[str, ModelInfo]:
    """Lit le registre (par défaut ``slm_quality_bench/models.yaml``) : tag → ``ModelInfo``.

    ``ConfigError`` si le fichier est absent, d'un autre schéma, ou si une entrée est invalide."""
    path = Path(path) if path is not None else models_path()
    if not path.exists():
        raise ConfigError(f"registre des modèles absent : {path}")
    raw = _require_mapping(read_yaml(path), str(path))
    _reject_unknown(raw, {"schema", "models"}, str(path))
    if raw.get("schema") != SCHEMA_ID:
        raise ConfigError(f"{path} : schema « {SCHEMA_ID} » attendu, reçu {raw.get('schema')!r}")
    models = _require_mapping(raw.get("models"), "models")
    if not models:
        raise ConfigError("models : au moins un modèle attendu")
    return {str(tag): _entry(str(tag), entry) for tag, entry in models.items()}
