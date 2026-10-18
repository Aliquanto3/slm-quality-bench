"""Mémoire de la machine pendant la génération (AD-7, AD-14) : RAM système et VRAM de la carte.

Le banc mesure ce qu'un modèle coûte à la machine qui sert aussi à autre chose (bureautique) :
- **RAM** : mémoire physique utilisée de la machine entière (total moins disponible), en MiB.
  Windows : ``GlobalMemoryStatusEx`` (ctypes) ; Linux : ``/proc/meminfo`` ; autres systèmes :
  valeur nulle (aucune mesure, sans erreur).
- **VRAM** : ``memory.total`` et ``memory.used`` de ``nvidia-smi`` (somme des cartes), par le
  point d'injection ``gpu.RUN``. ``nvidia-smi`` absent ou illisible, ou ``[N/A]`` : valeur nulle.

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
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import gpu

logger = logging.getLogger(__name__)

INTERVAL_S = 2.0
_MIB = 1024 * 1024


@dataclass(frozen=True)
class Reading:
    """Une lecture (MiB) ; ``None`` pour une valeur indisponible."""

    ram_total: int | None = None
    ram_used: int | None = None
    vram_total: int | None = None
    vram_used: int | None = None


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


def read_vram() -> tuple[int | None, int | None]:
    """``(total, utilisée)`` en MiB de toutes les cartes NVIDIA, ``(None, None)`` si
    ``nvidia-smi`` ne répond pas ou rend une valeur inconnue."""
    try:
        lines = gpu._nvidia_smi(["nvidia-smi", "--query-gpu=memory.total,memory.used"])
        total = used = 0
        for line in lines:
            total_text, used_text = line.split(",", 1)
            card_total, card_used = gpu._mib(total_text), gpu._mib(used_text)
            if card_total is None or card_used is None:
                return None, None
            total += card_total
            used += card_used
    except Exception:  # noqa: BLE001
        return None, None
    return (total, used) if lines else (None, None)


def system_probe() -> Reading:
    ram_total, ram_used = read_ram()
    vram_total, vram_used = read_vram()
    return Reading(ram_total, ram_used, vram_total, vram_used)


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
    ) -> None:
        self._probe = probe
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
            self.samples += 1
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
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_s + 5)
            self._thread = None
        self.sample()  # dernier échantillon, à la fin du déchargement

    def summary(self) -> dict[str, Any]:
        with self._lock:
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
            }
