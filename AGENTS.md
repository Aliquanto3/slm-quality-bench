## slm-quality-bench

Banc de qualité difficile pour petits modèles locaux (Ollama), en français. Python. Issu de wavelocalai (https://github.com/Aliquanto3/wavelocalai), du même auteur. Spec : `docs/spec/SPEC.md` ; architecture : `docs/architecture/ARCHITECTURE-SPINE.md` (décisions AD-1 à AD-17) ; reports : `docs/deferred-work.md`.

## Policy

- Jamais de push sur `main` : une branche préfixée (`fix/`, `feat/`, `docs/`, `chore/`, `bench/`, `audit/`, ou `claude/` en session cloud), une PR, fusion par merge commit, jamais de squash.
- Dépôt public : jamais de `data/` (jeux téléchargés, campagnes, calibration, questions privées) dans un commit ou une PR, ni question privée, extrait de réponse de modèle, ni capture montrant du contenu de ces données.
- Ne jamais éditer à la main `benchmarks/quality/` (index, manifestes et exports écrits par `build-set` et `report`) ; seules les références `references/aa-<date>.json` sont relevées à la main, datées.
- Ne jamais figer une version de dépendance de mémoire : la vérifier sur PyPI ou par une installation réelle. Les bornes sont dans `requirements.txt` (exécution) et `pyproject.toml` (extra `dev`).
- Le code emprunté sous `grading/vendored/` et `envs/vendored/` reste tel que publié (modifications listées dans chaque `PROVENANCE.md`, hors ruff, black et isort).
- Docs, messages de commit, PR et textes d'interface en français ; identifiants de code en anglais.
- Aucun appel à Ollama, aucun GPU ni modèle dans les tests : tout est simulé (`tests/ollama_fake.py`).

## Where things are

- Paquet : `slm_quality_bench/` (`python -m slm_quality_bench <commande>` ou `slm-quality-bench`), un sous-paquet par phase : `questions/`, `generation/`, `grading/`, `judge/`, `stats/`, `report/`, `common/`. Réglages versionnés : `judges.yaml`, `pilot.yaml`, `sets/`, `campaigns/`.
- Données hors dépôt : `data/quality_bench/` (défaut, ignoré par git) ou `$QUALITY_BENCH_DATA`. Projet indépendant de wavelocalai depuis le 2026-10-18 : l'ancien banc et le catalogue lus par `pilot` et `precheck` sont des copies figées sous `data/quality_bench/wavelocalai/` (`PROVENANCE.txt`), définitives : wavelocalai ne produit plus de résultats de banc, l'admission des nouveaux modèles se fait ici ; `$QUALITY_BENCH_OLD_BENCH` et `$QUALITY_BENCH_CATALOG` pour d'autres chemins. Ne jamais modifier wavelocalai depuis ce projet ; le consulter en lecture seule au besoin.
- Lancer le pilote : `docs/LANCER-LE-PILOTE.md` (`python -m slm_quality_bench.run_pilot`, dans un terminal à part ; jamais depuis le shell de Claude Code). Aucun Ollama, modèle ni GPU lancé par un agent.
- Lancer la campagne complète : `docs/LANCER-LA-CAMPAGNE.md` (`full-20261018` sur `set-v3`, même règle : terminal à part, jamais par un agent).
- Sources, licences et commandes d'avant campagne : `slm_quality_bench/questions/SOURCES.md`. Aucun téléchargement pendant une campagne.

## Running and verifying

- Installer : `python -m venv .venv`, puis `.venv\Scripts\python -m pip install -e ".[dev]"` (Python 3.14). Appeler l'interpréteur directement plutôt qu'activer le venv : l'exécution de scripts PowerShell peut être bloquée.
- Tests : `python -m pytest -q` (sans Ollama ni réseau ; `QUALITY_BENCH_DATA` doit contenir `nltk_data` pour les tests de correction, voir `fetch-nltk`). Les tests qui lisent l'ancien banc de wavelocalai sautent sans `QUALITY_BENCH_OLD_BENCH` et `QUALITY_BENCH_CATALOG`.
- Contrôles : `ruff check .`, `black --check .`, `isort --check-only .` (ligne de 100, cible py314).

## Conventions that differ from defaults

- Messages de commit : `Préfixe: description en français` (`Fix:`, `Feat:`, `Docs:`, `Chore:`, `Bench:`, `Audit:`), pas de conventional commits en minuscules.
- `disable_telemetry()` (`slm_quality_bench/common/telemetry.py`) s'appelle en tête de la CLI et juste avant tout import de `huggingface_hub` ; `tests/test_telemetry.py` le vérifie.
- `.secrets.baseline`, s'il est repris : écrire sans BOM (sous PowerShell 5.1, `Out-File -Encoding utf8` en ajoute un qui casse detect-secrets ; utiliser `[System.Text.UTF8Encoding]::new($false)`).
