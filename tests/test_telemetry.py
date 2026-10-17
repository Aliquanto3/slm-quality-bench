"""Télémétries coupées avant l'import d'une bibliothèque à télémétrie.

Version autonome du test de wavelocalai (``tests/unit/test_telemetry.py``, partie importeurs du
banc) : l'ordre est vérifié sur l'arbre syntaxique, les variables par un sous-processus.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from slm_quality_bench.common.telemetry import TELEMETRY_OPT_OUTS, disable_telemetry

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "slm_quality_bench"

# Racines des bibliothèques à télémétrie (ou qui en chargent une). Tout fichier du paquet qui
# en importe une figure dans TELEMETRY_IMPORTERS.
TELEMETRY_ROOTS = frozenset(
    {"huggingface_hub", "datasets", "transformers", "sentence_transformers"}
)

# Module → bibliothèques à télémétrie qu'il importe ; disable_telemetry() doit précéder la
# première de ces importations. La CLI (__main__.py) l'appelle en tête, avant tout import.
TELEMETRY_IMPORTERS: dict[str, tuple[str, ...]] = {
    "slm_quality_bench/questions/importers/remote.py": ("huggingface_hub",),
}
TELEMETRY_CALLERS = ("slm_quality_bench/__main__.py", *TELEMETRY_IMPORTERS)


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in TELEMETRY_OPT_OUTS}


def _imported_roots(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        return [node.module.split(".")[0]]
    return []


def _module_level_call_line(tree: ast.Module) -> int | None:
    return next(
        (
            node.lineno
            for node in tree.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "disable_telemetry"
        ),
        None,
    )


def test_disable_telemetry_sets_missing_and_keeps_existing(monkeypatch, tmp_path):
    for name in TELEMETRY_OPT_OUTS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")  # choix explicite conservé
    dotenv = tmp_path / ".env"
    dotenv.write_text("DO_NOT_TRACK=0\n", encoding="utf-8")  # réactivation par le .env

    disable_telemetry(dotenv)

    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "0"
    assert os.environ["DO_NOT_TRACK"] == "0"
    monkeypatch.delenv("HF_HUB_DISABLE_TELEMETRY")
    disable_telemetry(tmp_path / "absent.env")
    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


def test_every_telemetry_importer_is_listed():
    """Un module nouveau ou oublié qui importe une bibliothèque à télémétrie fait échouer la
    suite tant qu'il n'est pas protégé et listé dans TELEMETRY_IMPORTERS."""
    importers = {
        path.relative_to(ROOT).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "vendored" not in path.parts
        and any(
            TELEMETRY_ROOTS & set(_imported_roots(node))
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    }
    missing = sorted(importers - set(TELEMETRY_IMPORTERS))
    assert not missing, f"Modules à protéger par disable_telemetry() puis à lister : {missing}"


@pytest.mark.parametrize("relpath", sorted(TELEMETRY_IMPORTERS))
def test_disable_telemetry_precedes_library_import(relpath):
    """Dans chaque module, l'appel précède la première importation de la bibliothèque (y
    compris dans un try ou une fonction)."""
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    libraries = set(TELEMETRY_IMPORTERS[relpath])
    library_lines = [
        node.lineno for node in ast.walk(tree) if libraries & set(_imported_roots(node))
    ]
    call_line = _module_level_call_line(tree)
    assert library_lines, f"{relpath} n'importe plus {libraries} : mettre à jour la liste"
    assert call_line is not None, f"{relpath} n'appelle pas disable_telemetry()"
    assert call_line < min(library_lines)


@pytest.mark.parametrize("relpath", TELEMETRY_CALLERS)
def test_callers_import_the_local_copy(relpath):
    """L'appel vient de ``slm_quality_bench.common.telemetry``, jamais de wavelocalai."""
    tree = ast.parse((ROOT / relpath).read_text(encoding="utf-8"))
    sources = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "disable_telemetry" for alias in node.names)
    ]
    assert sources, f"{relpath} n'importe pas disable_telemetry"
    for node in sources:
        assert node.module == "slm_quality_bench.common.telemetry" or (
            node.level > 0 and (node.module or "").endswith("common.telemetry")
        ), f"{relpath} : import inattendu {node.module}"


def test_hf_telemetry_off_after_importer_import(tmp_path):
    """Hors du dépôt, sans opt-out dans l'environnement : l'import de l'importeur suffit à
    couper Hugging Face (``constants`` lu à l'import de ``huggingface_hub``)."""
    pytest.importorskip("huggingface_hub")
    code = (
        "import os\n"
        "import slm_quality_bench.questions.importers.remote\n"
        "from huggingface_hub import constants\n"
        "assert os.environ['HF_HUB_DISABLE_TELEMETRY'] == '1'\n"
        "assert constants.HF_HUB_DISABLE_TELEMETRY is True\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={**_clean_env(), "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
