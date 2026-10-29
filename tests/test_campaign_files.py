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
    """Lignes du tableau « Les 23 modèles de la campagne » : (tag, rôle)."""
    text = MODELES.read_text(encoding="utf-8")
    table = text.split("## Les 23 modèles de la campagne", 1)[1].split("\n## ", 1)[0]
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
    assert len(rows) == 23
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


THINK_ON_ONLY = ("LiquidAI/lfm2.5-2.6b", "lfm2.5-thinking:1.2b")
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
                **dict.fromkeys(THINK_ON_ONLY, ["think_on"]),
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
    """Lecture seule de l'ancien banc et du catalogue réels : chacun des 23 tags a un débit de
    décodage, de préremplissage et une durée de chargement ; 17 déclarent ``thinking``."""
    import json

    from slm_quality_bench.report.pilot import old_bench_by_tag

    settings = config.load_pilot_settings(paths.pilot_settings_path())
    old = json.loads(settings.old_bench_path.read_text(encoding="utf-8"))
    catalog = json.loads(settings.catalog_path.read_text(encoding="utf-8"))
    entries = old_bench_by_tag(old, catalog, settings.full_models)
    assert len(entries) == 23
    for tag, entry in entries.items():
        rate = entry.rate
        assert rate.known, (tag, rate.reason)
        assert rate.decode > 0 and rate.prefill > 0 and rate.load_s is not None, tag
    assert sum(1 for entry in entries.values() if entry.rate.thinking) == 17


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
        expected = {
            **dict.fromkeys(THINK_ON_ONLY, ["think_on"]),
            THINK_OFF_ONLY: ["think_off"],
        }.get(model["tag"])
        if expected:
            assert model["tracks"] == expected
        else:
            assert model["tracks"] in (["think_off"], ["think_off", "think_on"])
        if model["think_off"] is None:  # sans capacité thinking : piste coupée seule
            assert model["tracks"] == ["think_off"] and model["think_on"] is None
    assert sum(1 for model in models if "think_on" in model["tracks"]) == 16
    assert sum(1 for model in models if "think_off" in model["tracks"]) == 21


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


ADMISSION = "admission-20261018"
CANDIDATES = ["lfm2.5:24b-a2b-q4_K_M", "nemotron-3.5-lightning:30b-a3b-q4_K_M"]


def test_admission_campaign_shares_the_full_campaign_settings():
    admission = config.load_campaign(paths.campaign_config_path(ADMISSION))
    full = config.load_campaign(paths.campaign_config_path(FULL))
    assert admission.set_id == full.set_id == "set-v3"
    assert admission.grading == full.grading
    assert admission.gpu_check == full.gpu_check
    assert admission.ollama_version == full.ollama_version
    for key in ("request", "caps", "num_ctx_tiers"):
        assert admission.generation[key] == full.generation[key], key
    models = admission.generation["models"]
    assert [model["tag"] for model in models] == CANDIDATES
    assert [model["family"] for model in models] == ["lfm", "nemotron"]
    for model in models:
        assert model["tracks"] == ["think_off", "think_on"]
        assert (model["think_off"], model["think_on"]) == (False, True)
        assert model["num_ctx_max"] == 32768
    # Les candidats ne sont pas encore dans la campagne complète.
    assert not set(CANDIDATES) & {model["tag"] for model in full.generation["models"]}


def test_admission_selection_draws_70_questions_of_set_v3_per_track():
    """Variante réduite (décision du 2026-10-18) : effectifs think_on du rejeu sur les deux
    pistes ; sur l'index réel de set-v3, 66 groupes donnent 70 questions (groupes à deux
    questions)."""
    from slm_quality_bench.common.selection import group_ids

    admission = config.load_campaign(paths.campaign_config_path(ADMISSION))
    replay = config.load_campaign(paths.campaign_config_path(REPLAY))
    groups = admission.generation["selection"]["groups"]
    replay_groups = replay.generation["selection"]["groups"]
    assert groups["seed"] == replay_groups["seed"]
    assert groups["per_usage"].keys() == replay_groups["per_usage"].keys()
    for usage, counts in groups["per_usage"].items():
        assert counts["think_on"] == replay_groups["per_usage"][usage]["think_on"], usage
        assert counts["think_off"] == counts["think_on"]  # set-v3 : plus de groupe sans think_on
    index = [
        json.loads(line)
        for line in (paths.REPO_ROOT / "benchmarks/quality/sets/set-v3/index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    questions = {record["id"]: record for record in index}
    ids = sorted(questions)  # set-v3 : toutes les questions ont les deux pistes
    chosen = group_ids(ids, ids, questions, groups)
    assert sum(c["think_on"] for c in groups["per_usage"].values()) == 66
    assert len(chosen) == 70


NEMOTRON = "admission-20261018-nemotron"


def test_nemotron_admission_shares_the_admission_settings():
    reduced = config.load_campaign(paths.campaign_config_path(NEMOTRON))
    admission = config.load_campaign(paths.campaign_config_path(ADMISSION))
    assert reduced.set_id == admission.set_id == "set-v3"
    assert reduced.grading == admission.grading
    assert reduced.gpu_check == admission.gpu_check
    assert reduced.ollama_version == admission.ollama_version
    for key in ("request", "caps", "num_ctx_tiers"):
        assert reduced.generation[key] == admission.generation[key], key
    assert reduced.generation["models"] == [admission.generation["models"][1]]
    assert reduced.generation["models"][0]["tag"] == CANDIDATES[1]


def test_nemotron_admission_selection_reaches_the_high_tiers():
    """15 questions par piste, dont exactement 2 au palier 16 384 et 3 au palier 32 768 (mesure
    de la mémoire de pointe et du contexte validé) ; le tirage est vérifié sur le set-v3 construit.
    Comme celui de l'admission, ce test saute en CI faute de set-v3 (jeu hors dépôt)."""
    from collections import Counter
    from pathlib import Path

    from slm_quality_bench.generation.runner import build_plan

    from .conftest import _REAL_DATA_ROOT

    set_dir = Path(_REAL_DATA_ROOT) / "sets" / "set-v3"
    questions_path = set_dir / "questions.jsonl"
    if not questions_path.is_file():
        pytest.skip("set-v3 non construit dans QUALITY_BENCH_DATA")
    by_id = {}
    for line in questions_path.read_text(encoding="utf-8").splitlines():
        question = json.loads(line)
        by_id[question["id"]] = question
    tracks = json.loads((set_dir / "tracks.json").read_text(encoding="utf-8"))
    campaign = config.load_campaign(paths.campaign_config_path(NEMOTRON))
    plan = build_plan(campaign.generation, by_id, tracks)
    for track in ("think_off", "think_on"):
        assert len(plan[track]) == 15, track
        tiers = Counter(question["num_ctx"] for question in plan[track])
        assert tiers == {4096: 1, 8192: 9, 16384: 2, 32768: 3}, (track, tiers)
    assert [q["id"] for q in plan["think_off"]] == [q["id"] for q in plan["think_on"]]


BONSAI2 = "bonsai2-20261023"
ADMISSION_1026 = "admission-20261026"
BOLT_TAG = "hf.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF:UD-Q4_K_XL"
K2_TAG = "hf.co/IFM/K2-Horizon-3.7B-GGUF:Q4_K_M"
# Repris à l'identique de full-20261018 (décision du 2026-10-27 : full est arrêtée après granite).
FROM_FULL_TAGS = ["gemma4-ud:12b-iq3_xxs", "bonsai:27b-q1_0"]
ADMISSION_1026_TAGS = [K2_TAG, BOLT_TAG, *FROM_FULL_TAGS]
BONSAI2_TAGS = [
    "hf.co/prism-ml/Ternary-Bonsai-2-2B-gguf:Q2_0",
    "hf.co/prism-ml/Ternary-Bonsai-2-4B-gguf:Q2_0",
    "hf.co/prism-ml/Ternary-Bonsai-2-9B-gguf:Q2_0",
]
FLINT = "flint-20261029"
FLINT_TAG = "hf.co/unsloth/flint-GGUF:UD-Q3_K_XL"
LFM3 = "lfm3-20261029"
LFM3_TAG = "lfm3:1.7b-q4_K_M"
LFM3_OMNI_TAG = "lfm3-omni:2b-q4_K_M"


def _without_models(campaign):
    return {key: value for key, value in campaign.generation.items() if key != "models"}


def test_bonsai2_campaign_shares_the_full_campaign_settings():  # configuration, pas comportement
    bonsai = config.load_campaign(paths.campaign_config_path(BONSAI2))
    full = config.load_campaign(paths.campaign_config_path(FULL))
    assert bonsai.set_id == full.set_id == "set-v3"
    assert bonsai.grading == full.grading
    assert bonsai.gpu_check == full.gpu_check
    # Seule la version d'Ollama diffère (0.40.13, décision du 2026-10-29 ; Q2_0 lu depuis 0.40.6) :
    # full-20261018 reste en 0.40.5.
    assert full.ollama_version == "0.40.5"
    assert bonsai.ollama_version == "0.40.13"
    assert _without_models(bonsai) == _without_models(full)
    models = bonsai.generation["models"]
    assert [model["tag"] for model in models] == BONSAI2_TAGS
    full_models = {model["tag"]: model for model in full.generation["models"]}
    for model in models:
        # Bonsai 2 : famille à part (décision du 2026-10-23), ni qwen (bases), ni bonsai (1 bit).
        assert model["family"] == "bonsai2"
        assert model["tracks"] == ["think_off", "think_on"]
        # Valeurs think du YAML, supposées d'après la lignée Qwen : precheck (/api/show) les
        # confirme sur la tour, ce test ne fige que la configuration.
        assert (model["think_off"], model["think_on"]) == (False, True)
        assert model["num_ctx_max"] == 32768
    # Campagne distincte : les 23 modèles de la campagne complète ne changent pas ; les Bonsai 2
    # n'y sont pas, et Bolt est passé dans admission-20261026.
    assert len(full.generation["models"]) == 23
    assert not set(BONSAI2_TAGS) & set(full_models)
    assert BOLT_TAG not in {model["tag"] for model in models}
    # Bonsai 2 est hors périmètre (2026-10-29) : le fichier est gardé, les références Qwen ne sont
    # plus rejouées (replay-20261029 supprimé).
    assert not any(model["tag"].startswith("qwen3.5:") for model in models)


def test_flint_campaign_shares_the_bonsai2_settings_with_one_model():
    flint = config.load_campaign(paths.campaign_config_path(FLINT))
    bonsai = config.load_campaign(paths.campaign_config_path(BONSAI2))
    assert flint.set_id == bonsai.set_id == "set-v3"
    assert flint.grading == bonsai.grading
    assert flint.gpu_check == bonsai.gpu_check
    assert flint.ollama_version == bonsai.ollama_version == "0.40.13"
    assert _without_models(flint) == _without_models(bonsai)
    (model,) = flint.generation["models"]
    assert model["tag"] == FLINT_TAG and model["family"] == "flint"
    assert model["tracks"] == ["think_off", "think_on"]
    assert (model["think_off"], model["think_on"]) == (False, True)  # à confirmer par precheck
    assert model["num_ctx_max"] == 32768


def test_lfm3_campaign_shares_the_flint_settings_with_two_models():
    lfm3 = config.load_campaign(paths.campaign_config_path(LFM3))
    flint = config.load_campaign(paths.campaign_config_path(FLINT))
    assert lfm3.set_id == flint.set_id == "set-v3"
    assert lfm3.grading == flint.grading
    assert lfm3.gpu_check == flint.gpu_check
    assert lfm3.ollama_version == flint.ollama_version == "0.40.13"
    assert _without_models(lfm3) == _without_models(flint)
    text, omni = lfm3.generation["models"]
    assert (text["tag"], omni["tag"]) == (LFM3_TAG, LFM3_OMNI_TAG)
    # Famille lfm, celle de LFM 2.5.
    assert text["family"] == omni["family"] == "lfm"
    assert text["tracks"] == ["think_off", "think_on"]
    assert (text["think_off"], text["think_on"]) == (False, True)
    # Omni : pas de capacité « thinking » dans /api/show, piste think_off seule (convention K2).
    assert omni["tracks"] == ["think_off"]
    assert (omni["think_off"], omni["think_on"]) == (None, None)
    assert text["num_ctx_max"] == omni["num_ctx_max"] == 32768


def test_replay_campaign_is_removed_and_bonsai2_is_out_of_scope():
    assert not (paths.campaign_config_path("replay-20261029")).exists()
    bonsai = paths.campaign_config_path(BONSAI2)
    assert bonsai.read_text(encoding="utf-8").startswith("# HORS PÉRIMÈTRE")


def test_admission_20261026_shares_the_full_campaign_settings():
    admission = config.load_campaign(paths.campaign_config_path(ADMISSION_1026))
    full = config.load_campaign(paths.campaign_config_path(FULL))
    assert admission.set_id == full.set_id == "set-v3"
    assert admission.grading == full.grading
    assert admission.gpu_check == full.gpu_check
    assert admission.ollama_version == full.ollama_version == "0.40.5"
    assert _without_models(admission) == _without_models(full)
    models = admission.generation["models"]
    assert [model["tag"] for model in models] == ADMISSION_1026_TAGS
    full_models = {model["tag"]: model for model in full.generation["models"]}
    for model in models:
        if model["tag"] in FROM_FULL_TAGS:
            # Gemma 12B et Bonsai 27B : entrée identique à celle de full-20261018 (2026-10-27).
            assert model == full_models[model["tag"]]
            continue
        # K2 Horizon (décision du 2026-10-26) : famille à part, non qwen ; Bolt-E4B (décision du
        # 2026-10-24) : famille de l'éditeur, nemotron.
        assert model["family"] == ("nemotron" if model["tag"] == BOLT_TAG else "k2horizon")
        # Piste think_off seule pour les deux (precheck du 2026-10-27 : pas de capacité
        # « thinking » dans /api/show pour ces GGUF Hugging Face).
        assert model["tracks"] == ["think_off"]
        assert (model["think_off"], model["think_on"]) == (None, None)
        assert model["num_ctx_max"] == 32768
    # K2 7B retiré (2026-10-27) : débordement de la VRAM dès 8 192.
    assert "hf.co/IFM/K2-Horizon-7B-GGUF:Q4_K_M" not in {model["tag"] for model in models}
    assert not {K2_TAG, BOLT_TAG} & set(full_models)


def test_bonsai2_selection_keeps_the_whole_public_index_of_set_v3():
    """Sélection de la campagne sur l'index public de set-v3 : aucune restriction, donc 800
    questions par piste et 3 x 2 x 800 lignes. L'index public n'a ni palier ni taille de prompt :
    ``build_plan`` lui-même ne tourne que sur le jeu construit (test suivant, sauté en CI comme
    celui de full-20261018)."""
    from slm_quality_bench.common.selection import selected_ids

    index = [
        json.loads(line)
        for line in (paths.REPO_ROOT / "benchmarks/quality/sets/set-v3/index.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    questions = {record["id"]: record for record in index}
    ids = sorted(questions)  # set-v3 : toutes les questions ont les deux pistes
    generation = config.load_campaign(paths.campaign_config_path(BONSAI2)).generation
    assert selected_ids(generation["selection"], questions, ids, ids) is None
    lines = sum(len(model["tracks"]) * len(questions) for model in generation["models"])
    assert lines == 3 * 2 * 800


def test_built_set_v3_passes_the_plan_of_the_bonsai2_campaign():
    from pathlib import Path

    from slm_quality_bench.generation.runner import build_plan

    from .conftest import _REAL_DATA_ROOT

    set_dir = Path(_REAL_DATA_ROOT) / "sets" / "set-v3"
    questions_path = set_dir / "questions.jsonl"
    if not questions_path.is_file():
        pytest.skip("set-v3 non construit dans QUALITY_BENCH_DATA")
    by_id = {}
    for line in questions_path.read_text(encoding="utf-8").splitlines():
        question = json.loads(line)
        by_id[question["id"]] = question
    tracks = json.loads((set_dir / "tracks.json").read_text(encoding="utf-8"))
    campaign = config.load_campaign(paths.campaign_config_path(BONSAI2))
    plan = build_plan(campaign.generation, by_id, tracks)
    assert len(plan["think_off"]) == len(plan["think_on"]) == 800
