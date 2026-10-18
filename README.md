# slm-quality-bench

Banc de qualité difficile pour petits modèles de langage locaux (SLM) servis par [Ollama](https://ollama.com), en français.

Il répond à une question de choix : parmi une vingtaine de petits modèles qui tiennent sur une machine ordinaire, lequel prendre pour quel usage ? Les jeux publics connus sont saturés ou contaminés, et un banc d'une trentaine de questions ne départage plus les meilleurs modèles. Celui-ci compose environ 800 questions difficiles par piste, avec un classement statistiquement fondé (intervalles, comparaisons corrigées, groupes de modèles indiscernables).

> **État.** Le banc est construit et testé (sans Ollama ni GPU), mais le pilote sur 5 modèles et la campagne complète restent à lancer (procédure : `docs/LANCER-LE-PILOTE.md`). Aucun résultat n'est publié ici pour l'instant.

Projet d'origine : [wavelocalai](https://github.com/Aliquanto3/wavelocalai) (démonstrateur Streamlit de petits modèles locaux avec mesure carbone, et banc de vitesse). Ce dépôt en est l'extraction, avec l'historique du banc.

## Principe

- **Deux pistes.** Chaque modèle répond en raisonnement coupé (`think_off`, environ 800 questions) et, s'il en est capable, en raisonnement activé (`think_on`, environ 400 questions). Les conditions sont fixées et consignées : API native `/api/chat`, `temperature=0`, graine, `num_ctx`, plafond de tokens, chauffe, version d'Ollama.
- **Sept usages**, chacun avec ses correcteurs : raisonnement, consignes vérifiables, outils (appels multi-tours et parallèles), extraction JSON, RAG long contexte, abstention, rédaction en français.
- **Correction déterministe.** Hors rédaction, aucune note ne passe par un juge : les scores se recalculent hors ligne depuis les générations brutes (`generation.jsonl`), sans régénérer.
- **Campagne reprenable.** Fichiers JSONL en ajout seul, clé de reprise par (modèle, piste, question, graine), manifeste qui bloque une reprise incohérente, arrêt propre par `Ctrl+C` ou fichier `STOP`, veille de la machine empêchée.
- **Anti-contamination.** Questions générées à graine (mêmes graine, mêmes empreintes), questions privées gardées hors du dépôt (seules leurs empreintes sont versionnées), jeux publics à révision épinglée et empreinte `sha256` vérifiée, groupes de questions qui partagent un contexte traités comme une seule unité statistique.
- **Juge calibré pour la rédaction.** Les critères de sens sont notés un à un, en questions fermées, dans une phase séparée et reprenable. Le juge est choisi sur son accord avec des étiquettes humaines (candidats : Winnow-E4B local, cascade Winnow vers Claude Haiku, MiMo, Haiku), et son biais envers la famille Qwen est mesuré. Les critères qui demandent de compter sont vérifiés par le code, pas par le juge.
- **Statistiques.** Intervalle de Wilson par modèle, comparaisons appariées corrigées des tests multiples, groupes indiscernables, taux de troncature, corrélation de Spearman avec une référence externe (indice Artificial Analysis daté).

Référence externe : les valeurs de `benchmarks/quality/references/aa-2026-10-17.json` viennent de l'[Artificial Analysis Intelligence Index](https://artificialanalysis.ai) (relevé manuel du 2026-10-17). Elles sont reprises avec attribution ; Artificial Analysis en reste la source.

Les décisions de conception sont dans `docs/architecture/ARCHITECTURE-SPINE.md` (AD-1 à AD-17) et le contrat dans `docs/spec/SPEC.md`.

## Installation

**Prérequis : Python 3.14 ou plus récent.** Le code emploie une syntaxe propre à 3.14 (par exemple `except A, B:` sans parenthèses) : il ne s'importe pas sous 3.13 ou avant.

```powershell
git clone https://github.com/Aliquanto3/slm-quality-bench
cd slm-quality-bench
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Les dépendances d'exécution sont dans `requirements.txt` (bornes inférieures), les outils de développement dans l'extra `dev`. Installer en mode éditable (`-e`) depuis le dépôt : hors de ce mode, définir `QUALITY_BENCH_DATA` est obligatoire (`generate`, `judge` et `grade` refusent sinon de partir, pour ne pas écrire les données dans `site-packages`). Ollama doit tourner pour `generate` seulement ; les tests n'en ont pas besoin.

## Commandes principales

```powershell
python -m slm_quality_bench --help          # ou : slm-quality-bench --help

python -m slm_quality_bench precheck --campaign <c>   # contrôles d'avant campagne, lecture seule
python -m slm_quality_bench fetch --all     # jeux publics, à révision et empreinte épinglées
python -m slm_quality_bench fetch-nltk      # données NLTK de la correction
python -m slm_quality_bench build-set --set set-v2
python -m slm_quality_bench generate --campaign <c>
python -m slm_quality_bench judge --campaign <c> --judge <id>
python -m slm_quality_bench grade --campaign <c>
python -m slm_quality_bench report --campaign <c>
python -m slm_quality_bench pilot --campaign <c>     # rapport du pilote (projection, discrimination)
python -m slm_quality_bench calibrate-sample --campaign <c>   # échantillon à étiqueter
python -m slm_quality_bench calibrate --campaign <c>          # accord du juge avec les étiquettes
```

Le pilote se lance de bout en bout (contrôles, génération du pilote et du rejeu, correction, rapport ; sans le juge) par `python -m slm_quality_bench.run_pilot --campaign pilot-20261017`, reprenable en relançant la même commande : voir `docs/LANCER-LE-PILOTE.md`.

Les options de chaque commande s'affichent avec `--help`. Les sources, leurs licences et les commandes d'avant campagne sont décrites dans `slm_quality_bench/questions/SOURCES.md`. Le téléchargement se fait **avant** une campagne, jamais pendant.

## Données hors dépôt

Tout ce que le banc produit ou télécharge vit sous `$QUALITY_BENCH_DATA` (recommandé : un dossier hors du dépôt ; à défaut, et seulement en installation éditable, `data/quality_bench/` du dépôt, ignoré par git) : sources et candidats, jeux construits, campagnes, calibration, questions privées, données NLTK. Le dépôt ne versionne que le code, les réglages (`judges.yaml`, `pilot.yaml`, `sets/`, `campaigns/`), les index et manifestes de jeux et les exports publics sous `benchmarks/quality/`.

Les commandes `pilot` et `precheck` lisent deux fichiers venus de wavelocalai, projet séparé : un export du banc de vitesse (`benchmarks/results/<machine>-<empreinte>.json`) et le catalogue de modèles (`config/models_catalog.json`). Le banc en garde une copie figée sous `$QUALITY_BENCH_DATA/wavelocalai/`, aux mêmes chemins relatifs (provenance dans `PROVENANCE.txt`), définitive : wavelocalai ne produit plus de résultats de banc ; `QUALITY_BENCH_OLD_BENCH` et `QUALITY_BENCH_CATALOG` désignent d'autres chemins. Les tests qui les lisent sautent s'ils manquent.

## Tests et contrôles

```powershell
$env:QUALITY_BENCH_DATA = "D:\quality_bench"   # facultatif ; doit contenir nltk_data (fetch-nltk)
python -m pytest -q
ruff check . ; black --check . ; isort --check-only .
```

## Licence et citation

Apache-2.0 (voir `LICENSE`). Le code tiers repris sous `grading/vendored/` et `envs/vendored/` conserve sa licence (voir `NOTICE`). Les jeux publics ne sont pas redistribués ; leurs licences sont dans `SOURCES.md`.

### Citer

Si vous utilisez ce banc, merci de le citer (voir aussi `CITATION.cff`) :

> Yahi, Anaël (2026). *slm-quality-bench : banc de qualité difficile pour petits modèles locaux, en français*. Wavestone. https://github.com/Aliquanto3/slm-quality-bench
