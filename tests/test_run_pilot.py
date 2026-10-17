"""Lanceur du pilote : ordre des étapes, arrêt au premier refus, reprise, pas de juge."""

from __future__ import annotations

import pytest

from slm_quality_bench import run_pilot
from slm_quality_bench.common import paths
from slm_quality_bench.generation.commands import COMPLETE_MESSAGE, STOPPED_MESSAGE

PILOT = "pilot-x"
REPLAY = "pilot-x-replay"


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    from slm_quality_bench.common.logs import setup_logging

    setup_logging("test", None)


def _log(campaign, message):
    path = paths.log_path(campaign, "generate")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"2026-10-17T10:00:00 INFO [generate] x : {message % campaign}\n")


@pytest.fixture
def steps(monkeypatch):
    """Étapes simulées : codes par commande, journal de ``generate`` complet par défaut."""
    calls: list[list[str]] = []
    behaviour = {"codes": {}, "stopped": set()}

    def fake(arguments):
        calls.append(list(arguments))
        command = arguments[0]
        if command == "generate":
            target = arguments[2]
            _log(target, STOPPED_MESSAGE if target in behaviour["stopped"] else COMPLETE_MESSAGE)
        return behaviour["codes"].get((command, arguments[2]), 0)

    monkeypatch.setattr(run_pilot, "RUN_STEP", fake)
    return calls, behaviour


def _commands(calls):
    return [(call[0], call[2]) for call in calls]


def test_nominal_order_and_no_judge(steps):
    calls, _ = steps
    assert run_pilot.run_pilot(PILOT) == 0
    assert _commands(calls) == [
        ("precheck", PILOT),
        ("generate", PILOT),
        ("generate", REPLAY),
        ("grade", PILOT),
        ("grade", REPLAY),
        ("pilot", PILOT),
    ]
    assert calls[0][calls[0].index("--replay") + 1] == REPLAY
    assert calls[-1][-2:] == ["--replay", REPLAY]
    assert not any(call[0] in ("judge", "calibrate", "calibrate-sample") for call in calls)


@pytest.mark.parametrize("failing", [("precheck", PILOT), ("generate", REPLAY), ("grade", PILOT)])
def test_first_refusal_stops_the_chain(steps, failing):
    calls, behaviour = steps
    behaviour["codes"][failing] = 2
    assert run_pilot.run_pilot(PILOT) == 2
    assert _commands(calls)[-1] == failing  # rien après le refus


def test_clean_stop_of_generation_does_not_grade(steps):
    calls, behaviour = steps
    behaviour["stopped"].add(PILOT)
    assert run_pilot.run_pilot(PILOT) == run_pilot.EXIT_STOPPED
    assert [call[0] for call in calls] == ["precheck", "generate"]


def test_rerun_after_stop_resumes_the_same_commands(steps):
    calls, behaviour = steps
    behaviour["stopped"].add(PILOT)
    run_pilot.run_pilot(PILOT)
    behaviour["stopped"].clear()
    first = list(calls)
    assert run_pilot.run_pilot(PILOT) == 0
    assert calls[len(first) :][:2] == first  # mêmes commandes, donc même reprise de generate


def test_interruption_is_reported_as_130(monkeypatch):
    def interrupted(arguments):
        raise run_pilot.InterruptedStepError(0)

    monkeypatch.setattr(run_pilot, "RUN_STEP", interrupted)
    assert run_pilot.run_pilot(PILOT) == run_pilot.EXIT_INTERRUPTED


def test_generation_completed_reads_the_last_message():
    assert run_pilot.generation_completed(PILOT) is False  # pas de journal
    _log(PILOT, STOPPED_MESSAGE)
    assert run_pilot.generation_completed(PILOT) is False
    _log(PILOT, COMPLETE_MESSAGE)
    assert run_pilot.generation_completed(PILOT) is True
    _log(PILOT, STOPPED_MESSAGE)
    assert run_pilot.generation_completed(PILOT) is False


def test_main_refuses_a_bad_identifier(steps):
    calls, _ = steps
    assert run_pilot.main(["--campaign", "../x"]) == 2
    assert calls == []


def test_main_runs_with_a_default_replay(steps):
    calls, _ = steps
    assert run_pilot.main(["--campaign", PILOT]) == 0
    assert calls[2][2] == REPLAY


def test_real_subprocess_step_runs_the_cli():
    """Le lanceur appelle bien ``python -m slm_quality_bench`` dans un processus à part."""
    assert run_pilot.run_subprocess(["--help"]) == 0


def test_ollama_version_is_forwarded_to_precheck_only_when_given(steps):
    calls, _ = steps
    assert run_pilot.run_pilot(PILOT) == 0
    assert "--ollama-version" not in calls[0]  # precheck lit ollama_version du YAML
    calls.clear()
    assert run_pilot.run_pilot(PILOT, ollama_version="0.40.6") == 0
    assert calls[0][calls[0].index("--ollama-version") + 1] == "0.40.6"
    assert not any("--ollama-version" in call for call in calls[1:])
