# Lancer la campagne complète

Campagne `full-20261018` : 21 modèles sur `set-v3` (800 questions, `think_on` sur toutes), K = 1, plafonds de 4 096 tokens (RAG 2 048), budget 216 h. Elle suit le pilote (`docs/LANCER-LE-PILOTE.md`, dont les prérequis valent ici : Ollama 0.40.5, modèles installés, GPU libre, venv). Les deux modèles candidats (LFM 2.5 24B-A2B, Nemotron 3.5 Lightning), s'ils sont retenus, s'ajoutent avant le lancement dans une PR à part : entrée à leur rang de débit dans `slm_quality_bench/campaigns/full-20261018.yaml` et dans `full_models` de `slm_quality_bench/pilot.yaml`, ligne du tableau de `docs/spec/modeles.md`, comptes de `tests/test_campaign_files.py` (21 modèles, 15 en `think_on`), et nouvelle projection de durée contre les 216 h.

## Environnement

Dans un terminal PowerShell à part, pas dans le shell de Claude Code :

```powershell
cd <dépôt slm-quality-bench>
# Données : data\quality_bench\ du dépôt par défaut (sets\set-v3\, nltk_data\, et copies figées
# de wavelocalai sous wavelocalai\). Pour un autre dossier seulement :
# $env:QUALITY_BENCH_DATA = "<dossier-de-données>"
```

Le jeu `set-v3` doit être construit dans `$env:QUALITY_BENCH_DATA` avec sa clé `caps` (reconstruit le 2026-10-18 à la revue ; paliers `num_ctx` dimensionnés pour les plafonds de 4 096). Sinon, sur un arbre propre, avec les sources de `set-v2` déjà présentes (`fetch`, fichiers privés sous `private\`, voir `slm_quality_bench/questions/SOURCES.md`) :

```powershell
.venv\Scripts\python -m slm_quality_bench build-set --set set-v3
```

`build-set` refuse un jeu existant : supprimer d'abord `sets\set-v3\` sous les données et `benchmarks\quality\sets\set-v3\` dans le dépôt, puis vérifier que `git status` ne montre aucun changement sous ce dernier (mêmes entrées et même graine : index identique ; seul `manifest.json` change s'il est construit à un autre commit, à ne pas commiter).

Les 21 modèles (et les candidats) doivent être installés (`ollama pull`) **avant** : aucun téléchargement pendant la campagne. Dans les commandes ci-dessous, `python` est `.venv\Scripts\python`.

## Avant la campagne : admission des deux candidats

Télécharger d'abord `lfm2.5:24b-a2b-q4_K_M` et `nemotron-3.5-lightning:30b-a3b-q4_K_M` (`ollama pull`, Nemotron pèse ~25 Go), puis lancer `precheck` et `generate` sur la campagne `admission-20261018` (70 questions `think_off` et 70 `think_on` de `set-v3` par modèle, 280 lignes, ~3 h pour les deux candidats), **avant** `full-20261018`. Elle mesure le débit, la mémoire de la machine (`memory.jsonl` : RAM et VRAM de référence et de pointe, section « Mémoire de la machine » du rapport `pilot`), le contexte validé (`num_ctx_max: 32768` est à confirmer par `precheck`) et donne un aperçu de qualité, pour admettre ou écarter chaque candidat :

```powershell
.venv\Scripts\python -m slm_quality_bench precheck --campaign admission-20261018
.venv\Scripts\python -m slm_quality_bench generate --campaign admission-20261018
```

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

## Publier les résultats

```powershell
.venv\Scripts\python -m slm_quality_bench export-release --campaign full-20261018 admission-20261018 --version 0.2.0
```

Hors ligne, sans Ollama ni verrou : écrit `benchmarks/quality/releases/0.2.0/slm-quality-results.json` (`qb.results/1`, schéma `docs/schemas/qb.results-1.schema.json`, AD-18), recalculable à l'identique. Il faut refaire `grade` (et le juge) puis, au besoin, ajouter les modèles au registre `slm_quality_bench/models.yaml` : un modèle absent refuse l'export. Une campagne incomplète est publiée avec `status: partial`. L'énergie reste `unvalidated` (valeurs nulles) tant que la mesure de puissance de la machine n'est pas validée. Joindre ensuite le fichier à la release GitHub sous `slm-quality-results.json` et `slm-quality-results-vX.Y.Z.json`.

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

## Revue de l'admission et de la mesure de mémoire

Revue de la PR `feat/memoire-systeme-admission` (2026-10-18, une passe, second avis compris), rebasée sur `main` (`d54955f`).

- medium | décision | corrigé | campagne d'admission réduite (décision d'Anaël) : effectifs `think_on` du rejeu sur les deux pistes. Tirage vérifié par `group_ids` sur `benchmarks/quality/sets/set-v3/index.jsonl` : 66 groupes, 70 questions (raisonnement : 13 questions pour 9 groupes), soit 70 `think_off` + 70 `think_on` par modèle, 280 lignes, ~3 h pour les deux candidats. La variante longue aurait donné 140 + 140 (132 groupes). Le test vérifie le compte sur l'index réel.
- medium | second avis 1 | corrigé | un arrêt brutal perdait toute la mesure du modèle en cours, sans signal. Points intermédiaires : un segment `qb.memory/1` au plus tard toutes les 10 min (avant la question suivante), puis à la fin du modèle ; seul le dernier segment est perdu. Le rapport `pilot` nomme les modèles interrogés sans aucune mesure ; la spec ne dit plus « rien n'est perdu ».
- low | second avis 2 | corrigé | un `memory.jsonl` illisible refusait toute la génération : avertissement et génération sans mesure.
- low | second avis 3 | corrigé | `stop()` attend le fil `interval + 1` s et saute la dernière sonde si le fil est encore bloqué dans `nvidia-smi` (au plus ~3 s par modèle au lieu de ~17 s).
- low | second avis 4 | corrigé | l'échantillonneur est affecté au runner avant `start()` : une interruption ne laisse plus de fil orphelin.
- low | second avis 5 | rejeté | l'empreinte du harnais change avec `common/` et `generation/` : voulu (AD-12), aucune campagne en cours ; `full-20261018` et l'admission démarreront sur ce code.
- low | second avis 6 | corrigé | lignes `memory.jsonl` d'un autre manifeste ou d'une autre campagne : écartées avec un avertissement au journal de `pilot`.
- low | revue | reporté | `pilot --campaign admission-20261018` (sans rejeu, candidats absents de l'ancien banc) n'a pas été essayé sur données réelles : à lancer après la génération pour lire la section « Mémoire de la machine » ; en cas d'échec, lire `memory.jsonl` directement.
- low | décision | ajouté | puissance du GPU dans `memory.jsonl` (`gpu_power_source`, `gpu_power_avg_w`, `gpu_power_max_w`, `gpu_power_samples`, `gpu_energy_wh`) : `power.draw` lu dans la même commande que la VRAM ; à défaut (`[N/A]` sur la tour, pilote 610.62), `Avg` des « Power Samples » de `nvidia-smi -q -d POWER`, relu au plus toutes les 10 s ; toute erreur donne des valeurs nulles. Sur la tour, attendre `power_samples_avg` : valeur non validée tant qu'elle reste à 46,3 W sous charge (à vérifier dans le rapport `pilot` après l'admission).
