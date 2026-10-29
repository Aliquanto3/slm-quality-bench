"""Reclassement des prompts tronqués en silence par Ollama (constat du 2026-10-28) : lignes
simulées, sans données de campagne."""

from __future__ import annotations

import pytest

from slm_quality_bench.common.schemas import SchemaValidationError, validate
from slm_quality_bench.grading.silent_truncation import (
    SILENT_PROMPT_TRUNCATION,
    has_signature,
    real_prompts,
    reclassify,
)

from .factories import HASH_A, generation_record

CWE = "rag/oneruler-fr-cwe/0001"
NONE = "abstention/oneruler-fr-none/0001"


def _line(model, question_id, status, prompt, *, num_ctx=16384, calls=1, cached=0):
    extra = {"context_limit": "bench"} if status == "context_exceeded" else {}
    record = generation_record(
        **extra,
        key=f"c|{model}|think_off|{question_id}|0",
        model=model,
        question_id=question_id,
        num_ctx=num_ctx,
        num_predict=2048,
        status=status,
        calls=calls,
    )
    record["tokens"] = {**record["tokens"], "prompt": prompt, "prompt_cached": cached}
    return record


def _questions(est_cwe=11419, est_none=9820):
    return {CWE: {"est_prompt_tokens": est_cwe}, NONE: {"est_prompt_tokens": est_none}}


def _by_key(*lines):
    return {line["key"]: line for line in lines}


def test_halved_prompt_with_long_real_prompt_is_reclassified():
    refused = _line("a", CWE, "context_exceeded", 14600)
    ok = _line("b", CWE, "ok", 8194)
    truncated = _line("c", CWE, "truncated", 8195)
    generations = _by_key(refused, ok, truncated)
    result = reclassify(generations, _questions())
    assert result.reclassified == {ok["key"], truncated["key"]}
    for key in result.reclassified:
        assert result.generations[key]["status"] == "context_exceeded"
        assert result.generations[key]["context_limit"] == "bench"
        validate(result.generations[key])
    assert result.generations[refused["key"]] == refused
    assert generations[ok["key"]]["status"] == "ok"  # entrée jamais modifiée
    assert result.suspects == 0


def test_tokenizer_margin_covers_a_real_prompt_just_under_the_limit():
    """Plus grand prompt mesuré 14 261 < 14 336 (autre tokenizer) : reclassé (marge de 10 %)."""
    generations = _by_key(_line("a", CWE, "ok", 14261), _line("b", CWE, "ok", 8194))
    assert len(reclassify(generations, _questions()).reclassified) == 1


def test_abstention_prompt_near_half_context_is_kept():
    """Abstention OneRuler à ~8 192 tokens au palier 16 384 : taille réelle, pas une troncature."""
    lines = [_line(m, NONE, "ok", p) for m, p in (("a", 8193), ("b", 8195), ("c", 9269))]
    result = reclassify(_by_key(*lines), _questions())
    assert result.reclassified == frozenset()
    assert result.suspects == 2
    assert all(line["status"] == "ok" for line in result.generations.values())


def test_unknown_real_prompt_is_not_reclassified():
    """Campagne à un seul modèle qui tronque : seule l'estimation (sous-estimée) est connue."""
    line = _line("a", CWE, "ok", 8194)
    result = reclassify(_by_key(line), _questions())
    assert result.reclassified == frozenset() and result.suspects == 1


def test_estimate_alone_bounds_the_real_prompt():
    line = _line("a", CWE, "ok", 8194)
    result = reclassify(_by_key(line), _questions(est_cwe=15000))
    assert result.reclassified == {line["key"]}


def test_multi_call_lines_are_ignored_on_both_sides():
    summed = _line("a", CWE, "ok", 30000, calls=3)
    halved = _line("b", CWE, "ok", 8194, calls=2)
    assert real_prompts([summed], _questions())[CWE] == 11419
    assert not has_signature(halved)
    assert reclassify(_by_key(summed, halved), _questions()).reclassified == frozenset()


@pytest.mark.parametrize("prompt, expected", [(8191, False), (8192, True), (8200, True)])
def test_signature_bounds(prompt, expected):
    assert has_signature(_line("a", CWE, "ok", prompt)) is expected


def test_signature_reads_prompt_without_cached_tokens():
    assert has_signature(_line("a", CWE, "truncated", 8195, cached=7))


def test_other_statuses_have_no_signature():
    assert not has_signature(_line("a", CWE, "error", 8194))
    assert not has_signature(_line("a", CWE, "context_exceeded", 8194))


def _grading(**overrides):
    record = {
        "schema": "qb.grading/1",
        "key": "c|m|think_off|rag/oneruler-fr-cwe/0001|0",
        "generation_manifest": HASH_A,
        "judgment_manifest": None,
        "grader": "oneruler_cwe@2",
        "status": "context_exceeded",
        "score": None,
        "success": None,
        "metrics": {},
        "context_limit": "bench",
        "reclassified": SILENT_PROMPT_TRUNCATION,
    }
    record.update(overrides)
    return record


def test_reclassified_grading_line_validates():
    assert validate(_grading()) == "qb.grading/1"


@pytest.mark.parametrize(
    "overrides",
    [
        {"reclassified": "autre"},
        {"context_limit": "model", "score": 0.0, "success": False},
        {"status": "ok", "score": 1.0, "success": True, "context_limit": None},
    ],
)
def test_reclassified_only_on_bench_context_exceeded(overrides):
    record = _grading(**overrides)
    if record.get("context_limit") is None:
        record.pop("context_limit")
    with pytest.raises(SchemaValidationError):
        validate(record)
