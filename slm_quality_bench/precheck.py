"""Sous-commande ``precheck --campaign <c> [--replay <c>-replay] [--ollama-url <url>]`` :
contrôles d'avant campagne en lecture seule, pour ne pas découvrir après des heures de
génération qu'une étape suivante (correction, rapport du pilote) sera refusée.

Elle n'écrit rien (ni verrou, ni journal, ni manifeste), n'enchaîne aucune phase et ne lance
aucun modèle : elle interroge Ollama (``/api/version``, ``/api/tags``, ``/api/show``, ``/api/ps``)
et ``nvidia-smi``. Contrôles, tous exécutés (les refus sont listés ensemble) :

1. ``QUALITY_BENCH_DATA`` défini dans l'environnement et dossier existant ;
2. YAML de la campagne (et du rejeu, de même jeu) valides ;
3. jeu de questions construit (``build-set``) ;
4. données NLTK de la correction (``fetch-nltk``) ;
5. fichiers de wavelocalai lus par ``pilot`` (ancien banc, catalogue) lisibles ;
6. Ollama joignable, en version attendue ; préflight des modèles de la campagne ;
7. GPU libre (``nvidia-smi``, AD-13) ;
8. liste de contrôle d'AD-13 rappelée (mises à jour, veille, ``OLLAMA_NUM_PARALLEL``).

Codes de sortie : 0 (tout est prêt) ; 2 (au moins un refus, listé).
"""

from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Callable

from .common import config, paths
from .common.logs import setup_logging
from .generation import commands as generation
from .generation.preflight import LaunchError, check_launch
from .generation.runner import SetError, build_plan
from .ollama.client import DEFAULT_BASE_URL, OllamaError, check_local_base_url

logger = logging.getLogger(__name__)

COMMAND = "precheck"
# Version d'Ollama épinglée pour la campagne (campagne-et-reprise.md) : un manifeste bloque la
# reprise si elle change.
EXPECTED_OLLAMA_VERSION = "0.40.2"


def _data_root_check() -> str | None:
    if not os.environ.get(paths.DATA_ENV, "").strip():
        return (
            f"{paths.DATA_ENV} n'est pas défini : le définir explicitement (dossier des "
            "données hors dépôt) avant de lancer une campagne"
        )
    if not paths.data_root().is_dir():
        return f"{paths.DATA_ENV} désigne un dossier absent : {paths.data_root()}"
    return None


def _nltk_check() -> str | None:
    from .grading import nlp  # import tardif : nltk ne se charge pas au démarrage de la CLI

    missing = nlp.missing_resources()
    if missing:
        return (
            f"données NLTK absentes de {paths.nltk_data_dir()} : {', '.join(missing)} "
            f"(lancer {nlp.FETCH_COMMAND})"
        )
    return None


def _origin_check() -> str | None:
    try:
        settings = config.load_pilot_settings(paths.pilot_settings_path())
    except config.ConfigError as exc:
        return f"réglage du pilote invalide : {exc}"
    missing = [
        f"{label} ({path}; variable {env})"
        for label, path, env in (
            ("ancien banc", settings.old_bench_path, paths.OLD_BENCH_ENV),
            ("catalogue", settings.catalog_path, paths.CATALOG_ENV),
        )
        if not path.is_file()
    ]
    if missing:
        return "fichier(s) de wavelocalai lus par pilot absents : " + " ; ".join(missing)
    return None


def run_checks(
    campaign: str,
    replay: str | None,
    base_url: str,
    expected_version: str | None = EXPECTED_OLLAMA_VERSION,
) -> list[str]:
    """Liste des refus (vide si tout est prêt) ; chaque contrôle réussi est journalisé."""
    failures: list[str] = []

    def record(label: str, problem: str | None) -> bool:
        if problem:
            failures.append(f"{label} : {problem}")
            logger.error("REFUS  %s : %s", label, problem)
            return False
        logger.info("OK     %s", label)
        return True

    def guarded(label: str, check: Callable[[], str | None]) -> bool:
        try:
            return record(label, check())
        except (
            config.ConfigError,
            LaunchError,
            SetError,
            generation.GenerateError,
            OllamaError,
            OSError,
        ) as exc:
            return record(label, str(exc))

    guarded("données (QUALITY_BENCH_DATA)", _data_root_check)
    guarded("données NLTK", _nltk_check)
    guarded("fichiers de wavelocalai (pilot)", _origin_check)

    loaded = {}
    for name in (campaign, replay):
        if name is None:
            continue
        label = f"campagne {name}"

        def load(name: str = name) -> str | None:
            config_path = paths.campaign_config_path(name)
            if not config_path.exists():
                return f"configuration absente : {config_path}"
            loaded[name] = config.load_campaign(config_path)
            return None

        guarded(label, load)
    if replay is not None and campaign in loaded and replay in loaded:
        same = loaded[campaign].set_id == loaded[replay].set_id
        record("rejeu sur le même jeu", None if same else "jeux différents")

    if campaign not in loaded:
        return failures
    campaign_config = loaded[campaign]
    plan: dict = {}

    def set_check() -> str | None:
        nonlocal plan
        questions, tracks, _ = generation.load_set(campaign_config.set_id)
        plan = build_plan(campaign_config.generation, questions, tracks)
        return None

    if guarded(f"jeu {campaign_config.set_id} construit", set_check):
        logger.info(
            "       %d question(s) think_off, %d think_on dans la campagne",
            len(plan["think_off"]),
            len(plan["think_on"]),
        )

    client = generation.make_client(base_url)
    try:

        def ollama_check() -> str | None:
            version = client.version()
            if expected_version and version != expected_version:
                return (
                    f"version {version} au lieu de {expected_version} (une seule version "
                    "pour toute la campagne ; --ollama-version pour en choisir une autre)"
                )
            return None

        def models_check() -> str | None:
            resolved = generation.preflight(client, campaign_config.generation["models"])
            if plan:
                check_launch(resolved, plan)
            return None

        def gpu_check() -> str | None:
            generation.check_gpu_free(client, campaign_config.gpu_check)
            return None

        if guarded("Ollama joignable, version attendue", ollama_check):
            guarded("modèles installés et pistes (préflight)", models_check)
            guarded("GPU libre (nvidia-smi)", gpu_check)
    finally:
        client.close()
    return failures


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign", required=True, help="identifiant de la campagne")
    parser.add_argument(
        "--replay", default=None, help="campagne de rejeu à contrôler aussi (défaut : aucune)"
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_BASE_URL,
        help=f"URL locale d'Ollama (défaut : {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--ollama-version",
        default=EXPECTED_OLLAMA_VERSION,
        help=f"version d'Ollama attendue (défaut : {EXPECTED_OLLAMA_VERSION} ; vide : aucune)",
    )


def _run(args: argparse.Namespace) -> int:
    setup_logging(COMMAND, None)  # console seule : rien n'est écrit
    try:
        paths.check_id(args.campaign, "campagne")
        if args.replay is not None:
            paths.check_id(args.replay, "campagne de rejeu")
        base_url = check_local_base_url(args.ollama_url)
    except ValueError as exc:
        logger.error("Contrôle refusé : %s", exc)
        return 2
    failures = run_checks(args.campaign, args.replay, base_url, args.ollama_version or None)
    for reminder in generation.CHECKLIST_REMINDERS:
        logger.info("À vérifier à la main (AD-13) : %s", reminder)
    value = os.environ.get(generation.NUM_PARALLEL_ENV)
    if value not in (None, "", "1"):
        logger.warning(
            "%s=%s dans cet environnement : exiger 1 côté service",
            generation.NUM_PARALLEL_ENV,
            value,
        )
    if failures:
        logger.error("%d contrôle(s) refusé(s) : rien n'est lancé", len(failures))
        return 2
    logger.info("Tous les contrôles automatiques sont passés")
    return 0


PRECHECK = (
    COMMAND,
    "Contrôles d'avant campagne en lecture seule (données, NLTK, jeu, Ollama, GPU) ; n'écrit rien",
    _configure,
    _run,
)
