"""Mémoire de la machine (``common/memory.py``) : sondes simulées, échantillonneur sans attente
réelle (fausse horloge), pointes, repli en cas d'erreur et schéma ``qb.memory/1``."""

from __future__ import annotations

import logging
import subprocess

import pytest

from slm_quality_bench.common import gpu, memory
from slm_quality_bench.common.memory import MemorySampler, Reading
from slm_quality_bench.common.schemas import SchemaValidationError, validate

from .gpu_fakes import FakeSmi


class Probe:
    """Sonde simulée : rend les lectures dans l'ordre (la dernière reste) ou lève."""

    def __init__(self, readings):
        self.readings = list(readings)
        self.calls = 0

    def __call__(self):
        item = self.readings[min(self.calls, len(self.readings) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return item


def _reading(ram, vram):
    return Reading(ram_total=32768, ram_used=ram, vram_total=8192, vram_used=vram)


def fake_wait(ticks):
    """Fausse attente : ``ticks`` échantillons de fond, puis l'arrêt (sans dormir)."""
    state = {"n": 0, "intervals": []}

    def wait(interval):
        state["intervals"].append(interval)
        state["n"] += 1
        return state["n"] > ticks

    wait.state = state
    return wait


def test_peaks_baseline_and_tiers():
    probe = Probe([_reading(10000, 400), _reading(12000, 3000), _reading(20000, 7000)])
    wait = fake_wait(1)
    sampler = MemorySampler(probe, interval_s=2.0, wait=wait)
    sampler.baseline()
    sampler.set_tier(4096)
    sampler.start()  # après set_tier (12000/3000), start (20000/7000), fil : échantillon 2 (20000/7000)
    sampler._thread.join(timeout=5)
    sampler.set_tier(8192)
    sampler.stop()  # échantillon final (reste 20000/7000)
    summary = sampler.summary()
    assert summary["samples"] == 5
    assert summary["ram_baseline_mib"] == 10000 and summary["vram_baseline_mib"] == 400
    assert summary["ram_peak_mib"] == 20000 and summary["vram_peak_mib"] == 7000
    assert summary["ram_total_mib"] == 32768 and summary["vram_total_mib"] == 8192
    assert wait.state["intervals"] == [2.0, 2.0]
    assert summary["tiers"] == [
        {"num_ctx": 4096, "samples": 3, "ram_peak_mib": 20000, "vram_peak_mib": 7000},
        {"num_ctx": 8192, "samples": 2, "ram_peak_mib": 20000, "vram_peak_mib": 7000},
    ]


def test_probe_failure_gives_null_values_and_one_warning(caplog):
    sampler = MemorySampler(Probe([RuntimeError("boum")]), wait=fake_wait(0))
    with caplog.at_level(logging.WARNING):
        sampler.baseline()
        sampler.start()
        sampler.stop()
    summary = sampler.summary()
    assert summary["samples"] == 0
    assert summary["ram_peak_mib"] is None and summary["vram_baseline_mib"] is None
    assert len([r for r in caplog.records if "Mesure de la mémoire" in r.message]) == 1


def test_unknown_values_keep_other_peak():
    probe = Probe([Reading(), Reading(ram_total=100, ram_used=60), Reading(ram_total=100)])
    sampler = MemorySampler(probe, wait=fake_wait(0))
    sampler.baseline()
    sampler.start()
    sampler.stop()
    summary = sampler.summary()
    assert summary["ram_peak_mib"] == 60 and summary["vram_peak_mib"] is None
    assert summary["ram_baseline_mib"] is None


def test_read_vram_sums_cards(monkeypatch):
    monkeypatch.setattr(gpu, "RUN", FakeSmi(used=[300, 200]))
    assert memory.read_vram() == (16384, 500)


@pytest.mark.parametrize(
    "smi",
    [
        FakeSmi(error=FileNotFoundError()),
        FakeSmi(error=subprocess.TimeoutExpired("nvidia-smi", 10)),
        FakeSmi(returncode=9),
        FakeSmi(used=[]),
    ],
)
def test_read_vram_unavailable_is_null(monkeypatch, smi):
    monkeypatch.setattr(gpu, "RUN", smi)
    assert memory.read_vram() == (None, None)


def test_read_vram_unknown_value_is_null(monkeypatch):
    smi = FakeSmi(used=[300])
    smi.total = "[N/A]"
    monkeypatch.setattr(gpu, "RUN", smi)
    assert memory.read_vram() == (None, None)


def test_read_ram_unsupported_system_is_null(monkeypatch):
    monkeypatch.setattr(memory.sys, "platform", "darwin")
    assert memory.read_ram() == (None, None)


def test_read_ram_error_is_null(monkeypatch):
    monkeypatch.setattr(memory.sys, "platform", "linux")
    monkeypatch.setattr(memory, "_ram_linux", lambda: 1 / 0)
    assert memory.read_ram() == (None, None)


def test_read_ram_real_system_is_plausible():
    total, used = memory.read_ram()
    if total is not None:  # Windows ou Linux
        assert used is not None and 0 < used <= total


def test_memory_schema_is_closed():
    record = {
        "schema": "qb.memory/1",
        "key": "c|m|0",
        "manifest": "a" * 64,
        "campaign": "c",
        "model": "m",
        "samples": 2,
        "interval_s": 2.0,
        "ram_total_mib": 32768,
        "ram_baseline_mib": 10000,
        "ram_peak_mib": 20000,
        "vram_total_mib": None,
        "vram_baseline_mib": None,
        "vram_peak_mib": None,
        "tiers": [{"num_ctx": 4096, "samples": 2, "ram_peak_mib": 20000, "vram_peak_mib": None}],
        "gpu_power_source": "power_samples_avg",
        "gpu_power_avg_w": 46.3,
        "gpu_power_max_w": 46.3,
        "gpu_power_samples": 2,
        "gpu_energy_wh": 0.0257,
        "created_at": "2026-10-18T10:00:00Z",
    }
    validate(record)
    validate({**record, "gpu_power_source": None, "gpu_power_avg_w": None, "gpu_energy_wh": None})
    with pytest.raises(SchemaValidationError):
        validate({**record, "extra": 1})
    with pytest.raises(SchemaValidationError):
        validate({**record, "gpu_power_source": "power.draw.average"})


def test_checkpoint_returns_the_segment_then_resets_it():
    probe = Probe([_reading(10000, 400), _reading(12000, 3000), _reading(11000, 2000)])
    sampler = MemorySampler(probe, wait=fake_wait(0))
    sampler.baseline()
    sampler.set_tier(4096)  # 12000/3000
    first = sampler.checkpoint()
    assert (first["samples"], first["ram_baseline_mib"], first["ram_peak_mib"]) == (1, 10000, 12000)
    assert [t["num_ctx"] for t in first["tiers"]] == [4096]
    sampler.sample()  # 11000/2000, même palier
    second = sampler.checkpoint()
    assert (second["samples"], second["ram_baseline_mib"], second["ram_peak_mib"]) == (
        1,
        None,
        11000,
    )
    assert second["vram_peak_mib"] == 2000 and second["ram_total_mib"] == 32768
    assert second["tiers"] == [
        {"num_ctx": 4096, "samples": 1, "ram_peak_mib": 11000, "vram_peak_mib": 2000}
    ]
    assert first["tiers"][0]["ram_peak_mib"] == 12000  # le segment rendu n'est plus modifié


def test_stop_skips_the_final_probe_when_the_thread_is_stuck():
    import threading

    release = threading.Event()
    calls = {"n": 0}

    def probe():
        calls["n"] += 1
        if calls["n"] == 2:  # échantillon du fil de fond : nvidia-smi bloqué
            release.wait(5)
        return _reading(10000, 400)

    sampler = MemorySampler(probe, interval_s=0.01)
    sampler.start()
    while calls["n"] < 2:
        pass
    sampler.stop()
    assert calls["n"] == 2  # pas de dernière sonde dans le fil principal
    release.set()


# --- Puissance du GPU ------------------------------------------------------------------------

# Bloc relevé sur la tour (pilote 610.62, RTX 3050), 2026-10-18.
POWER_Q = """
==============NVSMI LOG==============

Attached GPUs                             : 1
GPU 00000000:01:00.0
    GPU Power Readings
        Average Power Draw                : N/A
        Instantaneous Power Draw          : N/A
        Current Power Limit               : 70.00 W
    Power Samples
        Duration                          : 235.19 sec
        Number of Samples                 : 119
        Max                               : 46.30 W
        Min                               : 46.30 W
        Avg                               : 46.30 W
    GPU Memory Power Readings
        Average Power Draw                : N/A
"""


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_power_draw_numeric_is_read_in_the_same_command(monkeypatch):
    smi = FakeSmi(used=[3000, 1000])
    smi.power = ["42.50", "10.00"]
    monkeypatch.setattr(gpu, "RUN", smi)
    reading = memory.SystemProbe()()
    assert (reading.vram_used, reading.gpu_power_w, reading.gpu_power_source) == (
        4000,
        52.5,
        "power.draw",
    )
    assert len(smi.commands) == 1  # une seule commande nvidia-smi par échantillon


def test_power_samples_avg_when_power_draw_is_na_read_every_10_s(monkeypatch):
    smi = FakeSmi(used=[3000])
    smi.power_query = POWER_Q
    monkeypatch.setattr(gpu, "RUN", smi)
    clock = Clock()
    probe = memory.SystemProbe(clock=clock)
    first = probe()
    assert (first.vram_used, first.gpu_power_w, first.gpu_power_source) == (
        3000,
        46.3,
        "power_samples_avg",
    )
    clock.now = 2.0
    assert probe().gpu_power_w == 46.3  # valeur gardée, pas de relecture
    queried = [c for c in smi.commands if c[1:] == ["-q", "-d", "POWER"]]
    assert len(queried) == 1
    clock.now = 10.0
    probe()
    assert len([c for c in smi.commands if c[1:] == ["-q", "-d", "POWER"]]) == 2


@pytest.mark.parametrize(
    "power_query",
    ["", POWER_Q.replace("Avg                               : 46.30 W", "Avg : N/A"), "bruit"],
)
def test_power_all_na_is_null(monkeypatch, power_query):
    smi = FakeSmi(used=[3000])
    smi.power_query = power_query
    monkeypatch.setattr(gpu, "RUN", smi)
    reading = memory.SystemProbe()()
    assert reading.vram_used == 3000
    assert (reading.gpu_power_w, reading.gpu_power_source) == (None, None)


def test_power_query_failure_is_null_and_nvidia_smi_absent_skips_it(monkeypatch):
    smi = FakeSmi(used=[3000])
    monkeypatch.setattr(gpu, "RUN", smi)

    def failing(command, **kwargs):
        if command[1:] == ["-q", "-d", "POWER"]:
            raise subprocess.TimeoutExpired("nvidia-smi", 10)
        return smi(command, **kwargs)

    monkeypatch.setattr(gpu, "RUN", failing)
    assert memory.SystemProbe()().gpu_power_w is None
    absent = FakeSmi(error=FileNotFoundError())
    monkeypatch.setattr(gpu, "RUN", absent)
    reading = memory.SystemProbe()()
    assert (reading.vram_used, reading.gpu_power_w, reading.gpu_power_source) == (None,) * 3
    assert all(c[1:] != ["-q", "-d", "POWER"] for c in absent.commands)


def test_parse_power_samples_sums_cards():
    two = POWER_Q + POWER_Q.split("GPU 00000000:01:00.0", 1)[1].replace("46.30 W", "10.00 W")
    assert memory.parse_power_samples(two) == pytest.approx(56.3)
    assert memory.parse_power_samples("    Power Samples\n        Avg : 12.5 W\n") == 12.5


def test_sampler_power_average_max_and_energy():
    def reading(power, source="power.draw"):
        return Reading(32768, 10000, 8192, 500, power, source if power is not None else None)

    clock = Clock()
    probe = Probe([reading(40.0), reading(60.0), reading(None)])
    sampler = MemorySampler(probe, wait=fake_wait(0), clock=clock)
    sampler.sample()  # t = 0 : 40 W, aucun temps écoulé
    clock.now = 1800.0
    sampler.sample()  # 60 W pendant 1 800 s : 30 Wh
    clock.now = 3600.0
    sampler.sample()  # sans puissance
    summary = sampler.summary()
    assert summary["gpu_power_source"] == "power.draw"
    assert (summary["gpu_power_avg_w"], summary["gpu_power_max_w"]) == (50.0, 60.0)
    assert summary["gpu_power_samples"] == 2
    assert summary["gpu_energy_wh"] == 30.0
    reset = sampler.checkpoint() and sampler.summary()
    assert reset["gpu_power_samples"] == 0
    assert reset["gpu_power_avg_w"] is None and reset["gpu_energy_wh"] is None


def test_sampler_without_power_gives_null_fields():
    sampler = MemorySampler(Probe([_reading(10000, 400)]), wait=fake_wait(0))
    sampler.sample()
    summary = sampler.summary()
    assert summary["gpu_power_source"] is None and summary["gpu_power_samples"] == 0
    assert summary["gpu_power_max_w"] is None and summary["gpu_energy_wh"] is None
