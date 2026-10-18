"""Mémoire de la machine pendant la génération (AD-7, AD-14) : RAM système et VRAM de la carte.

Le banc mesure ce qu'un modèle coûte à la machine qui sert aussi à autre chose (bureautique) :
- **RAM** : mémoire physique utilisée de la machine entière (total moins disponible), en MiB.
  Windows : ``GlobalMemoryStatusEx`` (ctypes) ; Linux : ``/proc/meminfo`` ; autres systèmes :
  valeur nulle (aucune mesure, sans erreur).
- **VRAM** : ``memory.total`` et ``memory.used`` de ``nvidia-smi`` (somme des cartes), par le
  point d'injection ``gpu.RUN``. ``nvidia-smi`` absent ou illisible, ou ``[N/A]`` : valeur nulle.
- **Puissance du GPU** (W, somme des cartes) : ``power.draw``, lu dans la même commande que la
  VRAM ; s'il vaut ``[N/A]`` (pilote WDDM de la tour, 610.62), ``Avg`` du bloc « Power Samples »
  de ``nvidia-smi -q -d POWER`` (moyenne glissante du pilote sur ~4 min), relu au plus toutes les
  ``POWER_SAMPLES_EVERY_S`` secondes. Source notée (``power.draw`` ou ``power_samples_avg``).
  Valeur non validée tant qu'elle ne varie pas sous charge (46,3 W constants au repos relevés
  sur la tour le 2026-10-18).

Ce sont des mesures de la machine entière, pas du seul modèle : la mesure de référence, prise
juste avant le chargement du modèle (machine au repos), sert à isoler son apport (pointe moins
référence). Précision : échantillonnage toutes les ``INTERVAL_S`` secondes, donc une pointe plus
brève que l'intervalle peut échapper ; la mémoire d'autres programmes fait varier la pointe.

``MemorySampler`` échantillonne dans un fil de fond. Rien ici ne lève : une sonde en échec
donne des valeurs nulles et un avertissement journalisé une seule fois, jamais un échec de la
génération.
"""

from __future__ import annotations

import ctypes
import logging
import math
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import gpu

logger = logging.getLogger(__name__)

INTERVAL_S = 2.0
POWER_SAMPLES_EVERY_S = 10.0
SOURCE_DRAW = "power.draw"
SOURCE_SAMPLES = "power_samples_avg"
_MIB = 1024 * 1024


@dataclass(frozen=True)
class Reading:
    """Une lecture (MiB) ; ``None`` pour une valeur indisponible."""

    ram_total: int | None = None
    ram_used: int | None = None
    vram_total: int | None = None
    vram_used: int | None = None
    gpu_power_w: float | None = None
    gpu_power_source: str | None = None


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("sullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def _ram_windows() -> tuple[int, int] | None:
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return status.ullTotalPhys // _MIB, (status.ullTotalPhys - status.ullAvailPhys) // _MIB


def _ram_linux() -> tuple[int, int] | None:
    values: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            name, _, rest = line.partition(":")
            values[name] = int(rest.split()[0])  # ko
    total, available = values["MemTotal"], values["MemAvailable"]
    return total // 1024, (total - available) // 1024


def read_ram() -> tuple[int | None, int | None]:
    """``(total, utilisée)`` en MiB, ``(None, None)`` si le système n'est pas géré ou en cas
    d'erreur."""
    try:
        if sys.platform == "win32":
            found = _ram_windows()
        elif sys.platform.startswith("linux"):
            found = _ram_linux()
        else:
            found = None
    except Exception:  # noqa: BLE001 (la mesure ne doit jamais faire échouer la génération)
        found = None
    return found if found is not None else (None, None)


def _watts(text: str) -> float | None:
    """``46.30`` ou ``46.30 W`` en watts ; ``None`` pour ``[N/A]`` ou toute valeur illisible."""
    text = text.strip().removesuffix("W").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def read_gpu() -> tuple[int | None, int | None, float | None]:
    """``(VRAM totale, VRAM utilisée, power.draw)`` de toutes les cartes en une commande
    ``nvidia-smi`` ; chaque valeur est nulle si une carte la rend inconnue."""
    try:
        lines = gpu._nvidia_smi(["nvidia-smi", "--query-gpu=memory.total,memory.used,power.draw"])
    except Exception:  # noqa: BLE001
        return None, None, None
    if not lines:
        return None, None, None
    vram: tuple[int, int] | None = (0, 0)
    power: float | None = 0.0
    for line in lines:
        parts = line.split(",")
        if len(parts) != 3:
            return None, None, None
        try:
            card_total, card_used = gpu._mib(parts[0]), gpu._mib(parts[1])
        except ValueError:
            card_total = card_used = None
        if vram is not None and card_total is not None and card_used is not None:
            vram = (vram[0] + card_total, vram[1] + card_used)
        else:
            vram = None
        card_power = _watts(parts[2])
        power = None if power is None or card_power is None else power + card_power
    total, used = vram if vram is not None else (None, None)
    return total, used, power


def read_vram() -> tuple[int | None, int | None]:
    """``(total, utilisée)`` en MiB de toutes les cartes NVIDIA, ``(None, None)`` si
    ``nvidia-smi`` ne répond pas ou rend une valeur inconnue."""
    total, used, _ = read_gpu()
    return total, used


def parse_power_samples(text: str) -> float | None:
    """Somme des ``Avg`` des blocs « Power Samples » de ``nvidia-smi -q -d POWER`` (un par
    carte) ; ``None`` sans bloc ou si une carte n'a pas de moyenne lisible."""
    averages: list[float | None] = []
    block_indent: int | None = None
    found: float | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        indent = len(raw) - len(raw.lstrip())
        if block_indent is not None and indent <= block_indent:
            averages.append(found)
            block_indent = None
        if stripped == "Power Samples":
            block_indent, found = indent, None
        elif block_indent is not None:
            name, _, value = stripped.partition(":")
            if name.strip() == "Avg":
                found = _watts(value)
    if block_indent is not None:
        averages.append(found)
    known = [value for value in averages if value is not None]
    if not averages or len(known) != len(averages):
        return None
    return sum(known)


def read_power_samples() -> float | None:
    """``Avg`` des « Power Samples » de ``nvidia-smi -q -d POWER`` ; ``None`` en cas d'erreur."""
    try:
        result = gpu.RUN(  # noqa: S603 (commande fixe, sans shell)
            ["nvidia-smi", "-q", "-d", "POWER"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=gpu.TIMEOUT_S,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    return parse_power_samples(result.stdout or "")


class SystemProbe:
    """Sonde de la machine : RAM, puis VRAM et ``power.draw`` en une commande ; à défaut de
    ``power.draw``, moyenne des « Power Samples », relue au plus toutes les ``every_s``
    secondes (valeur gardée entre deux relectures). Rien ici ne lève."""

    def __init__(
        self,
        *,
        every_s: float = POWER_SAMPLES_EVERY_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.every_s = every_s
        self._clock = clock
        self._samples_at: float | None = None
        self._samples_w: float | None = None

    def __call__(self) -> Reading:
        ram_total, ram_used = read_ram()
        vram_total, vram_used, power = read_gpu()
        source = SOURCE_DRAW if power is not None else None
        if power is None and vram_total is not None:  # nvidia-smi répond, sans power.draw
            now = self._clock()
            if self._samples_at is None or now - self._samples_at >= self.every_s:
                self._samples_at = now
                self._samples_w = read_power_samples()
            power = self._samples_w
            source = SOURCE_SAMPLES if power is not None else None
        return Reading(ram_total, ram_used, vram_total, vram_used, power, source)


system_probe = SystemProbe()


def _peak(current: int | None, value: int | None) -> int | None:
    if value is None:
        return current
    return value if current is None else max(current, value)


class MemorySampler:
    """Référence puis échantillons : ``baseline()`` avant le chargement du modèle, ``start()``
    (fil de fond) pendant qu'il tourne, ``stop()`` à son déchargement, ``summary()`` ensuite.

    ``probe`` rend un ``Reading`` ; ``wait(interval)`` bloque jusqu'au prochain échantillon et
    rend ``True`` quand il faut s'arrêter (par défaut : attente d'un événement d'arrêt, que les
    tests remplacent par une fausse horloge)."""

    def __init__(
        self,
        probe: Callable[[], Reading],
        *,
        interval_s: float = INTERVAL_S,
        wait: Callable[[float], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._clock = clock
        self._sampled_at: float | None = None
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._warned = False
        self._tier: int | None = None
        self.samples = 0
        self.base = Reading()
        self.ram_total: int | None = None
        self.vram_total: int | None = None
        self.ram_peak: int | None = None
        self.vram_peak: int | None = None
        self.tiers: dict[int, dict[str, Any]] = {}
        self._reset_power()

    def _reset_power(self) -> None:
        self.power_source: str | None = None
        self.power_samples = 0
        self.power_sum = 0.0
        self.power_max: float | None = None
        self.energy_wh = 0.0

    def _read(self) -> Reading | None:
        try:
            return self._probe()
        except Exception as exc:  # noqa: BLE001
            if not self._warned:
                self._warned = True
                logger.warning(
                    "Mesure de la mémoire en échec (%s) : valeurs nulles", type(exc).__name__
                )
            return None

    def baseline(self) -> None:
        reading = self._read()
        if reading is not None:
            self.base = reading
            self.ram_total = reading.ram_total
            self.vram_total = reading.vram_total

    def set_tier(self, num_ctx: int) -> None:
        """Palier en cours ; un changement déclenche un échantillon, pour que chaque palier en
        ait au moins un."""
        with self._lock:
            changed = self._tier != num_ctx
            self._tier = num_ctx
        if changed:
            self.sample()

    def sample(self) -> None:
        reading = self._read()
        if reading is None:
            return
        with self._lock:
            now = self._clock()
            elapsed = 0.0 if self._sampled_at is None else max(now - self._sampled_at, 0.0)
            self._sampled_at = now
            self.samples += 1
            if reading.gpu_power_w is not None:
                # Énergie : puissance lue × temps écoulé depuis l'échantillon précédent.
                self.power_source = reading.gpu_power_source
                self.power_samples += 1
                self.power_sum += reading.gpu_power_w
                self.power_max = max(self.power_max or 0.0, reading.gpu_power_w)
                self.energy_wh += reading.gpu_power_w * elapsed / 3600
            if reading.ram_total is not None:
                self.ram_total = reading.ram_total
            if reading.vram_total is not None:
                self.vram_total = reading.vram_total
            self.ram_peak = _peak(self.ram_peak, reading.ram_used)
            self.vram_peak = _peak(self.vram_peak, reading.vram_used)
            if self._tier is not None:
                tier = self.tiers.setdefault(
                    self._tier,
                    {
                        "num_ctx": self._tier,
                        "samples": 0,
                        "ram_peak_mib": None,
                        "vram_peak_mib": None,
                    },
                )
                tier["samples"] += 1
                tier["ram_peak_mib"] = _peak(tier["ram_peak_mib"], reading.ram_used)
                tier["vram_peak_mib"] = _peak(tier["vram_peak_mib"], reading.vram_used)

    def _loop(self) -> None:
        while not self._wait(self.interval_s):
            self.sample()

    def start(self) -> None:
        self.sample()  # un premier échantillon aussitôt
        self._thread = threading.Thread(target=self._loop, name="memory-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Arrête le fil et prend un dernier échantillon, sauf si le fil est encore bloqué dans
        une sonde (``nvidia-smi`` qui ne répond pas) : pas de seconde attente de la sonde."""
        self._stop.set()
        stuck = False
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s + 1)
            stuck = self._thread.is_alive()
            self._thread = None
        if not stuck:
            self.sample()  # dernier échantillon, à la fin du déchargement

    def checkpoint(self) -> dict[str, Any]:
        """Résumé du segment écoulé (comme ``summary``), puis remise à zéro des échantillons, des
        pointes et des paliers : le segment suivant ne compte que ses propres échantillons et n'a
        plus de référence (nulle), pour que des segments consignés l'un après l'autre se
        cumulent sans double compte (échantillons sommés, pointes au maximum, référence au
        minimum des valeurs connues)."""
        with self._lock:
            summary = self._summary()
            self.samples = 0
            self.ram_peak = self.vram_peak = None
            self.tiers = {}
            self.base = Reading()
            self._reset_power()
        return summary

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return self._summary()

    def _summary(self) -> dict[str, Any]:
        return {
            "samples": self.samples,
            "interval_s": self.interval_s,
            "ram_total_mib": self.ram_total,
            "ram_baseline_mib": self.base.ram_used,
            "ram_peak_mib": self.ram_peak,
            "vram_total_mib": self.vram_total,
            "vram_baseline_mib": self.base.vram_used,
            "vram_peak_mib": self.vram_peak,
            "tiers": [self.tiers[key] for key in sorted(self.tiers)],
            "gpu_power_source": self.power_source,
            "gpu_power_avg_w": (
                round(self.power_sum / self.power_samples, 2) if self.power_samples else None
            ),
            "gpu_power_max_w": round(self.power_max, 2) if self.power_max is not None else None,
            "gpu_power_samples": self.power_samples,
            "gpu_energy_wh": round(self.energy_wh, 4) if self.power_samples else None,
        }
