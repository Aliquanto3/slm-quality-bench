"""Commande ``status`` : avancement d'une campagne, lecture seule, notifications (simulées)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from slm_quality_bench.common import paths
from slm_quality_bench.common.canonical import pretty_bytes
from slm_quality_bench.common.jsonl import rewrite_jsonl
from slm_quality_bench.common.locks import FileLock
from slm_quality_bench.monitor import commands
from slm_quality_bench.monitor.notify import Transitions, dispatch, drift_level
from slm_quality_bench.monitor.status import (
    RowCache,
    _per_line_seconds,
    compute_status,
    estimate_remaining,
    expected_lines,
    lock_held,
    render_text,
    verdict,
)

from .grading_factories import questions

CAMPAIGN = "mon-test"
SET_ID = "small-mon"
A, B = (
    "m-a:1b",
    "m-b:1b",
)  # A : deux pistes (3 + 2 lignes), B : think_off (3 lignes), hors référence
T0 = datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _model(tag, tracks):
    return {
        "tag": tag,
        "family": "qwen",
        "tracks": tracks,
        "think_off": False if "think_on" in tracks else None,
        "think_on": True if "think_on" in tracks else None,
        "num_ctx_max": 32768,
    }


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("QUALITY_BENCH_DATA", str(data))
    config_dir = tmp_path / "campaigns_yaml"
    config_dir.mkdir()
    monkeypatch.setattr(paths, "campaign_config_path", lambda c: config_dir / f"{c}.yaml")
    doc = {
        "set": SET_ID,
        "generation": {"models": [_model(A, ["think_off", "think_on"]), _model(B, ["think_off"])]},
    }
    (config_dir / f"{CAMPAIGN}.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    named = questions()
    chosen = sorted((named[n] for n in ("bbeh", "var_math", "piaf")), key=lambda q: q["id"])
    tracks = {
        "think_off": [q["id"] for q in chosen],
        "think_on": [chosen[0]["id"], chosen[1]["id"]],
    }
    rewrite_jsonl(paths.set_questions_path(SET_ID), chosen)
    paths.set_tracks_path(SET_ID).write_bytes(pretty_bytes(tracks))
    # Référence : A seul est connu (3 h think_off sur 3 lignes, 2 h think_on sur 2 lignes).
    baseline = data / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "projection": {
                    "models": [
                        {
                            "tag": A,
                            "known": True,
                            "think_off_hours": 3.0,
                            "think_on_hours": 2.0,
                        },
                        {"tag": "autre", "known": False},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    campaign_dir = paths.campaign_dir(CAMPAIGN)
    campaign_dir.mkdir(parents=True)
    return {"data": data, "baseline": baseline, "dir": campaign_dir}


def _line(index, model, track, status="ok", wall_s=7200.0, at=None):
    at = at or T0 + timedelta(minutes=10 * index)
    return {
        "schema": "qb.generation/1",
        "key": f"{CAMPAIGN}|{model}|{track}|q{index}|0",
        "campaign": CAMPAIGN,
        "model": model,
        "track": track,
        "status": status,
        "wall_s": wall_s,
        "created_at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "output": [{"content": "contenu privé"}],
    }


def _write(env, lines, tail=""):
    text = "".join(json.dumps(line) + "\n" for line in lines) + tail
    (env["dir"] / "generation.jsonl").write_text(text, encoding="utf-8")


def _scenario():
    """A : 3 lignes think_off (7 200 s, prévu 3 600 s) + 1 sur 2 en think_on : ratio 2."""
    lines = [_line(i, A, "think_off") for i in range(3)]
    lines.append(_line(3, A, "think_on", wall_s=7200.0, at=NOW - timedelta(minutes=10)))
    return lines


def _status(env, now=NOW, stall=30.0, cache=None):
    return compute_status(
        CAMPAIGN,
        cache=cache or RowCache(env["dir"] / "generation.jsonl"),
        baseline_path=env["baseline"],
        stall_minutes=stall,
        now=now,
    )


def test_counts_percent_and_states(env):
    _write(env, _scenario())
    status = _status(env)
    overall = status["overall"]
    assert (overall["lines_done"], overall["lines_expected"]) == (4, 8)
    assert overall["percent"] == 50.0
    assert overall["state"] == "running"
    a, b = status["models"]
    assert (a["tag"], a["state"], a["lines_done"], a["lines_expected"]) == (A, "running", 4, 5)
    assert a["percent"] == 80.0
    assert (b["state"], b["lines_done"]) == ("upcoming", 0)
    assert a["wall_h"] == 8.0
    assert a["statuses"] == {"ok": 4}


def test_model_done_when_all_lines_present(env):
    _write(
        env,
        [_line(i, A, "think_off") for i in range(3)]
        + [_line(i + 3, A, "think_on") for i in range(2)],
    )
    assert _status(env)["models"][0]["state"] == "done"


def test_ratio_and_estimated_end(env):
    _write(env, _scenario())
    overall = _status(env)["overall"]
    # réel 8 h pour 4 h prévues sur les mêmes lignes
    assert overall["speed_ratio"] == 2.0
    assert overall["planned_h"] == 8.0
    # restant prévu : 1 ligne think_on (1 h) + B estimé à 1 h par ligne (3 h) = 4 h
    assert overall["eta"] == "2026-10-20T20:00:00+00:00"
    assert overall["initial_end"] == "2026-10-20T08:00:00+00:00"
    assert overall["drift_h"] == 12.0
    assert overall["drift_pct"] == 150.0
    assert overall["elapsed_h"] == 12.0
    assert overall["wall_h"] == 8.0


def test_no_line_means_ratio_one_and_no_eta(env):
    status = _status(env)
    assert status["overall"]["speed_ratio"] == 1.0
    assert status["overall"]["state"] == "not_started"
    assert status["overall"]["eta"] is None
    assert status["overall"]["last_line_age_min"] is None
    assert not any(a["code"] == "stalled" for a in status["alerts"])


def test_model_outside_baseline_is_estimated_by_median(env):
    _write(env, _scenario())
    a, b = _status(env)["models"]
    assert (a["baseline"], b["baseline"]) == ("measured", "estimated")
    assert b["tracks"][0]["baseline"] == "estimated"
    assert b["planned_h"] == 3.0  # 3 lignes x médiane des prévus par ligne de think_off (1 h)


def test_truncated_last_line_and_garbage_are_ignored(env):
    path = env["dir"] / "generation.jsonl"
    lines = _scenario()
    _write(env, lines, tail='{"schema": "qb.generation/1", "key": "mon-test|m-a:1b|th')
    cache = RowCache(path)
    assert len(cache.update()) == 4
    # la ligne finit d'être écrite : relue au passage suivant
    rest = json.dumps(_line(4, A, "think_on"))
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: text.rindex("\n") + 1] + rest + "\n", encoding="utf-8")
    assert len(cache.update()) == 5


def test_duplicate_keys_and_bad_lines_are_skipped(env):
    lines = _scenario()
    _write(env, [*lines, lines[0]], tail="")
    with open(env["dir"] / "generation.jsonl", "a", encoding="utf-8") as handle:
        handle.write("pas du json\n[1]\n")
    assert len(RowCache(env["dir"] / "generation.jsonl").update()) == 4


def test_stalled_alert_and_error_rate(env):
    lines = _scenario()
    lines[-1]["status"] = "context_exceeded"
    lines[-2]["status"] = "error"
    _write(env, lines)
    fresh = _status(env, now=NOW)
    assert not any(a["code"] == "stalled" for a in fresh["alerts"])
    assert fresh["overall"]["error_rate_last50"] == 0.5
    late = _status(env, now=NOW + timedelta(minutes=45), stall=30)
    assert any(a["code"] == "stalled" for a in late["alerts"])
    assert late["overall"]["last_line_age_min"] == 55.0
    assert late["overall"]["statuses"] == {"context_exceeded": 1, "error": 1, "ok": 2}


def test_log_and_lock_and_stop(env):
    (env["dir"] / "log-generate.log").write_text(
        "2026-10-20T11:00:00 WARNING [generate] slm_quality_bench.generation.runner : "
        "k : Ollama ne répond plus, attente du service\n"
        "2026-10-20T11:30:00 INFO [generate] slm_quality_bench.generation.runner : "
        f"{A} : modèle déchargé\n",
        encoding="utf-8",
    )
    _write(env, _scenario())
    (env["dir"] / "STOP").write_text("", encoding="utf-8")
    status = _status(env)
    assert status["log"]["ollama_unresponsive_warnings"] == 1
    assert status["log"]["last_unload"]["model"] == A
    codes = {a["code"] for a in status["alerts"]}
    assert {"ollama_unresponsive", "stop_requested", "generator_stopped"} <= codes
    assert status["generator"] == {"lock_held": False, "stop_requested": True}
    with FileLock(paths.generation_lock_path(CAMPAIGN)):
        assert lock_held(paths.generation_lock_path(CAMPAIGN))
        held = _status(env)
        assert held["generator"]["lock_held"]
        assert "generator_stopped" not in {a["code"] for a in held["alerts"]}
    assert not lock_held(paths.generation_lock_path(CAMPAIGN))


def test_render_text_width_and_content(env):
    _write(env, _scenario())
    text = render_text(_status(env))
    assert max(len(line) for line in text.splitlines()) <= 100
    assert "\033[" not in text  # sans couleur par défaut
    summary, details = text.split("Détail par modèle")
    # Synthèse de direction d'abord : verdict, avancement, fin estimée, dérive, modèle en cours.
    assert "ARRÊTÉE, À VÉRIFIER" in summary  # verrou libre dans le scénario
    assert "50 %" in summary and "4/8 réponses" in summary and "0/2 modèles" in summary
    assert "mar. 20/10 à 20:00" in summary  # fin estimée
    assert "de retard (+150 %)" in summary
    assert f"En cours      {A} (80 %) · ensuite {B}" in summary
    assert f"⏳ {A}" in details and f"⬜ {B}" in details
    assert "contenu privé" not in text


def test_verdict_levels(env):
    _write(env, _scenario())
    status = _status(env)
    on_time = {**status, "alerts": [], "overall": {**status["overall"], "drift_pct": 3.0}}
    late = {**on_time, "overall": {**on_time["overall"], "drift_pct": 12.0}}
    early = {**on_time, "overall": {**on_time["overall"], "drift_pct": -8.0}}
    done = {**on_time, "overall": {**on_time["overall"], "state": "complete"}}
    assert verdict(status)[1].startswith("ARRÊTÉE")
    assert verdict(on_time)[1] == "DANS LES TEMPS"
    assert verdict(late)[1] == "EN RETARD"
    assert verdict(early)[1] == "EN AVANCE"
    assert verdict(done)[1] == "TERMINÉE"


def test_render_text_color_only_adds_ansi(env):
    _write(env, _scenario())
    status = _status(env)
    colored = render_text(status, color=True)
    assert "\033[31;1m" in colored  # verdict rouge et gras
    assert re.sub(r"\x1b\[[0-9;]*m", "", colored) == render_text(status)


def _tree(root: Path):
    return sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*"))


def test_status_is_read_only(env, capsys):
    _write(env, _scenario())
    before = _tree(env["data"])
    for extra in ([], ["--json"]):
        code = commands._run(_args(env, extra))
        assert code == 0
    assert _tree(env["data"]) == before
    assert not paths.generation_lock_path(CAMPAIGN).exists()


def _args(env, extra):
    import argparse

    parser = argparse.ArgumentParser()
    commands._configure(parser)
    return parser.parse_args(["--campaign", CAMPAIGN, "--baseline", str(env["baseline"]), *extra])


def test_cli_json_and_exit_codes(env, capsys):
    from slm_quality_bench.__main__ import main

    _write(env, _scenario())
    assert (
        main(["status", "--campaign", CAMPAIGN, "--baseline", str(env["baseline"]), "--json"]) == 0
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["schema"] == "qb.status/1"
    assert doc["overall"]["lines_done"] == 4
    assert main(["status", "--campaign", "absente"]) == 2
    assert main(["status", "--campaign", "../x"]) == 2
    assert main(["status", "--campaign", CAMPAIGN, "--notify"]) == 2


class Recorder:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def notify(self, title, message):
        if self.fail:
            raise RuntimeError("toast KO")
        self.sent.append((title, message))


def test_watch_notifies_on_transition_and_exits_cleanly(env, monkeypatch, capsys):
    _write(env, _scenario())
    recorder = Recorder()
    monkeypatch.setattr(commands, "make_notifier", lambda: recorder)
    monkeypatch.setattr(commands, "NOW", lambda: NOW)
    calls = []

    def sleep(seconds):
        calls.append(seconds)
        if len(calls) == 1:  # entre deux passages : A finit sa dernière ligne think_on
            path = env["dir"] / "generation.jsonl"
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(_line(4, A, "think_on", wall_s=3600.0)) + "\n")
        if len(calls) == 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(commands, "SLEEP", sleep)
    assert commands._run(_args(env, ["--watch", "60", "--notify"])) == 0
    assert calls == [60.0, 60.0, 60.0]
    titles = [title for title, _ in recorder.sent]
    assert titles.count(f"{CAMPAIGN} : modèle terminé") == 1  # pas de doublon aux passages suivants
    assert all("contenu privé" not in message for _, message in recorder.sent)


def _fake(done=(), complete=False, stalled=False, drift=None, held=True, warnings=0):
    models = [
        {
            "tag": tag,
            "state": "done" if tag in done else "running",
            "lines_done": 1,
            "lines_expected": 1,
            "wall_h": 1.0,
        }
        for tag in (A, B)
    ]
    return {
        "campaign": CAMPAIGN,
        "overall": {
            "complete": complete,
            "percent": 10.0,
            "lines_done": 1,
            "lines_expected": 2,
            "wall_h": 1.0,
            "elapsed_h": 1.0,
            "last_line_age_min": 50.0,
            "drift_pct": drift,
            "drift_h": None if drift is None else drift / 10,
        },
        "models": models,
        "alerts": [{"code": "stalled"}] if stalled else [],
        "generator": {"lock_held": held},
        "log": {"ollama_unresponsive_warnings": warnings},
    }


def test_transitions_first_observation_is_silent_then_each_event_once():
    t = Transitions()
    assert t.events(_fake(stalled=True, warnings=2)) == []
    assert t.events(_fake(stalled=True, warnings=2)) == []
    assert [e[0] for e in t.events(_fake(done=(A,), stalled=True, warnings=2))] == [
        f"{CAMPAIGN} : modèle terminé"
    ]
    assert t.events(_fake(done=(A,), stalled=True, warnings=2)) == []
    assert t.events(_fake(done=(A,), stalled=False, warnings=2)) == []
    assert [e[0] for e in t.events(_fake(done=(A,), stalled=True, warnings=2))] == [
        f"{CAMPAIGN} : campagne bloquée ?"
    ]
    assert [e[0] for e in t.events(_fake(done=(A,), stalled=True, warnings=3))] == [
        f"{CAMPAIGN} : Ollama ne répond plus"
    ]
    assert [e[0] for e in t.events(_fake(done=(A,), stalled=True, warnings=3, held=False))] == [
        f"{CAMPAIGN} : générateur arrêté"
    ]


def test_campaign_complete_does_not_report_generator_stopped():
    t = Transitions()
    t.events(_fake())
    titles = [e[0] for e in t.events(_fake(done=(A, B), complete=True, held=False))]
    assert f"{CAMPAIGN} : campagne terminée" in titles
    assert f"{CAMPAIGN} : générateur arrêté" not in titles


def test_drift_steps():
    assert [drift_level(x) for x in (None, -5, 9.9, 10, 19.9, 20, 35)] == [None, 0, 0, 1, 1, 2, 3]
    t = Transitions()
    assert t.events(_fake(drift=5.0)) == []
    assert t.events(_fake(drift=9.0)) == []
    assert len(t.events(_fake(drift=11.0))) == 1  # franchit +10 %
    assert t.events(_fake(drift=15.0)) == []
    assert len(t.events(_fake(drift=21.0))) == 1  # palier +20 %
    assert t.events(_fake(drift=None)) == []
    assert t.events(_fake(drift=21.0)) == []
    assert t.events(_fake(drift=12.0)) == []  # redescend à 10-20 % sans toast
    assert len(t.events(_fake(drift=21.0))) == 1  # le palier 20 % se refranchit
    back = t.events(_fake(drift=3.0))
    assert len(back) == 1 and "résorbé" in back[0][0]


def test_dispatch_swallows_notifier_failure(caplog):
    dispatch(Recorder(fail=True), [("titre", "texte")])  # ne lève pas


def test_drift_hysteresis_no_toast_storm_around_a_threshold():
    t = Transitions()
    assert t.events(_fake(drift=5.0)) == []
    sent = [t.events(_fake(drift=x)) for x in (11.0, 9.0, 11.0, 8.0, 11.0)]
    assert sum(len(e) for e in sent) == 1  # un seul toast, au premier franchissement
    sent = [t.events(_fake(drift=x)) for x in (21.0, 19.0, 21.0, 16.0, 21.0)]
    assert sum(len(e) for e in sent) == 1
    assert t.events(_fake(drift=14.0)) == []  # 14 + 5 < 20 : palier 1, silencieux
    assert t.events(_fake(drift=6.0)) == []  # 6 + 5 >= 10 : reste au palier 1
    back = t.events(_fake(drift=4.0))
    assert len(back) == 1 and "résorbé" in back[0][0]


def test_local_timestamps_follow_dst_per_instant():
    from slm_quality_bench.monitor.status import _display_tz, _iso

    assert _display_tz(datetime.now().astimezone()) is None
    for moment in (
        datetime(2026, 10, 20, 12, tzinfo=UTC),  # avant le passage à l'heure d'hiver
        datetime(2026, 10, 28, 12, tzinfo=UTC),  # après
    ):
        expected = moment.astimezone().utcoffset()
        assert datetime.fromisoformat(_iso(moment, None)).utcoffset() == expected


def test_watch_survives_a_failing_round(env, monkeypatch, capsys):
    _write(env, _scenario())
    monkeypatch.setattr(commands, "NOW", lambda: NOW)
    real = commands.compute_status
    rounds = []

    def flaky(*args, **kwargs):
        rounds.append(1)
        if len(rounds) == 1:
            raise OSError("disque indisponible")
        return real(*args, **kwargs)

    calls = []

    def sleep(seconds):
        calls.append(seconds)
        if len(calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(commands, "compute_status", flaky)
    monkeypatch.setattr(commands, "SLEEP", sleep)
    assert commands._run(_args(env, ["--watch", "60", "--json"])) == 0
    assert len(rounds) == 2
    assert "Tour de suivi en échec" in capsys.readouterr().err


def test_toast_text_goes_through_env_not_script(monkeypatch):
    from slm_quality_bench.monitor import notify

    seen = {}

    class Done:
        returncode = 0

    def run(cmd, env, **kwargs):
        seen["cmd"], seen["env"] = cmd, env
        return Done()

    monkeypatch.setattr(notify.subprocess, "run", run)
    title, body = "a'<b>&\"$(x)", "c</text><x>"
    notify.ToastNotifier().notify(title, body)
    script = seen["cmd"][-1]
    assert title not in script and body not in script
    assert seen["env"][notify.TITLE_ENV] == title and seen["env"][notify.BODY_ENV] == body
    assert script.count("SecurityElement]::Escape") == 2


# -- Estimation de la fin par usage ------------------------------------------------------------

USAGES = {"think_off": {"a": 12, "b": 12}}


def _rows(usage, count, wall):
    return [{"usage": usage, "wall_s": float(wall)} for _ in range(count)]


def _pair(a_wall, b_wall, count=12):
    return _rows("a", count, a_wall) + _rows("b", count, b_wall)


def _estimate(done, kinds=None, order=None):
    """Paires toutes sur la piste think_off, 24 lignes attendues, prévu 10 s par ligne ;
    ``kinds`` : nature de la référence par modèle (``measured`` par défaut)."""
    tags = order or list(done)
    kinds = kinds or {}
    per_line = {(t, "think_off"): (10.0, kinds.get(t, "measured")) for t in tags}
    expected = {t: {"think_off": 24} for t in tags}
    return estimate_remaining(
        expected, USAGES, per_line, {(t, "think_off"): rows for t, rows in done.items()}
    )


def test_usage_factor_is_median_over_calibrated_pairs():
    # facteurs observés : a 1 puis 2, b 3 puis 6 (médianes 1,5 et 4,5) ; m3 à venir
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60)}
    estimate = _estimate(done, order=["m1", "m2", "m3"])
    assert estimate.remaining_s == pytest.approx(12 * 10 * 1.5 + 12 * 10 * 4.5)
    assert estimate.by_model == {"m1": 0.0, "m2": 0.0, "m3": pytest.approx(720.0)}


def test_running_pair_uses_remaining_usage_blocks_and_shrinks_its_own_factor():
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60), "m3": _rows("a", 12, 30)}
    estimate = _estimate(done)
    # m3 a fait ses 12 lignes « a » à 2 fois le facteur ; reste 12 lignes « b » (4,5 × 10 s),
    # facteur propre c = 2 rétréci : (12 × 2 + 50) / (12 + 50)
    shrunk = (12 * 2 + 50) / 62
    assert estimate.by_model["m3"] == pytest.approx(12 * 45 * shrunk)
    # un usage déjà vu sur 10 lignes ou plus se fie à sa moyenne observée
    done["m3"] = _rows("a", 11, 40)
    own = 11 * 40 / (11 * 15)
    shrunk = (11 * own + 50) / (11 + 50)
    assert _estimate(done).by_model["m3"] == pytest.approx(1 * 40 + 12 * 45 * shrunk)


def test_estimated_pairs_do_not_calibrate():
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60), "e": _pair(1000, 5000)}
    estimate = _estimate(done, kinds={"e": "estimated"}, order=["m1", "m2", "e", "m3"])
    assert estimate.by_model["m3"] == pytest.approx(720.0)
    assert estimate.by_model["e"] == 0.0


def test_estimated_pair_in_progress_uses_median_of_finished_pairs():
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60), "e": _rows("a", 12, 15)}
    estimate = _estimate(done, kinds={"e": "estimated"}, order=["m1", "m2", "e"])
    # moyenne par ligne des paires terminées : 20 et 40 (médiane 30) ; F vaut 1,5 (a) et 4,5 (b),
    # moyenne 3 : a vaut 30 × 1,5 / 3 = 15 (comme observé, facteur propre 1), b vaut 45
    assert estimate.by_model["e"] == pytest.approx(12 * 45)


def test_range_is_null_below_three_observed_pairs_and_brackets_eta_above():
    two = _estimate({"m1": _pair(10, 30), "m2": _pair(20, 60)}, order=["m1", "m2", "m3"])
    assert two.low_s is None and two.high_s is None
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60), "m3": _pair(40, 90)}
    three = _estimate(done, order=["m1", "m2", "m3", "m4"])
    assert three.low_s is not None and three.high_s is not None
    assert three.low_s < three.remaining_s < three.high_s


def test_running_pair_does_not_calibrate_usage_factors():
    # m3 en cours n'a vu que ses lignes « a », très rapides : F des paires à venir n'en dépend pas
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60), "m3": _rows("a", 12, 1)}
    estimate = _estimate(done, order=["m1", "m2", "m3", "m4"])
    assert estimate.by_model["m4"] == pytest.approx(720.0)


def test_range_comes_from_held_out_pairs():
    # facteurs 1, 2 et 4 sur les deux usages ; chaque paire prévue par la médiane des deux autres :
    # 1/3, 2/2,5 et 4/1,5, quartiles inclusifs 0,5667 et 1,7333 ; m4 à venir : 24 × 10 s × 2
    done = {"m1": _pair(10, 10), "m2": _pair(20, 20), "m3": _pair(40, 40)}
    estimate = _estimate(done, order=["m1", "m2", "m3", "m4"])
    assert estimate.remaining_s == pytest.approx(480.0)
    assert estimate.low_s == pytest.approx(480.0 * (1 / 3 + 0.8) / 2)
    assert estimate.high_s == pytest.approx(480.0 * (0.8 + 4 / 1.5) / 2)


def test_range_of_running_pair_is_attenuated_by_its_own_lines():
    done = {"m1": _pair(10, 10), "m2": _pair(20, 20), "m3": _pair(40, 40), "m4": _rows("a", 2, 20)}
    estimate = _estimate(done)
    weight = 50 / (2 + 50)  # part du reste de m4 qui dépend encore de F
    low = (1 / 3 + 0.8) / 2
    assert estimate.low_s == pytest.approx(estimate.remaining_s * (1 + (low - 1) * weight))
    assert estimate.low_s < estimate.remaining_s < estimate.high_s


def test_rest_override_is_an_exact_horizon():
    done = {"m1": _pair(10, 30), "m2": _pair(20, 60)}
    tags = ["m1", "m2", "m3", "m4"]
    per_line = {(t, "think_off"): (10.0, "measured") for t in tags}
    expected = {t: {"think_off": 24} for t in tags}
    rows = {(t, "think_off"): r for t, r in done.items()}
    horizon = {("m3", "think_off"): {"a": 2}}  # m4 absent : hors horizon
    estimate = estimate_remaining(expected, USAGES, per_line, rows, rest_override=horizon)
    assert estimate.remaining_s == pytest.approx(2 * 10 * 1.5)
    assert estimate.by_model["m4"] == 0.0


def test_track_without_any_reference_borrows_other_tracks():
    # aucune référence ni ligne en think_on : prévu non nul (références de think_off), donc une
    # fin estimée après maintenant plutôt qu'un reste nul
    expected = {"m1": {"think_off": 2, "think_on": 2}}
    baseline = {"m1": {"think_off": 1.0}}
    per_line = _per_line_seconds(expected, baseline, {})
    assert per_line[("m1", "think_on")] == (1800.0, "estimated")


def test_status_json_fields_and_eta_from_remaining(env):
    _write(env, _scenario())
    status = _status(env)
    overall = status["overall"]
    assert overall["eta_method"] == "per_usage"
    assert overall["eta_low"] is None and overall["eta_high"] is None  # moins de 3 paires
    assert overall["remaining_h"] == 8.0  # ``eta`` : maintenant + 8 h
    by_model = {m["tag"]: m["remaining_h"] for m in status["models"]}
    assert by_model == {A: 2.0, B: 6.0}
    complete = _status(env, cache=RowCache(env["dir"] / "none.jsonl"))
    assert complete["overall"]["eta_low"] is None


def test_plan_gives_expected_lines_per_usage(env):
    _, expected, usages = expected_lines(CAMPAIGN)
    assert expected[A] == {"think_off": 3, "think_on": 2}
    assert sum(usages["think_off"].values()) == 3 and sum(usages["think_on"].values()) == 2


def test_usage_falls_back_to_question_id_prefix(env, tmp_path):
    line = _line(0, A, "think_off")
    line["key"] = f"{CAMPAIGN}|{A}|think_off|rag/piaf/0027|0"
    _write(env, [line])
    assert RowCache(env["dir"] / "generation.jsonl").update()[0]["usage"] == "rag"


def test_render_text_shows_range_and_remaining_per_model(env):
    _write(env, _scenario())
    status = _status(env)
    status["overall"]["eta_low"] = "2026-10-20T18:00:00+00:00"
    status["overall"]["eta_high"] = "2026-10-21T02:00:00+00:00"
    text = render_text(status)
    assert "entre mar. 20/10 à 18:00 et mer. 21/10 à 02:00" in text
    assert "~6 h 00" in text and "~2 h 00" in text
    assert max(len(line) for line in text.splitlines()) <= 100
