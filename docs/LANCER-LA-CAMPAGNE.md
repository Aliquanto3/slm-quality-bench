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

## Revue

Revue de la PR `feat/campagne-complete-set-v3` (2026-10-18, une passe, second avis compris). `set-v3` reconstruit au commit `49bf5a5` (arbre propre) : mêmes 800 identifiants et mêmes pistes, 512 paliers relevés (4 096 : 50 questions, 8 192 : 643, 16 384 : 75, 32 768 : 32), empreinte du jeu `8081ad74…`.

- high | second avis 1 | corrigé | les paliers `num_ctx` étaient fixés à la construction du jeu avec les plafonds par défaut (2 048 hors raisonnement) : avec les plafonds de 4 096, `precheck` et `generate` refusaient la campagne (`num_predict 4096 ≥ num_ctx 4096`, 512 questions sous la marge d'AD-5). Clé `caps` du YAML de jeu (paliers des candidats importés recalculés, contextes OneRuler calibrés), set-v3 reconstruit avec les plafonds de la campagne ; set-v1 et set-v2 inchangés.
- medium | revue | corrigé | `build_plan` ne vérifiait que `num_predict < num_ctx` : il applique désormais la règle d'AD-5 complète (prompt estimé × 1,25 + `num_predict` ≤ `num_ctx`) et refuse d'avance ce qui finirait en `context_exceeded` « banc ».
- medium | revue | corrigé | trois candidats `jsonschemabench` (non tirés) n'ont aucun palier avec un plafond de 4 096 : ils gardent le leur pour que le tirage ne change pas, et le jeu n'est refusé que si l'un d'eux est tiré.
- medium | second avis 2 | corrigé | commande `build-set --set set-v3` et prérequis ajoutés au guide.
- medium | second avis 3 | corrigé | `modeles.md` : 14 modèles aux deux pistes, 6 en piste coupée seule, 1 en piste avec réflexion seule.
- medium | second avis 4 | corrigé | ajout des candidats : fichiers à toucher listés en tête du guide (PR à part).
- medium | second avis 5 | corrigé | interdits précisés d'après le `blocking` du manifeste (`HARNESS_DIRS`, section `generation`, jeu, digests, version d'Ollama, machine).
- low | second avis 6 | corrigé | manifeste de set-v3 reconstruit depuis un arbre propre (`dirty: false`).
- low | second avis 7 | corrigé | 216 h et 21 modèles dans `SOURCES.md` et le guide du pilote (story 8 inchangée).
- low | second avis 8 | corrigé | import `Path` inutilisé retiré.
- low | revue | reporté | la projection de durée du rapport pilote compte les paliers de set-v2 (plafonds par défaut, surtout 4 096) ; set-v3 est surtout à 8 192, donc plus de préremplissage et de cache KV. Les 216 h sont peut-être sous-estimées : surveiller le débit des premiers modèles (`log-generate.log`) ou refaire la projection avec les paliers de set-v3.
- low | revue | signalé | `oneruler-fr-none` (abstention, plafond passé de 2 048 à 4 096) a des contextes plus courts qu'en set-v2 : ses scores ne se comparent pas directement d'un jeu à l'autre. NIAH et CWE (RAG, 2 048) sont identiques.
