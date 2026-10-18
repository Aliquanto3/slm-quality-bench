"""Fichiers réels du pilote (story 8) : ``campaigns/pilot-20261017.yaml``, son rejeu et
``pilot.yaml`` se chargent et respectent la spec (modeles.md, rejeu sous-ensemble du pilote)."""

from __future__ import annotations

import copy
import json
import re

import pytest

from slm_quality_bench.common import config, paths
from slm_quality_bench.common.config import DEFAULT_GENERATION

PILOT = "pilot-20261017"
REPLAY = f"{PILOT}-replay"
MODELES = paths.REPO_ROOT / "docs/spec/modeles.md"


def _modeles_rows():
    """Lignes du tableau « Les 21 modèles de la campagne » : (tag, rôle)."""
    text = MODELES.read_text(encoding="utf-8")
    table = text.split("## Les 21 modèles de la campagne", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in table.splitlines():
        match = re.match(r"\|[^|]+\| `([^`]+)` \|.*\|\s*([^|]*?)\s*\|$", line)
        if match:
            rows.append((match.group(1), match.group(2).strip()))
    return rows


@pytest.fixture(scope="module")
def campaigns():
    return {c: config.load_campaign(paths.campaign_config_path(c)) for c in (PILOT, REPLAY)}


def test_modeles_table_is_parsed():
    rows = _modeles_rows()
    assert len(rows) == 21
    assert sum(1 for _, role in rows if role == "pilote") == 5


def test_both_campaigns_load_with_the_same_generation_but_selection(campaigns):
    pilot, replay = campaigns[PILOT], campaigns[REPLAY]
    assert pilot.set_id == replay.set_id == "set-v2"
    assert pilot.grading == replay.grading == {"judge": "haiku"}
    without = []
    for campaign in (pilot, replay):
        generation = copy.deepcopy(campaign.generation)
        generation.pop("selection")
        without.append(generation)
    assert without[0] == without[1]
    assert pilot.generation["request"]["k"] == 1
    assert pilot.generation["caps"] == DEFAULT_GENERATION["caps"]
    assert pilot.generation["num_ctx_tiers"] == DEFAULT_GENERATION["num_ctx_tiers"]


def test_replay_counts_are_within_the_pilot(campaigns):
    pilot = campaigns[PILOT].generation["selection"]["groups"]
    replay = campaigns[REPLAY].generation["selection"]["groups"]
    assert pilot["seed"] == replay["seed"]
    assert set(replay["per_usage"]) == set(pilot["per_usage"])
    for usage, counts in replay["per_usage"].items():
        mine = pilot["per_usage"][usage]
        assert counts["think_on"] <= mine["think_on"]
        assert counts["think_off"] <= mine["think_off"]
        # Groupes sans think_on : préfixe plus court aussi.
        assert counts["think_off"] - counts["think_on"] <= mine["think_off"] - mine["think_on"]


THINK_ON_ONLY = "LiquidAI/lfm2.5-2.6b"
THINK_OFF_ONLY = "lfm2.5:8b-a1b-q4_K_M"


def test_campaign_models_are_the_five_pilot_models_of_modeles_md(campaigns):
    expected = [tag for tag, role in _modeles_rows() if role == "pilote"]
    for campaign in campaigns.values():
        models = campaign.generation["models"]
        assert sorted(model["tag"] for model in models) == sorted(expected)
        for model in models:
            # LFM 2.5 2.6B ne publie que think true dans /api/show (Ollama 0.40.2) : piste
            # think_on seulement, le préflight refusant think false. LFM 2.5 8B-A1B (renderer lfm2
            # d'Ollama 0.40.5) ne publie que think false : piste think_off seulement.
            expected_tracks = {
                THINK_ON_ONLY: ["think_on"],
                THINK_OFF_ONLY: ["think_off"],
            }.get(model["tag"], ["think_off", "think_on"])
            assert model["tracks"] == expected_tracks
            assert (model["think_off"], model["think_on"]) == (False, True)


def test_pilot_settings_point_outside_the_repository_by_default():
    settings = config.load_pilot_settings(paths.pilot_settings_path())
    assert settings.old_bench_path.parent.parent == paths.origin_dir() / "benchmarks"


def test_pilot_references_follow_explicit_paths(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.OLD_BENCH_ENV, str(tmp_path / "ancien.json"))
    monkeypatch.setenv(paths.CATALOG_ENV, str(tmp_path / "catalogue.json"))
    settings = config.load_pilot_settings(paths.pilot_settings_path())
    assert settings.old_bench_path == tmp_path / "ancien.json"
    assert settings.catalog_path == tmp_path / "catalogue.json"


def test_pilot_campaigns_tolerate_overwolf_only():
    for campaign in (PILOT, REPLAY):
        loaded = config.load_campaign(paths.campaign_config_path(campaign))
        assert loaded.gpu_check.allowed_processes == ("Overwolf.exe",)


def test_real_pilot_settings():
    settings = config.load_pilot_settings(paths.pilot_settings_path())
    rows = _modeles_rows()
    assert list(settings.full_models) == [tag for tag, _ in rows]
    pilot_tags = {tag for tag, role in rows if role == "pilote"}
    assert pilot_tags <= set(settings.full_models)
    assert settings.budget_hours == 216.0
    assert settings.think_on_n == 330
    assert [caps["think_on"] for caps in settings.reduction_caps] == [
        {"reasoning": 3072, "default": 1536},
        {"reasoning": 2048, "default": 1024},
    ]


def test_full_models_resolve_to_the_old_bench_through_the_catalog(origin_files):
    """Lecture seule de l'ancien banc et du catalogue réels : chacun des 21 tags a un débit de
    décodage, de préremplissage et une durée de chargement ; 16 déclarent ``thinking``."""
    import json

    from slm_quality_bench.report.pilot import old_bench_by_tag

    settings = config.load_pilot_settings(paths.pilot_settings_path())
    old = json.loads(settings.old_bench_path.read_text(encoding="utf-8"))
    catalog = json.loads(settings.catalog_path.read_text(encoding="utf-8"))
    entries = old_bench_by_tag(old, catalog, settings.full_models)
    assert len(entries) == 21
    for tag, entry in entries.items():
        rate = entry.rate
        assert rate.known, (tag, rate.reason)
        assert rate.decode > 0 and rate.prefill > 0 and rate.load_s is not None, tag
    assert sum(1 for entry in entries.values() if entry.rate.thinking) == 16


FULL = "full-20261018"


def _load_set(set_id: str):
    from slm_quality_bench.questions.schema import REFUSED_SOURCES, SOURCES

    return config.load_set(paths.set_config_path(set_id), SOURCES, REFUSED_SOURCES)


def test_set_v3_is_set_v2_with_think_on_on_every_question():
    v2, v3 = _load_set("set-v2"), _load_set("set-v3")
    assert v3.seed == v2.seed and v3.multi_turn_history is v2.multi_turn_history
    assert [(s.source, s.count, s.exclude) for s in v3.sources] == [
        (s.source, s.count, s.exclude) for s in v2.sources
    ]
    assert v3.think_off == v2.think_off
    assert v3.think_on == v3.think_off
    assert sum(v3.think_on.values()) == sum(v3.think_off.values()) == 800


def test_full_campaign_follows_the_decisions_of_2026_10_18():
    campaign = config.load_campaign(paths.campaign_config_path(FULL))
    assert campaign.set_id == "set-v3"
    generation = campaign.generation
    assert generation["selection"] is None
    assert generation["request"]["k"] == 1
    assert generation["caps"] == {
        "think_off": {"default": 4096, "rag": 2048},
        "think_on": {"default": 4096, "reasoning": 4096, "rag": 2048},
    }
    assert campaign.gpu_check.allowed_processes == ("Overwolf.exe",)
    settings = config.load_pilot_settings(paths.pilot_settings_path())
    models = generation["models"]
    assert [model["tag"] for model in models] == list(settings.full_models)
    assert [model["tag"] for model in models] == [tag for tag, _ in _modeles_rows()]
    for model in models:
        assert model["num_ctx_max"] == 32768
        expected = {THINK_ON_ONLY: ["think_on"], THINK_OFF_ONLY: ["think_off"]}.get(model["tag"])
        if expected:
            assert model["tracks"] == expected
        else:
            assert model["tracks"] in (["think_off"], ["think_off", "think_on"])
        if model["think_off"] is None:  # sans capacité thinking : piste coupée seule
            assert model["tracks"] == ["think_off"] and model["think_on"] is None
    assert sum(1 for model in models if "think_on" in model["tracks"]) == 15


def test_set_v3_tiers_cover_the_caps_of_the_full_campaign():
    # Les paliers num_ctx de set-v3 sont dimensionnés pour ses caps (AD-5) : ils doivent couvrir
    # chaque plafond de la campagne, piste par piste et usage par usage.
    caps = _load_set("set-v3").caps
    campaign = config.load_campaign(paths.campaign_config_path(FULL))
    for track, track_caps in campaign.generation["caps"].items():
        for usage in config.USAGES:
            wanted = track_caps.get(usage, track_caps["default"])
            assert wanted <= caps[track].get(usage, caps[track]["default"]), (track, usage)


def test_built_set_v3_passes_the_plan_of_the_full_campaign():
    """Jeu construit dans ``$QUALITY_BENCH_DATA`` : ``build_plan`` (precheck, generate) l'accepte
    avec les plafonds de la campagne, et son index est celui du dépôt."""
    from pathlib import Path

    from slm_quality_bench.generation.runner import build_plan

    from .conftest import _REAL_DATA_ROOT

    set_dir = Path(_REAL_DATA_ROOT) / "sets" / "set-v3"  # avant l'isolation des tests
    questions_path = set_dir / "questions.jsonl"
    if not questions_path.is_file():
        pytest.skip("set-v3 non construit dans QUALITY_BENCH_DATA")
    by_id = {}
    for line in questions_path.read_text(encoding="utf-8").splitlines():
        question = json.loads(line)
        by_id[question["id"]] = question
    tracks = json.loads((set_dir / "tracks.json").read_text(encoding="utf-8"))
    hashes = {
        json.loads(line)["id"]: json.loads(line)["question_hash"]
        for line in (paths.REPO_ROOT / "benchmarks/quality/sets/set-v3/index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    assert {qid: q["question_hash"] for qid, q in by_id.items()} == hashes
    campaign = config.load_campaign(paths.campaign_config_path(FULL))
    plan = build_plan(campaign.generation, by_id, tracks)
    assert len(plan["think_off"]) == len(plan["think_on"]) == 800
