"""Télémétries des bibliothèques coupées avant leur import (AD-1, AD-15).

Copie réduite de ``src/core/telemetry.py`` du projet d'origine, wavelocalai
(https://github.com/Aliquanto3/wavelocalai, même auteur, licence Apache-2.0) : seules les
variables utiles au banc sont reprises, celles de Hugging Face (importeurs des jeux publics) et
la convention commune ``DO_NOT_TRACK``.

Chaque bibliothèque lit sa variable au moment de son import : ``disable_telemetry()`` doit donc
s'exécuter avant. Appelants : ``__main__.py`` (en tête de la CLI) et chaque module qui importe
une bibliothèque à télémétrie, juste avant cet import (``questions/importers/remote.py`` ;
``tests/test_telemetry.py`` le vérifie).

Une valeur déjà définie, dans l'environnement ou dans le ``.env`` (lu ici d'abord, sans rien
écraser), l'emporte : c'est ainsi qu'on réactive volontairement une télémétrie.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Variable → valeur qui coupe la télémétrie.
TELEMETRY_OPT_OUTS: dict[str, str] = {
    "HF_HUB_DISABLE_TELEMETRY": "1",
    # Convention commune, lue par plusieurs bibliothèques (dont huggingface_hub).
    "DO_NOT_TRACK": "1",
}


def disable_telemetry(dotenv_path: str | Path | None = None) -> None:
    """Coupe les télémétries connues, sans écraser une valeur déjà définie (environnement,
    puis ``.env``)."""
    load_dotenv(dotenv_path)
    for name, value in TELEMETRY_OPT_OUTS.items():
        os.environ.setdefault(name, value)
