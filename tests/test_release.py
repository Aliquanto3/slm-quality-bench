"""Registre des modèles (``qb.models/1``) et commande ``export-release`` (AD-18, CAP-10) sur une
petite campagne synthétique : schéma ``qb.results/1``, octets identiques, rien de privé,
campagne partielle, énergie non validée."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from slm_quality_bench.common import config, paths
from slm_quality_bench.common.canonical import sha256_bytes, sha256_hex
from slm_quality_bench.common.jsonl import rewrite_jsonl
from slm_quality_bench.common.registry import ModelInfo, load_models
from slm_quality_bench.common.schemas import validate
from slm_quality_bench.report import release

from .report_factories import CAMPAIGN, SECRET_OUTPUT, SECRET_QUESTION, make_campaign

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "schemas" / "qb.results-1.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    from slm_quality_bench.common.logs import setup_logging

    setup_logging("test", None)


def _registry(n: int = 3) -> dict[str, ModelInfo]:
    return {
        f"model-{i}:4b": ModelInfo(
            tag=f"model-{i}:4b",
            name=f"Modèle {i}",
            editor="Testeurs",
            family="qwen",
            moe=bool(i % 2),
            params_total_b=4.0,
            params_active_b=None,
            context_length=131072,
            capabilities=("chat", "tools"),
            sources=({"ref": "https://exemple.test/fiche", "date": "2026-10-18"},),
        )
        for i in range(n)
    }


def _problems(document) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}"
        for e in VALIDATOR.iter_errors(document)
    ]


def _add_measures(synthetic, *, power: bool = True) -> None:
    """Débit, chauffes et mémoire de la campagne synthétique (modèles 0 à 2)."""
    for line in synthetic.generation:
        line["tokens"]["completion"] = 100
        line["durations_ns"]["eval"] = 2_000_000_000  # 50 tok/s
        line["num_ctx"] = 4096
    synthetic.write_generation()
    warmups, memories = [], []
    for index, tag in enumerate(synthetic.models):
        for count, tier in enumerate((4096, 8192)):
            warmups.append(
                {
                    "schema": "qb.warmup/1",
                    "key": f"{CAMPAIGN}|{tag}|{tier}|{count}",
                    "manifest": synthetic.generation_hash,
                    "campaign": CAMPAIGN,
                    "model": tag,
                    "num_ctx": tier,
                    "prompt_tokens": tier // 4,
                    "size": (2000 + index) * 1024 * 1024 * (count + 1),
                    "size_vram": 1000 * 1024 * 1024,
                    "prefill_tok_s": 400.0 / (count + 1),
                    "load_ns": 1_500_000_000 * (count + 1),
                    "created_at": "2026-10-15T08:12:03Z",
                }
            )
        for segment in range(2):
            memories.append(
                {
                    "schema": "qb.memory/1",
                    "key": f"{CAMPAIGN}|{tag}|{segment}",
                    "manifest": synthetic.generation_hash,
                    "campaign": CAMPAIGN,
                    "model": tag,
                    "samples": 10,
                    "interval_s": 1.0,
                    "ram_total_mib": 32768,
                    "ram_baseline_mib": 9000 if segment == 0 else None,
                    "ram_peak_mib": 10000 + 100 * segment,
                    "vram_total_mib": 8192,
                    "vram_baseline_mib": 400 if segment == 0 else None,
                    "vram_peak_mib": 3000 + 10 * segment,
                    "tiers": [],
                    "gpu_power_source": "power.draw" if power else None,
                    "gpu_power_avg_w": 40.0 if power else None,
                    "gpu_power_max_w": 60.0 if power else None,
                    "gpu_power_samples": 10 if power else 0,
                    "gpu_energy_wh": 0.5 if power else None,
                    "created_at": "2026-10-15T08:12:03Z",
                }
            )
    for record in (*warmups, *memories):
        validate(record)
    rewrite_jsonl(paths.warmups_path(CAMPAIGN), warmups)
    rewrite_jsonl(paths.memory_path(CAMPAIGN), memories)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    synthetic = make_campaign(tmp_path, monkeypatch, small=True)
    _add_measures(synthetic)
    return synthetic


def _export(registry=None) -> tuple[Path, dict]:
    target = release.export_release([CAMPAIGN], "1.2.3", registry or _registry())
    return target, json.loads(target.read_text(encoding="utf-8"))


# -- Registre ---------------------------------------------------------------------------------


def test_shipped_registry_covers_the_full_campaign_and_the_candidates():
    registry = load_models()
    pilot = config.load_pilot_settings(paths.pilot_settings_path())
    candidates = [
        m["tag"]
        for m in config.load_campaign(paths.campaign_config_path("admission-20261018")).generation[
            "models"
        ]
    ]
    assert len(candidates) == 2
    missing = [tag for tag in (*pilot.full_models, *candidates) if tag not in registry]
    assert missing == []
    for tag in candidates:  # contexte relevé par ollama show sur la tour, cité dans sources
        assert registry[tag].context_length is not None
        assert any(s["ref"].startswith("ollama show") for s in registry[tag].sources)


def test_shipped_registry_families_match_the_campaign_configuration():
    registry = load_models()
    for name in ("full-20261018", "admission-20261018", "admission-20261026", "bonsai2-20261023"):
        for model in config.load_campaign(paths.campaign_config_path(name)).generation["models"]:
            assert registry[model["tag"]].family == model["family"], model["tag"]


def _valid_yaml() -> dict:
    return {
        "schema": "qb.models/1",
        "models": {
            "a:1b": {
                "name": "A",
                "editor": "E",
                "family": "f",
                "moe": False,
                "params_total_b": 1.0,
                "params_active_b": None,
                "context_length": None,
                "capabilities": ["chat"],
                "sources": [{"ref": "x", "date": "2026-10-18"}],
            }
        },
    }


def _write_registry(tmp_path, document) -> Path:
    import yaml

    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


def test_registry_loader_accepts_null_unknowns(tmp_path):
    registry = load_models(_write_registry(tmp_path, _valid_yaml()))
    info = registry["a:1b"]
    assert info.params_active_b is None and info.context_length is None
    assert info.as_record()["capabilities"] == ["chat"]


def _drop(entry, key):
    del entry[key]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema="qb.models/2"),
        lambda d: d.update(extra=1),
        lambda d: d["models"].clear(),
        lambda d: _drop(d["models"]["a:1b"], "context_length"),  # clé omise (null attendu)
        lambda d: d["models"]["a:1b"].update(unknown=1),
        lambda d: d["models"]["a:1b"].update(moe="oui"),
        lambda d: d["models"]["a:1b"].update(params_total_b=-1),
        lambda d: d["models"]["a:1b"].update(params_total_b="1B"),
        lambda d: d["models"]["a:1b"].update(params_active_b=2.0),  # actifs > total
        lambda d: d["models"]["a:1b"].update(context_length=0),
        lambda d: d["models"]["a:1b"].update(capabilities=[]),
        lambda d: d["models"]["a:1b"].update(capabilities=["chat", "chat"]),
        lambda d: d["models"]["a:1b"].update(family=""),
        lambda d: d["models"]["a:1b"].update(sources=[]),
        lambda d: d["models"]["a:1b"].update(sources=[{"ref": "x"}]),  # date du relevé absente
        lambda d: d["models"]["a:1b"].update(sources=[{"ref": "x", "date": "hier"}]),
        lambda d: d["models"]["a:1b"].update(sources=[{"ref": "x", "date": "2026-10-18", "z": 1}]),
    ],
)
def test_registry_loader_refuses_an_invalid_entry(tmp_path, mutate):
    document = _valid_yaml()
    mutate(document)
    with pytest.raises(config.ConfigError):
        load_models(_write_registry(tmp_path, document))


def test_registry_loader_refuses_a_missing_file(tmp_path):
    with pytest.raises(config.ConfigError):
        load_models(tmp_path / "absent.yaml")


# -- Export -----------------------------------------------------------------------------------


def test_release_matches_the_schema_and_carries_the_measures(campaign):
    target, document = _export()
    assert target == paths.release_path("1.2.3")
    assert target.parts[-3:] == ("releases", "1.2.3", "slm-quality-results.json")
    assert _problems(document) == []
    assert document["schema"] == "qb.results/1"
    assert document["bench_version"] == "0.1.0"
    assert document["set"] == {
        "id": campaign.manifest["blocking"]["set"]["id"],
        "set_hash": campaign.manifest["blocking"]["set"]["hash"],
    }
    assert document["campaigns"] == [
        {
            "id": CAMPAIGN,
            "generation_hash": campaign.generation_hash,
            "ollama_version": "0.40.2",
            "status": "complete",
            "first_line_at": "2026-10-15T08:12:03Z",
            "last_line_at": "2026-10-15T08:12:03Z",
        }
    ]
    assert document["machines"] == [
        {
            "id": "tour-rtx3050",
            "label": "tour-rtx3050",
            "gpu": "NVIDIA GeForce RTX 3050",
            "vram_mib": 8192,
            "ram_mib": 32768,
            "os": "Windows 11",
        }
    ]
    models = document["models"]
    assert [m["tag"] for m in models] == campaign.models
    assert models[0]["digest"] == f"sha256:{0:064d}"
    assert models[0]["name"] == "Modèle 0" and models[0]["params_active_b"] is None
    # model-2 ne suit que think_off : 3 modèles, 5 pistes.
    assert [(r["model"], r["track"]) for r in document["results"]] == [
        ("model-0:4b", "think_off"),
        ("model-0:4b", "think_on"),
        ("model-1:4b", "think_off"),
        ("model-1:4b", "think_on"),
        ("model-2:4b", "think_off"),
    ]
    first = document["results"][0]
    assert first["complete"] is True
    assert first["speed"] == {"decode_tok_s": 50.0, "prefill_tok_s": 400.0, "load_time_ms": 1500.0}
    assert first["memory"] == {
        "ram_baseline_mib": 9000,
        "ram_peak_mib": 10100,
        "vram_baseline_mib": 400,
        "vram_peak_mib": 3010,
        "model_size_mib": 2000.0,
        "model_vram_mib": 1000.0,
        "validated_ctx": 4096,
    }
    quality = first["quality"]
    assert set(quality["usages"]) == {"reasoning"}
    scope = quality["global"]
    assert 0 <= scope["ci_low"] <= scope["score"] <= scope["ci_high"] <= 1
    assert scope["n_units"] > 0 and scope["coverage"] == 1.0
    assert scope["truncation_rate"] == 0.0 and scope["context_exceeded_rate"] == 0.0
    assert quality["usages"]["reasoning"] == scope  # le jeu ne compte que du raisonnement


def test_writing_usage_is_final_only_when_everything_is_judged(tmp_path, monkeypatch):
    synthetic = make_campaign(tmp_path, monkeypatch)
    _add_measures(synthetic)
    _, document = _export()
    assert _problems(document) == []
    writing = document["results"][0]["quality"]["usages"]["writing"]
    assert writing["status"] == "final"
    # Un jugement qui manque rend la rédaction provisoire.
    lines = [line for line in synthetic.grading if "writing/" not in line["key"]]
    synthetic.write_grading(lines)
    _, document = _export()
    assert _problems(document) == []
    assert document["campaigns"][0]["status"] == "partial"
    assert all(
        r["quality"]["usages"].get("writing", {"status": "provisional"})["status"] == "provisional"
        for r in document["results"]
    )


def test_energy_is_unvalidated_unavailable_or_measured(tmp_path, monkeypatch):
    synthetic = make_campaign(tmp_path, monkeypatch, small=True)
    _add_measures(synthetic)
    _, document = _export()
    for result in document["results"]:
        assert result["energy"] == {
            "status": "unvalidated",
            "gpu_power_avg_w": None,
            "gpu_wh_per_1k_tokens": None,
        }
    monkeypatch.setattr(release, "VALIDATED_ENERGY_MACHINES", frozenset({"tour-rtx3050"}))
    _, document = _export()
    assert _problems(document) == []
    energy = document["results"][0]["energy"]
    assert energy["status"] == "measured" and energy["gpu_power_avg_w"] == 40.0
    # 1 Wh de segments pour les lignes du modèle (100 tokens chacune) : Wh par 1 000 tokens.
    tokens = sum(
        g["tokens"]["completion"] for g in synthetic.generation if g["model"] == "model-0:4b"
    )
    assert energy["gpu_wh_per_1k_tokens"] == pytest.approx(1.0 / (tokens / 1000))
    monkeypatch.setattr(release, "VALIDATED_ENERGY_MACHINES", frozenset())
    _add_measures(synthetic, power=False)
    _, document = _export()
    assert {r["energy"]["status"] for r in document["results"]} == {"unavailable"}
    assert _problems(document) == []


def test_two_exports_are_byte_identical_and_canonical(campaign):
    target, document = _export()
    first = target.read_bytes()
    target.unlink()
    again, _ = _export()
    assert again.read_bytes() == first
    assert sha256_bytes(first) == sha256_hex(document)  # JSON canonique d'AD-4
    assert b"\n" not in first


def test_cli_writes_the_same_bytes_without_ollama(campaign, monkeypatch):
    from slm_quality_bench.__main__ import main
    from slm_quality_bench.common import registry as registry_module

    monkeypatch.setattr(registry_module, "models_path", lambda: _fake_registry_file(campaign))
    assert main(["export-release", "--campaign", CAMPAIGN, "--version", "0.9.0"]) == 0
    cli_bytes = paths.release_path("0.9.0").read_bytes()
    # Même registre, même entrée : mêmes octets que l'appel direct.
    direct = release.release_bytes(release.build_release([CAMPAIGN], load_models()))
    assert cli_bytes == direct
    assert not paths.machine_lock_path().exists()


def _fake_registry_file(campaign) -> Path:
    document = _valid_yaml()
    entry = document["models"]["a:1b"]
    document["models"] = {tag: copy.deepcopy(entry) for tag in campaign.models}
    return _write_registry(paths.data_root().parent, document)


def test_release_holds_nothing_private(campaign):
    target, _ = _export()
    text = target.read_text(encoding="utf-8")
    assert SECRET_QUESTION not in text and SECRET_OUTPUT not in text
    for question in campaign.questions.values():
        assert question["id"] not in text
        for field in ("question_hash", "prompt_hash", "target_hash"):
            if field in question:
                assert question[field] not in text
    for line in campaign.generation[:50]:
        assert line["key"] not in text and line["prompt_hash"] not in text
    forbidden = ("question_id", "question_hash", "prompt_hash", "target_hash", "output", "key")
    document = json.loads(text)

    def keys(node):
        if isinstance(node, dict):
            for name, value in node.items():
                yield name
                yield from keys(value)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    assert not set(forbidden) & set(keys(document))


def test_partial_campaign_is_published_as_partial(campaign):
    kept = [g for g in campaign.generation if g["key"] != campaign.generation[0]["key"]]
    campaign.write_generation(kept)
    campaign.write_grading(
        [g for g in campaign.grading if g["key"] != campaign.generation[0]["key"]]
    )
    _, document = _export()
    assert _problems(document) == []
    assert document["campaigns"][0]["status"] == "partial"
    assert [r["complete"] for r in document["results"]][0] is False
    assert any(r["complete"] for r in document["results"])  # les autres pistes sont complètes
    assert all(r["energy"]["status"] == "unvalidated" for r in document["results"])


def test_model_missing_from_the_registry_is_refused_and_nothing_is_written(campaign):
    registry = _registry()
    del registry["model-1:4b"]
    with pytest.raises(release.ReleaseError, match="model-1:4b"):
        release.export_release([CAMPAIGN], "1.2.3", registry)
    assert not paths.release_path("1.2.3").exists()


def test_undeclared_machine_label_is_refused_and_nothing_is_written(campaign, monkeypatch):
    # Sans $QUALITY_BENCH_MACHINE, le manifeste porte le nom d'hôte : jamais publié (AD-6).
    from slm_quality_bench.__main__ import main
    from slm_quality_bench.common import registry as registry_module

    monkeypatch.setattr(release, "PUBLIC_MACHINES", {})
    with pytest.raises(release.ReleaseError, match="machine non déclarée publique"):
        release.export_release([CAMPAIGN], "1.2.3", _registry())
    monkeypatch.setattr(registry_module, "models_path", lambda: _fake_registry_file(campaign))
    assert main(["export-release", "--campaign", CAMPAIGN, "--version", "1.2.3"]) == 1
    assert not paths.release_path("1.2.3").exists()


def test_bench_version_is_read_from_pyproject(monkeypatch):
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert release._bench_version() == pyproject["project"]["version"]
    monkeypatch.setattr(release.metadata, "version", lambda name: "0.0.0")
    assert release._bench_version() == pyproject["project"]["version"]


def test_write_failure_exits_with_code_1(campaign, monkeypatch):
    from slm_quality_bench.__main__ import main
    from slm_quality_bench.common import registry as registry_module

    monkeypatch.setattr(registry_module, "models_path", lambda: _fake_registry_file(campaign))

    def refuse(*args, **kwargs):
        raise PermissionError("fichier verrouillé")

    monkeypatch.setattr(release.os, "replace", refuse)
    assert main(["export-release", "--campaign", CAMPAIGN, "--version", "1.2.3"]) == 1
    target = paths.release_path("1.2.3")
    assert not target.exists() and not list(target.parent.glob(".*.tmp"))


@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "1.2.3-rc1", "latest", ""])
def test_version_must_be_semver(campaign, version):
    with pytest.raises(release.ReleaseError):
        release.export_release([CAMPAIGN], version, _registry())


def test_unknown_campaign_is_a_configuration_error(campaign):
    with pytest.raises(config.ConfigError):
        release.export_release(["absente-0000"], "1.2.3", _registry())


# -- Schéma -----------------------------------------------------------------------------------


def test_schema_is_a_valid_2020_12_schema():
    Draft202012Validator.check_schema(VALIDATOR.schema)


def _mutations():
    def at(document):
        return document["results"][0]

    return {
        "clé omise": lambda d: at(d)["speed"].pop("load_time_ms"),
        "clé inconnue": lambda d: at(d).update(extra=1),
        "piste": lambda d: at(d).update(track="think_maybe"),
        "statut de campagne": lambda d: d["campaigns"][0].update(status="done"),
        "statut d'énergie": lambda d: at(d)["energy"].update(status="ok"),
        "énergie non mesurée avec valeur": lambda d: at(d)["energy"].update(gpu_power_avg_w=40.0),
        "énergie mesurée sans valeur": lambda d: at(d)["energy"].update(status="measured"),
        "rédaction sans statut": lambda d: at(d)["quality"]["usages"].update(
            writing=dict(at(d)["quality"]["global"])
        ),
        "statut de rédaction": lambda d: at(d)["quality"]["usages"].update(
            writing={**at(d)["quality"]["global"], "status": "maybe"}
        ),
        "usage inconnu": lambda d: at(d)["quality"]["usages"].update(
            poetry=at(d)["quality"]["global"]
        ),
        "score hors [0, 1]": lambda d: at(d)["quality"]["global"].update(score=1.5),
        "version": lambda d: d.update(bench_version="1.2"),
        "schéma": lambda d: d.update(schema="qb.results/2"),
        "empreinte": lambda d: d["set"].update(set_hash="abc"),
        "date": lambda d: d["campaigns"][0].update(first_line_at="2026-10-15"),
    }


@pytest.mark.parametrize("name", list(_mutations()))
def test_schema_catches_faults(campaign, name):
    _, document = _export()
    mutated = copy.deepcopy(document)
    _mutations()[name](mutated)
    assert _problems(mutated), name


@pytest.mark.parametrize(("name", "count"), [("bonsai2-20261023", 6), ("admission-20261026", 4)])
def test_shipped_registry_covers_the_split_campaigns(name, count):
    registry = load_models()
    models = config.load_campaign(paths.campaign_config_path(name)).generation["models"]
    assert len(models) == count
    assert [m["tag"] for m in models if m["tag"] not in registry] == []
