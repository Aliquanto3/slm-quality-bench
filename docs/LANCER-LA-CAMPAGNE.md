# Lancer la campagne complète

Campagne `full-20261018` : 21 modèles sur `set-v3` (800 questions, `think_on` sur toutes), K = 1, plafonds de 4 096 tokens (RAG 2 048), budget 216 h. Elle suit le pilote (`docs/LANCER-LE-PILOTE.md`, dont les prérequis valent ici : Ollama 0.40.5, modèles installés, GPU libre, venv). Les deux modèles candidats (LFM 2.5 24B-A2B, Nemotron 3.5 Lightning), s'ils sont retenus, s'ajoutent avant le lancement dans une PR à part : entrée à leur rang de débit dans `slm_quality_bench/campaigns/full-20261018.yaml` et dans `full_models` de `slm_quality_bench/pilot.yaml`, ligne du tableau de `docs/spec/modeles.md`, comptes de `tests/test_campaign_files.py` (21 modèles, 15 en `think_on`), et nouvelle projection de durée contre les 216 h.

## Environnement

Dans un terminal PowerShell à part, pas dans le shell de Claude Code :

```powershell
cd <dépôt slm-quality-bench>
$env:QUALITY_BENCH_DATA = "<dossier-de-données>"   # contient sets\set-v3\ et nltk_data\
```

Le jeu `set-v3` doit être construit dans `$env:QUALITY_BENCH_DATA` avec sa clé `caps` (reconstruit le 2026-10-18 à la revue ; paliers `num_ctx` dimensionnés pour les plafonds de 4 096). Sinon, sur un arbre propre, avec les sources de `set-v2` déjà présentes (`fetch`, fichiers privés sous `private\`, voir `slm_quality_bench/questions/SOURCES.md`) :

```powershell
.venv\Scripts\python -m slm_quality_bench build-set --set set-v3
```

`build-set` refuse un jeu existant : supprimer d'abord `sets\set-v3\` sous les données et `benchmarks\quality\sets\set-v3\` dans le dépôt, puis vérifier que `git status` ne montre aucun changement sous ce dernier (mêmes entrées et même graine : index identique ; seul `manifest.json` change s'il est construit à un autre commit, à ne pas commiter).

Les 21 modèles (et les candidats) doivent être installés (`ollama pull`) **avant** : aucun téléchargement pendant la campagne. Dans les commandes ci-dessous, `python` est `.venv\Scripts\python`.

## Contrôler puis générer

```powershell
.venv\Scripts\python -m slm_quality_bench precheck --campaign full-20261018
.venv\Scripts\python -m slm_quality_bench generate --campaign full-20261018
```

`precheck` est en lecture seule et liste tous les refus d'un coup (modèles installés, valeurs `think` et pistes possibles selon `/api/show`, contexte déclaré, GPU, version d'Ollama). Corriger le YAML ou la machine avant `generate`. Suivre l'avancement : `campaigns\full-20261018\log-generate.log` et les lignes de `generation.jsonl`.

## Pause et reprise

Un fichier `STOP` dans `campaigns\full-20261018\` ou `Ctrl+C` laisse la question en cours se terminer, puis sort proprement. **Relancer la même commande `generate`** reprend sans doublon ni trou. Meilleur moment pour pauser : juste après « modèle déchargé » au journal (rien à recharger ni à perdre).

## Interdits pendant la campagne

La reprise est refusée (`blocking` du manifeste de campagne, `common/manifest.py`) si l'un de ces éléments change :

- le code du harnais : `slm_quality_bench/common/`, `ollama/`, `generation/` et `envs/` (`HARNESS_DIRS`). Un changement ailleurs (correcteurs, rapport, juge) ne bloque pas la reprise, mais pas de `git pull`, de fusion ni de changement de branche pendant la campagne par prudence ;
- la section `generation` résolue du YAML de campagne (plafonds, modèles, pistes, paliers) ; les commentaires et la section `grading` ne bloquent pas ;
- le jeu `set-v3` (son empreinte) ;
- le digest d'un modèle (retéléchargement ou reconstruction) et la version d'Ollama ;
- le libellé de la machine (`$env:QUALITY_BENCH_MACHINE`, sinon le nom d'hôte).

## Après la génération

```powershell
.venv\Scripts\python -m slm_quality_bench grade --campaign full-20261018
$env:ANTHROPIC_API_KEY = "..."   # clé dans l'environnement seulement
.venv\Scripts\python -m slm_quality_bench judge --campaign full-20261018 --judge haiku --max-cost-usd <plafond>
.venv\Scripts\python -m slm_quality_bench grade --campaign full-20261018
.venv\Scripts\python -m slm_quality_bench report --campaign full-20261018
```

Le juge (rédaction) n'a pas le droit de tourner pendant une génération ; refaire `grade` après lui, puis `report` (écrit `benchmarks/quality/full-20261018/`, à ne pas éditer à la main).
