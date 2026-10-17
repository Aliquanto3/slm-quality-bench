# Lancer le pilote

Le pilote fait tourner 4 modèles sur les deux pistes (`pilot-20261017`), puis rejoue un quart des questions (`pilot-20261017-replay`) pour mesurer la stabilité. Il produit le rapport qui fixe N (effectif de la campagne), les plafonds de tokens et K (graines par question) avant la campagne complète. Contrat : `docs/spec/stories/8-pilote-sur-4-modeles.md`.

Une seule commande, reprenable :

```powershell
python -m slm_quality_bench.run_pilot --campaign pilot-20261017
```

Elle ne lance **pas** le juge : il vient après, comme étape séparée (voir plus bas).

## Prérequis

1. **Ollama 0.40.2**, la version épinglée pour toute la campagne (un changement de version bloque la reprise). Mises à jour automatiques d'Ollama coupées, Windows Update en pause pendant le pilote, `OLLAMA_NUM_PARALLEL` absent ou à 1 pour le service.
2. **Les 4 modèles du pilote installés** : `ling3-tiny:8b-q4_k_m`, `LiquidAI/lfm2.5-2.6b`, `gemma4:e2b-it-qat`, `qwen3.5:4b`. Les tags exacts sont dans `slm_quality_bench/campaigns/pilot-20261017.yaml`. Aucun téléchargement n'a lieu pendant la campagne : tout se tire avant (`ollama pull`).
3. **Le GPU à soi** : aucun autre processus dessus (le banc contrôle `nvidia-smi` avant chaque modèle).
4. **Les données hors dépôt**, y compris les jeux construits, les questions privées et les données NLTK. Elles existent déjà ; `QUALITY_BENCH_DATA` doit pointer dessus (ou sur une copie) :

   ```powershell
   $env:QUALITY_BENCH_DATA = "<dossier-de-données>"
   ```

   Ce dossier contient `sets\set-v2\` (sinon : `build-set --set set-v2`, qui exige les sources téléchargées par `fetch --all`) et `nltk_data\` (sinon : `fetch-nltk`). **Ne jamais le commiter ni le copier dans ce dépôt** : il contient des questions privées. La commande refuse de partir si la variable n'est pas définie.
5. **Les deux fichiers de wavelocalai lus par le rapport**, que le banc ne copie pas : un export du banc de vitesse (`benchmarks/results/tour-rtx3050-a2b6baf5.json`) et le catalogue (`config/models_catalog.json`). Les indiquer, ou les déposer sous `$QUALITY_BENCH_DATA\wavelocalai\` aux mêmes chemins relatifs :

   ```powershell
   $env:QUALITY_BENCH_OLD_BENCH = "<clone de wavelocalai>\benchmarks\results\tour-rtx3050-a2b6baf5.json"
   $env:QUALITY_BENCH_CATALOG   = "<clone de wavelocalai>\config\models_catalog.json"
   ```

6. **Un venv du dépôt** (Python 3.14) :

   ```powershell
   python -m venv .venv
   .venv\Scripts\python -m pip install -e ".[dev]"
   ```

   Dans les commandes ci-dessous, `python` est `.venv\Scripts\python`.

## Lancer

**Dans un terminal PowerShell à part, pas dans le shell de Claude Code** : une génération longue lancée dans ce shell est tuée sous pression mémoire. Garder la fenêtre ouverte (ne pas la fermer ni mettre la session en veille à la main : le banc empêche déjà la mise en veille de Windows pendant la génération et la rend à la sortie).

```powershell
cd <dépôt slm-quality-bench>
$env:QUALITY_BENCH_DATA = "<dossier-de-données>"
.venv\Scripts\python -m slm_quality_bench.run_pilot --campaign pilot-20261017
```

Le lanceur enchaîne six étapes, chacune dans son processus (les phases ne communiquent que par fichiers) :

1. `precheck` : contrôles en lecture seule, tous listés d'un coup s'il y a des refus : `QUALITY_BENCH_DATA` défini, YAML des deux campagnes, jeu construit, données NLTK, fichiers de wavelocalai, Ollama joignable en 0.40.2, modèles installés et pistes possibles, GPU libre. Il rappelle aussi la liste d'avant campagne (AD-13) que seul un humain vérifie.
2. `generate` du pilote, 3. `generate` du rejeu.
4. `grade` du pilote, 5. `grade` du rejeu (la rédaction reste « en attente de jugement »).
6. `pilot --campaign pilot-20261017 --replay pilot-20261017-replay` : le rapport.

**Arrêt et reprise.** Il s'arrête au premier refus, avec le code de l'étape (2 : lancement refusé, rien d'écrit ; 1 : échec en cours de route). `Ctrl+C` (ou un fichier `STOP` dans `campaigns\<c>\`) laisse la question en cours se terminer, puis sort proprement (codes 130 et 3). **Relancer la même commande reprend sans doublon ni trou** : `generate` ne perd au plus que la question en cours, `grade` et le rapport réécrivent leurs sorties à l'identique. Après une panne d'Ollama, redémarrer le service puis relancer.

## Durée

Estimation de la story 8, au débit de l'ancien banc : pilote 8,5 h (scénario central) à 11,7 h (haut), rejeu 2,4 à 3,1 h, soit **11 à 15 h au total**, dont 60 % en piste activée (`think_on`) et un tiers pour Qwen 3.5 4B seul. Prévoir une nuit et la journée suivante, machine branchée.

Suivre l'avancement sans gêner le banc : `campaigns\<c>\log-generate.log` (identifiants, statuts, comptes) et le nombre de lignes de `campaigns\<c>\generation.jsonl`.

## Lire le rapport

`campaigns\pilot-20261017\pilot-report.md` (et `.json`), sous `$QUALITY_BENCH_DATA`. Il ne contient ni question ni sortie de modèle. À regarder :

- **N, l'effectif.** La discordance ψ entre modèles, par paire et par usage, donne le N indicatif pour détecter 10 et 20 points d'écart. À comparer à l'effectif du jeu : si N dépasse ce qu'on peut faire tenir, c'est la réduction (ci-dessous) qui tranche.
- **Les plafonds de tokens.** Taux de troncature par modèle et par usage au plafond actuel (4 096 en `think_on` raisonnement, 2 048 ailleurs), et troncature projetée des deux plafonds candidats de `pilot.yaml`. Un plafond qui tronque beaucoup mesure le plafond, pas le modèle.
- **K, le nombre de graines.** La stabilité au rejeu : part de sorties et de scores qui changent à graine égale, et son ratio à ψ. Le rapport n'en conclut rien : K reste à décider.
- **Usages au plafond ou au plancher** (moyenne ≥ 0,9 ou ≤ 0,1 pour chaque modèle) : un usage qui ne discrimine pas est à retravailler ou à retirer.
- **La projection de la durée** de la campagne complète sur les 20 modèles contre le budget de 144 h (6 jours). Si elle dépasse, appliquer l'ordre de réduction des contraintes de `docs/spec/SPEC.md`.
- La **complétude** de chaque campagne, en tête : un pilote incomplet donne des mesures partielles.
- La rédaction est « non notée » tant que le juge n'a pas tourné ; la note provisoire n'est pas une mesure.

Décider ensuite N, les plafonds et K (et les consigner dans les YAML de campagne), puis passer au juge.

## Étape suivante : le juge, puis la calibration

Séparée du lanceur, parce qu'elle a le droit au réseau (juge cloud, payant) ou exige le GPU (juge local), jamais les deux en même temps qu'une génération. `grading.judge` du pilote est `haiku` ; les juges sont définis dans `slm_quality_bench/judges.yaml`.

```powershell
# Juge cloud (Claude Haiku en lots) : clé d'API dans l'environnement seulement, plafond de dépense explicite
$env:ANTHROPIC_API_KEY = "..."
.venv\Scripts\python -m slm_quality_bench judge --campaign pilot-20261017 --judge haiku --max-cost-usd 5

# Corriger de nouveau, maintenant que les verdicts existent, puis relire le rapport
.venv\Scripts\python -m slm_quality_bench grade --campaign pilot-20261017
.venv\Scripts\python -m slm_quality_bench pilot --campaign pilot-20261017 --replay pilot-20261017-replay
```

Pour le juge local Winnow, voir la procédure manuelle de `docs/spec/juge-et-calibration.md` (import du modèle, mesures sur la machine). Le juge local prend le verrou machine et refuse de partir si un modèle de génération est chargé.

**Calibration.** Choisir le juge sur son accord avec environ 100 étiquettes humaines :

```powershell
.venv\Scripts\python -m slm_quality_bench calibrate-sample --campaign pilot-20261017 --size 100
# Étiqueter : calibration\labels-todo-pilot-20261017.{jsonl,md} sous $QUALITY_BENCH_DATA, puis ajouter à labels.jsonl
.venv\Scripts\python -m slm_quality_bench calibrate --campaign pilot-20261017 --min-agreement <X> --max-qwen-bias <Y>
```

Les deux seuils (accord minimal, biais Qwen maximal toléré) sont à fixer par l'utilisateur, au plus tard à ce moment ; sans eux le rapport dit « seuil non fixé » et ne recommande rien. Le rapport est `campaigns\pilot-20261017\calibration-report.md`. Le juge retenu se consigne avant la campagne complète.
