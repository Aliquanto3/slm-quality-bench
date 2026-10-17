"""Sous-commande ``precheck`` : contrôles d'avant campagne en lecture seule, sur un jeu
synthétique et un Ollama simulé (aucun modèle, aucun GPU)."""

from __future__ import annotations

import pytest

from slm_quality_bench.__main__ import main
from slm_quality_bench.common import paths
from slm_quality_bench.grading import nlp
from slm_quality_bench.precheck import EXPECTED_OLLAMA_VERSION, run_checks

from .test_generate_command import CAMPAIGN, _reset_logging, env  # noqa: F401


@pytest.fixture
def ready(env, monkeypatch, tmp_path):  # noqa: F811
    """Tout est en place : données, NLTK, fichiers de wavelocalai, rejeu de même jeu."""
    old_bench = tmp_path / "ancien.json"
    catalog = tmp_path / "catalogue.json"
    old_bench.write_text("{}", encoding="utf-8")
    catalog.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(paths.OLD_BENCH_ENV, str(old_bench))
    monkeypatch.setenv(paths.CATALOG_ENV, str(catalog))
    monkeypatch.setattr(nlp, "missing_resources", lambda: [])
    config_text = (env["config_dir"] / f"{CAMPAIGN}.yaml").read_text(encoding="utf-8")
    (env["config_dir"] / f"{CAMPAIGN}-replay.yaml").write_text(config_text, encoding="utf-8")
    env["replay"] = f"{CAMPAIGN}-replay"
    return env


def _checks(env, **kwargs):
    return run_checks(CAMPAIGN, env.get("replay"), "http://127.0.0.1:11434", **kwargs)


def test_everything_ready_has_no_failure_and_writes_nothing(ready):
    before = sorted(paths.data_root().rglob("*"))
    assert _checks(ready) == []
    assert sorted(paths.data_root().rglob("*")) == before  # lecture seule
    assert EXPECTED_OLLAMA_VERSION == "0.40.2"


def test_cli_exit_codes(ready, capsys):
    argv = ["precheck", "--campaign", CAMPAIGN, "--replay", ready["replay"]]
    assert main(argv) == 0
    ready["fake"].version = "0.40.3"
    assert main(argv) == 2
    assert "0.40.3" in capsys.readouterr().err


def test_wrong_ollama_version_is_refused_unless_chosen(ready):
    ready["fake"].version = "0.41.0"
    failures = _checks(ready)
    assert len(failures) == 1 and "0.41.0" in failures[0]
    assert _checks(ready, expected_version="0.41.0") == []
    assert _checks(ready, expected_version=None) == []


def test_missing_nltk_is_refused_with_the_fetch_command(ready, monkeypatch):
    monkeypatch.setattr(nlp, "missing_resources", lambda: ["tokenizers/punkt"])
    failures = _checks(ready)
    assert len(failures) == 1 and "fetch-nltk" in failures[0]


def test_data_root_must_be_defined_and_exist(ready, monkeypatch, tmp_path):
    monkeypatch.delenv(paths.DATA_ENV)
    assert any("n'est pas défini" in failure for failure in _checks(ready))
    monkeypatch.setenv(paths.DATA_ENV, str(tmp_path / "absent"))
    assert any("dossier absent" in failure for failure in _checks(ready))


def test_missing_wavelocalai_files_name_the_variables(ready, monkeypatch, tmp_path):
    monkeypatch.setenv(paths.OLD_BENCH_ENV, str(tmp_path / "nulle-part.json"))
    failures = _checks(ready)
    assert len(failures) == 1
    assert paths.OLD_BENCH_ENV in failures[0]


def test_missing_set_and_missing_model_are_listed_together(ready):
    paths.set_tracks_path("small-gen").unlink()
    ready["fake"].models.pop("m-plain:1b")
    failures = _checks(ready)
    assert any("jeu small-gen" in failure for failure in failures)
    assert any("m-plain:1b" in failure for failure in failures)


def test_unreachable_ollama_is_a_refusal(ready, monkeypatch):
    from slm_quality_bench.generation import commands
    from slm_quality_bench.ollama.client import OllamaClient

    monkeypatch.setattr(commands, "make_client", lambda url: OllamaClient("http://127.0.0.1:9"))
    failures = _checks(ready)
    assert failures and "Ollama joignable" in failures[0]


def test_missing_campaign_configuration_is_refused(ready):
    (ready["config_dir"] / f"{CAMPAIGN}-replay.yaml").unlink()
    failures = _checks(ready)
    assert any(f"{CAMPAIGN}-replay" in failure for failure in failures)
