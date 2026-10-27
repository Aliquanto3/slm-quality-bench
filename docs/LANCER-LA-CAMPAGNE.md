# Lancer la campagne complète

Campagne `full-20261018` : 23 modèles sur `set-v3` (800 questions, `think_on` sur toutes), K = 1, plafonds de 4 096 tokens (RAG 2 048), budget 216 h (projection : 108,0 h, voir ci-dessous). Elle suit le pilote (`docs/LANCER-LE-PILOTE.md`, dont les prérequis valent ici : Ollama 0.40.5, modèles installés, GPU libre, venv). Les deux modèles candidats (LFM 2.5 24B-A2B, Nemotron 3.5 Lightning) sont écartés (décision d'Anaël du 2026-10-18, voir « Avant la campagne : admission des deux candidats » et `docs/spec/modeles.md`) ; LFM 2.5 24B-A2B sera réexaminé après la campagne.

## Environnement

Dans un terminal PowerShell à part, pas dans le shell de Claude Code :

```powershell
cd <dépôt slm-quality-bench>
# Données : data\quality_bench\ du dépôt par défaut (sets\set-v3\, nltk_data\, et copies figées
# de wavelocalai sous wavelocalai\). Pour un autre dossier seulement :
# $env:QUALITY_BENCH_DATA = "<dossier-de-données>"
$env:QUALITY_BENCH_MACHINE = "tour-rtx3050"   # libellé public, avant admission et campagne
```

`QUALITY_BENCH_MACHINE` est obligatoire pour `admission-20261018` et `full-20261018` : sans lui, le manifeste porte le nom d'hôte, que `export-release` refuse de publier (AD-6). Le libellé entre dans `blocking` : le poser avant le premier `generate`, puis ne plus le changer.

Le jeu `set-v3` doit être construit dans `$env:QUALITY_BENCH_DATA` avec sa clé `caps` (reconstruit le 2026-10-18 à la revue ; paliers `num_ctx` dimensionnés pour les plafonds de 4 096). Sinon, sur un arbre propre, avec les sources de `set-v2` déjà présentes (`fetch`, fichiers privés sous `private\`, voir `slm_quality_bench/questions/SOURCES.md`) :

```powershell
.venv\Scripts\python -m slm_quality_bench build-set --set set-v3
```

`build-set` refuse un jeu existant : supprimer d'abord `sets\set-v3\` sous les données et `benchmarks\quality\sets\set-v3\` dans le dépôt, puis vérifier que `git status` ne montre aucun changement sous ce dernier (mêmes entrées et même graine : index identique ; seul `manifest.json` change s'il est construit à un autre commit, à ne pas commiter).

Les 23 modèles (et les candidats, dont `granite4:350m` et `qwen3.5:0.8b`, réintégrés comme références le 2026-10-18) doivent être installés (`ollama pull`) **avant** : aucun téléchargement pendant la campagne. Dans les commandes ci-dessous, `python` est `.venv\Scripts\python`.

## Avant la campagne : admission des candidats (arrêtée)

`admission-20261018` (70 questions `think_off` et 70 `think_on` de `set-v3` par modèle, prévue pour les deux candidats `lfm2.5:24b-a2b-q4_K_M` et `nemotron-3.5-lightning:30b-a3b-q4_K_M`, 280 lignes, ~3 h) devait mesurer le débit, la mémoire de la machine (`memory.jsonl` : RAM et VRAM de référence et de pointe, section « Mémoire de la machine » du rapport `pilot`) et le contexte validé, et donner un aperçu de qualité. **Ne pas la relancer** : elle a été lancée puis arrêtée (voir ci-dessous) et ses lignes sont gardées telles quelles.

`admission-20261018` est **arrêtée après `lfm2.5:24b-a2b-q4_K_M`** par décision d'Anaël du 2026-10-18 (~6 h au lieu des 3 h prévues), après 88 lignes (70 `think_off` et 18 `think_on`) ; la qualité des candidats est jugée sur Artificial Analysis. **Les deux candidats sont écartés de `full-20261018`** (décision du 2026-10-18, détail dans `docs/spec/modeles.md`). La campagne réduite `admission-20261018-nemotron` est gardée par curiosité seulement et **ne bloque pas** `full-20261018` : 15 questions par piste (`think_off`, `think_on`), dont 2 au palier 16 384 et 3 au palier 32 768, pour mesurer le débit, la pointe de RAM et de VRAM et le contexte validé de Nemotron (30 lignes, ~1 h 30). Télécharger d'abord le modèle (`ollama pull`, ~25 Go). Terminal à part, jamais depuis un agent :

```powershell
$env:QUALITY_BENCH_MACHINE = "tour-rtx3050"
.venv\Scripts\python -m slm_quality_bench precheck --campaign admission-20261018-nemotron
.venv\Scripts\python -m slm_quality_bench generate --campaign admission-20261018-nemotron
```

## Contrôler puis générer

```powershell
.venv\Scripts\python -m slm_quality_bench precheck --campaign full-20261018
.venv\Scripts\python -m slm_quality_bench generate --campaign full-20261018
```

`precheck` est en lecture seule et liste tous les refus d'un coup (modèles installés, valeurs `think` et pistes possibles selon `/api/show`, contexte déclaré, GPU, version d'Ollama). Corriger le YAML ou la machine avant `generate`.

## Suivre l'avancement

Dans un second terminal (le générateur n'est pas touché) :

```powershell
.venv\Scripts\python -m slm_quality_bench status --campaign full-20261018 --watch 60 --notify
```

Tableau par modèle (lignes, %, temps réel et prévu), fin estimée par usage de question (le coût d'une ligne dépend du modèle et de l'usage ; fourchette « entre … et … » dès 3 paires modèle-piste mesurées terminées, restant estimé par modèle) et écart avec la fin initiale, alertes (`stalled` après 30 min sans ligne, générateur arrêté, « Ollama ne répond plus »). `--notify` envoie des toasts Windows sur les seuls changements (modèle ou campagne terminé, blocage, dérive de la fin estimée par paliers de 10 %, générateur arrêté, nouvel avertissement Ollama), sans jamais de contenu de question ni de réponse. `--json` écrit l'objet `qb.status/1` (champs documentés dans `slm_quality_bench/monitor/status.py`) pour un outil externe. `status` est en lecture seule : aucun fichier écrit, `generation.lock` jamais pris. Avec `--watch`, `Ctrl+C` sort proprement.

## Arrêt après `granite4.2:8b` et règle de mémoire (décision d'Anaël du 2026-10-27)

Anaël arrête la génération de `full-20261018` (`Ctrl+C`) dès que `granite4.2:8b` est fini : la campagne reste partielle (le rapport gère `--partial`). NE PAS modifier `full-20261018.yaml` : la liste des modèles entre dans `generation_hash`, la changer casserait la reprise et l'empreinte. Les modèles non générés : `gemma4-ud:12b-iq3_xxs` et `bonsai:27b-q1_0` passent dans `admission-20261026` (entrées identiques) ; `ministral-3:8b` (dense, 5,6 Gio avec la vision, déborde dès 4 096) et `ministral3-ud:14b-iq2_m` (dense 40 couches, même cache que granite 8B, à la limite à 8 192, net à 16 384, 14B actifs) sont abandonnés.

Règle de mémoire retenue : un modèle dont les paramètres actifs + cache débordent du GPU (RTX 3050, 8 Go, ~6 Gio utilisables) dès le palier 8 192 (80 % des lignes de `set-v3`) n'est pas testé ; un débordement seulement à 32 768 (4 à 8 % des lignes) est accepté (déjà le cas mesuré de `phi4-mini`, `ministral-3:3b` et d'un `qwen3.5`) ; les experts inactifs d'un MoE sur le CPU sont acceptés (`qwen3.6:35b-a3b`). Cas mesuré qui fonde la règle, `granite4.2:8b` dans cette campagne : 40/41 couches sur le GPU à 8 192, 33/41 à 16 384, 24/41 à 32 768 ; 22 tok/s contre 35 pour `qwen3.5:9b` ; 31,4 h réelles au lieu d'environ 10 projetées ; puissance GPU moyenne 54 W contre 88 à 109 W ailleurs. K2 Horizon 7B en a été retiré pour la même raison. La projection de durée de `status` ne voit pas ce débordement (voir `docs/deferred-work.md`).

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

## Après la campagne : LFM2.5-24B-A2B, K2 Horizon, Ternary Bonsai 2, Flint et Swift 1.5

À la fin de `full-20261018`, relancer la recherche d'une notation indépendante (Artificial Analysis) de `lfm2.5:24b-a2b-q4_K_M` (aucun score au 2026-10-18, sorti le 2026-10-13), puis arbitrer avec Anaël son ajout au banc (voir `docs/deferred-work.md`).

### Décision d'Anaël du 2026-10-26 : `bonsai2-20261023` scindée en deux

Constat : Ollama ne lit le format Q2_0 (les trois Ternary Bonsai 2) qu'à partir de la 0.40.6 (notes de version : « v0.40.6 (16 oct.) : adds q2_0 tensor and file types »), alors que les campagnes sont épinglées sur 0.40.5 comme `full-20261018`. K2 Horizon (architecture `k2-horizon`) est lu depuis la 0.40.4 (issue ollama/ollama#18698 fermée le 2026-10-14 : 3.7B Q4_K_M confirmé ; llama.cpp PR #29535, build b11454) ; le 7B, de même architecture dense, n'a pas de test public : à confirmer par `precheck`. Ce qui suit REMPLACE la composition à quatre modèles de la campagne `bonsai2-20261023` (décisions des 2026-10-23 et 2026-10-24, gardées plus bas pour l'historique). Ordre convenu :

1. fin de `full-20261018` ;
2. juges `opus`, `haiku` puis `opus-replay` sur `full-20261018` : le juge et la génération ne peuvent pas tourner ensemble (`machine.lock`) ;
3. `admission-20261026` en Ollama 0.40.5 ;
4. mise à jour d'Ollama vers 0.40.6 par Anaël (pas avant la fin d'`admission-20261026`) ;
5. `bonsai2-20261023` en 0.40.6.

### K2 Horizon 3.7B, Bolt-E4B, Gemma 12B et Bonsai 27B : campagne `admission-20261026`

Nouvelle campagne (`slm_quality_bench/campaigns/admission-20261026.yaml`), Ollama 0.40.5 et exactement les réglages de `full-20261018` (set-v3, `request`, plafonds, `num_ctx_tiers`, juge `opus`, `gpu_check`) : comparable ligne à ligne. Quatre modèles, par débit présumé décroissant (deux pistes de 800 lignes chacun, soit 6 400 lignes). Décisions d'Anaël du 2026-10-27 : K2 Horizon 7B retiré, Gemma 12B et Bonsai 27B repris de `full-20261018` (voir « Arrêt de `full-20261018` après `granite4.2:8b` » plus bas) :

- `hf.co/IFM/K2-Horizon-3.7B-GGUF:Q4_K_M` (fichier K2-Horizon-4B-Q4_K_M.gguf, 3,16 Go ; dense 3,7B ; Apache 2.0 ; contexte 524 288 ; raisonnement ; indice Artificial Analysis v4.3.2 : 16, variante reasoning ; sorti le 2026-09-03 par l'Institute of Foundation Models (MBZUAI)) ; langue déclarée sur la fiche : anglais seulement ; très verbeux (180 M tokens sur l'indice AA contre une médiane de 74 M) : l'éditeur recommande >= 32 768 tokens de sortie, nos plafonds de 4 096 le sous-évalueront probablement, à noter dans l'analyse ;
- `hf.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF:UD-Q4_K_XL` (4,76 Go, repris de l'ancienne composition de `bonsai2-20261023` : décision du 2026-10-24, famille `nemotron`, référence `gemma4:e4b-it-qat`, chiffres du fournisseur seulement) ;
- `gemma4-ud:12b-iq3_xxs` (entrée identique à celle de `full-20261018`, déjà installé) : estimation de mémoire (pas une mesure) 4,3 Gio, cache surtout en fenêtre glissante (40 couches sur 48, fenêtre 1 024), tout sur le GPU à 4 096 au pilote, à la limite seulement à 32 768 ;
- `bonsai:27b-q1_0` (entrée identique à celle de `full-20261018`, déjà installé) : estimation de mémoire (pas une mesure) 3,5 Gio, hybride qwen35 (16 couches d'attention), à la limite seulement à 32 768.

K2 Horizon 7B (`hf.co/IFM/K2-Horizon-7B-GGUF:Q4_K_M`, 5,59 Go) est RETIRÉ (décision du 2026-10-27, motif dans la règle de mémoire ci-dessous) ; son entrée reste dans `models.yaml`.

K2 : `family: k2horizon` (famille à part, non qwen), deux pistes, valeurs `think` (false, true) À CONFIRMER par `precheck`. Projection de durée, grossière, À MESURER par `status` sur les premières lignes : Bolt 8 à 10 h (`gemma4:e4b-it-qat` : 6,2 h réelles dans `full-20261018`), K2 3.7B 11 à 18 h (`qwen3.5:4b` : 11,4 h ; plus verbeux, plafond : toutes les lignes `think_on` à 4 096 jetons à 58 tok/s), Gemma 12B 10 à 22 h et Bonsai 27B 12 à 27 h. Source des deux derniers : durées prévues par `status --campaign full-20261018 --json` (9,9 h et 12,4 h, base mesurée au pilote) multipliées par 1 à 2,2, le rapport réel / prévu de `qwen3.5:9b` (18,9 h réelles pour 8,6 h prévues ; `gemma4:e4b-it-qat` : 1,2) ; `status` ne voit pas le débordement mémoire (`granite4.2:8b` : 9,7 h prévues, 31,6 h réelles). Total : 41 à 77 h pour les quatre. Téléchargements : K2 3.7B et Bolt (~7,9 Go : 3,16 + 4,76) seulement après la campagne complète ; Gemma 12B et Bonsai 27B sont déjà installés. Dans un terminal à part, jamais par un agent :

```powershell
$env:QUALITY_BENCH_MACHINE = "tour-rtx3050"
.venv\Scripts\python -m slm_quality_bench precheck --campaign admission-20261026
.venv\Scripts\python -m slm_quality_bench generate --campaign admission-20261026
```

Conduite décidée d'avance (accord d'Anaël du 2026-10-26, même règle que pour `bonsai2-20261023`) : si `ollama pull` ou `precheck` refuse un modèle ou une piste sous 0.40.5, le retirer ou restreindre ses `tracks` par une PR AVANT le premier `generate`, avec YAML, tests (`tests/test_campaign_files.py`, `tests/test_release.py`) et docs dans la MÊME PR.

- **Contrôle de Bolt-E4B et de K2 3.7B après leurs premières lignes** : `precheck` (`/api/show`) ne prouve pas que le modèle de conversation honore le paramètre `think` d'Ollama 0.40.5. Dès que `generation.jsonl` compte quelques lignes `think_off` et `think_on` de chacun, comparer (lecture seule, comptes seulement, jamais le texte des réponses) par piste la médiane de `tokens.thinking_est` (nombre de fragments de flux `thinking`, estimation) et de `tokens.completion` (jetons générés). Attendu : `think_off` à `thinking_est` nul ou quasi nul et à `completion` court, `think_on` à `thinking_est` élevé. Si `think_off` raisonne autant que `think_on`, ou si `think_on` ne raisonne pas, créer le fichier `STOP` dans `campaigns\admission-20261026\` et arbitrer avec Anaël : les deux pistes seraient identiques. Précédent : `lfm2.5:8b-a1b-q4_K_M` raisonne en `think_off` (voir `docs/deferred-work.md`).
- Jugement ensuite : le YAML fixe `grading.judge: opus` comme `full-20261018` (même juge exigé pour la comparabilité, décision d'Anaël) ; section non bloquante. **Coût** : couvert par les crédits Opus d'Anaël, renouvelés chaque mois (précision du 2026-10-26) ; vérifier le solde du mois avant de lancer `judge` (repère mesuré : ~2,85 $ pour 1 000 critères ; plafond par `--max-cost-usd`).

### Ternary Bonsai 2 : campagne `bonsai2-20261023` (composition du 2026-10-26)

Décision d'Anaël du 2026-10-23 (sans notation indépendante : aucune page AA, chiffres du fournisseur PrismML seulement) : ajouter trois tailles de Ternary Bonsai 2 (2B, 4B, 9B ; le 27B a été retiré le jour même, voir plus bas), format Q2_0 (le seul que PrismML dit lisible par llama.cpp amont), famille `bonsai2` à part (ni `qwen`, ni `bonsai` du Bonsai 1 bit), par une campagne distincte (`slm_quality_bench/campaigns/bonsai2-20261023.yaml`) : 2B (`hf.co/prism-ml/Ternary-Bonsai-2-2B-gguf:Q2_0`, référence `qwen3.5:2b`), 4B (`...-4B-gguf:Q2_0`, déjà installé, référence `qwen3.5:4b`), 9B (`...-9B-gguf:Q2_0`, référence `qwen3.5:9b`).

**Remplacé le 2026-10-26** : Bolt-E4B (ajout du 2026-10-24, quatre modèles, 38 à 60 h, 6 400 lignes, sous 0.40.5) est passé dans `admission-20261026`. La campagne, qui garde son identifiant, compte maintenant six modèles : les trois Bonsai 2 PLUS leurs trois références rejouées `qwen3.5:2b`, `qwen3.5:4b`, `qwen3.5:9b` (entrées identiques à celles de `full-20261018`), sous `ollama_version: "0.40.6"` (première version qui lit Q2_0 ; seul réglage qui diffère de `full-20261018` ; à confirmer par `precheck`). La comparaison Bonsai 2 contre sa base se fait DANS cette campagne (même moteur) ; contre les autres modèles de `full-20261018` (0.40.5) elle n'est qu'indicative. Ne pas mettre Ollama à jour avant la fin d'`admission-20261026`. Téléchargement : 2B et 9B seulement (~3,1 Go ; le 4B et les `qwen3.5` sont déjà là), après `admission-20261026`. Ordre dans le YAML : chaque Bonsai 2 suivi de sa base (2B, 4B, 9B). Dans un terminal à part, jamais par un agent, après la mise à jour d'Ollama vers 0.40.6 :

```powershell
$env:QUALITY_BENCH_MACHINE = "tour-rtx3050"
.venv\Scripts\python -m slm_quality_bench precheck --campaign bonsai2-20261023
.venv\Scripts\python -m slm_quality_bench generate --campaign bonsai2-20261023
```

`precheck` vérifie qu'Ollama 0.40.6 charge le Q2_0 et lit les valeurs `think` publiées (à confirmer : restreindre les pistes du YAML sinon). Conduite décidée d'avance : si `ollama pull` ou `precheck` refuse une taille, la retirer du YAML par une PR AVANT le premier `generate` (accord donné d'avance par Anaël le 2026-10-23) ; les autres tailles restent. Un retrait met à jour dans la MÊME PR le YAML, les tests et les docs. Jugement ensuite (`grading.judge: opus` comme `full-20261018`, section non bloquante) : comme pour `admission-20261026`, probablement hors des crédits Opus (après le 31/10), coût réel à annoncer à Anaël avant de lancer `judge` (~2,85 $ pour 1 000 critères, plafond par `--max-cost-usd`).

Projection de durée (6 modèles, 9 600 lignes) : **69 à 89 h**, grossière, à mesurer par `status`. Références rejouées : 38,5 h, durées réelles de `full-20261018` (somme de `wall_s`, 800 lignes par piste) ; Bonsai 2 : 31 à 50 h pour les trois, soit 0,8 à 1,3 fois la durée réelle de sa base. La compression ternaire peut changer le débit (fichier plus léger, mais noyaux Q2_0 récents) et la verbosité : les Qwen 3.5 bouclent en `think_on` (43 à 72 % de lignes tronquées aux plafonds de 4 096), ce qui borne la hausse. Le budget de 216 h de `pilot.yaml` ne s'applique pas à cette campagne.

| Taille | Base rejouée, durée réelle | Bonsai 2 estimé |
|---|---|---|
| 2B | `qwen3.5:2b` : 8,2 h (think_off 1,3 h, think_on 6,9 h) | 7 à 11 h |
| 4B | `qwen3.5:4b` : 11,4 h (think_off 2,0 h, think_on 9,4 h) | 9 à 15 h |
| 9B | `qwen3.5:9b` : 18,9 h (think_off 3,5 h, think_on 15,4 h) | 15 à 25 h |
| Total | 38,5 h | 31 à 50 h |

**27B retiré le 2026-10-23 (décision d'Anaël)** : durée projetée non mesurée (30 à 130 h, décharge sur le CPU) et aucun modèle d'origine au banc (Qwen3.8 27B). Il pourra être réexaminé avec une carte graphique à plus de VRAM ou après une mesure de débit (voir `docs/deferred-work.md`).

Flint (`hf.co/unsloth/flint-GGUF`, MoE de 39,8B dont ~2,5B actifs) : rechercher aussi une notation indépendante (aucune au 2026-10-22), puis lancer une campagne d'admission sur le modèle d'`admission-20261018-nemotron`, en `UD-Q3_K_XL` ou `UD-IQ3_XXS`, après avoir vérifié qu'Ollama 0.40.5 charge l'architecture (détail dans `docs/deferred-work.md`). Aucun téléchargement avant la fin de la campagne.

Swift 1.5 Ornith 9B (`hf.co/ukisai/Swift-1.5-Ornith-9B-GGUF:Q4_K_M`, 5,8 Go, UkisAI ; réglage d'Ornith-1.5-9B qui raccourcit le raisonnement) : campagne d'admission courte par curiosité (demande d'Anaël du 2026-10-23), sur le modèle d'`admission-20261018-nemotron`, après Flint (détail dans `docs/deferred-work.md`). Aucun téléchargement avant la fin de la campagne.

## Publier les résultats

```powershell
.venv\Scripts\python -m slm_quality_bench export-release --campaign full-20261018 admission-20261018 --version 0.2.0
```

Hors ligne, sans Ollama ni verrou : écrit `benchmarks/quality/releases/0.2.0/slm-quality-results.json` (`qb.results/1`, schéma `docs/schemas/qb.results-1.schema.json`, AD-18), recalculable à l'identique. Il faut refaire `grade` (et le juge) puis, au besoin, ajouter les modèles au registre `slm_quality_bench/models.yaml` : un modèle absent refuse l'export. Une campagne incomplète est publiée avec `status: partial`. La machine doit être déclarée dans `PUBLIC_MACHINES` (`report/release.py`) : un nom d'hôte refuse l'export. La version publiée (`bench_version`) est lue dans `pyproject.toml` : l'y porter à X.Y.Z avant l'export. L'énergie reste `unvalidated` (valeurs nulles) tant que la mesure de puissance de la machine n'est pas validée. Joindre ensuite le fichier à la release GitHub sous `slm-quality-results.json` et `slm-quality-results-vX.Y.Z.json`.

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

## Revue de la publication qb.results/1

Revue du commit `5e603e4` (branche `feat/publication-qb-results`, 2026-10-18, une passe, second avis compris). Export vérifié en mémoire sur `pilot-20261017` (données réelles, rien écrit) : valide au schéma, octets identiques sur deux appels, `status: partial` (198 lignes en attente du juge).

- medium | second avis 1 | corrigé | sans `$env:QUALITY_BENCH_MACHINE`, le manifeste porte le nom d'hôte (cas de toutes les campagnes existantes), qui finissait dans `machines[]` et `results[].machine` du fichier public (AD-6). Table `PUBLIC_MACHINES` dans `report/release.py` (`tour-rtx3050` : GPU et système) ; une machine absente refuse l'export (code 1). La variable est ajoutée à l'environnement du guide, avant l'admission. `gpu` et `os` ne sont plus nuls.
- low | second avis 2 | rejeté | `set.set_hash` est l'empreinte agrégée du jeu entier, exigée par AD-18 ; elle ne permet de retrouver aucune question.
- low | second avis 3 | corrigé | en-tête de `models.yaml` : null pour l'inconnu, note dans `sources` pour une valeur déduite (paramètres des candidats lus dans le tag) ou incertaine.
- low | second avis 4 | corrigé | provenance exacte : fiches publiques marquées « non rouverte au relevé », catalogue de wavelocalai daté par son commit `ee472c8`.
- low | second avis 5 | corrigé | `bench_version` lu dans `pyproject.toml` du dépôt (installation éditable non rafraîchie), métadonnées installées en repli.
- low | second avis 6 | corrigé | `OSError` à l'écriture : code 1 et message au journal, fichier temporaire supprimé.
- low | revue | corrigé | description du schéma : jointure `results[]` → `models[]` sur (`model`, `digest`), `quality.usages` limité aux usages du jeu pour la piste.
- low | décision d'Anaël 2026-10-18 | fait | `granite4:350m` (piste coupée seule) et `qwen3.5:0.8b` (deux pistes), écartés comme faibles, réintégrés comme références (baselines) des plus petits modèles, aux rangs 2 et 3 de l'ordre de débit (195 et 154 tok/s, derrière LFM 2.5 1.2B Thinking à 230). `num_ctx_max` 32 768 pour les deux, comme les autres : le contexte déclaré de Granite 350M est exactement 32 768, celui de Qwen 0.8B 262 144 ; les paliers `num_ctx` sont ceux de `set-v3`, inchangés. Projection de durée (rapport pilote recalculé hors dépôt avec les 23 tags, débits de l'ancien banc figé, mêmes mesures du pilote `pilot-20261017`) : 106,1 h avant, 108,7 h après (+0,68 h pour Granite 350M, +1,92 h pour Qwen 0.8B), contre 216 h. Même réserve que la projection du pilote : paliers de set-v2, donc peut-être sous-estimée. `generation_hash` de la campagne modifié (aucune campagne lancée).
- low | revue | signalé | `common/registry.py` et `common/paths.py` changent l'empreinte du harnais : aucune campagne en cours, l'admission et `full-20261018` démarreront sur ce code.

## Revue de l'ajout des références

Revue du commit `36e384c` (branche `bench/ajout-baselines-minuscules`, 2026-10-18, une passe, second avis compris). Pistes, ordre de débit, comptes (23 modèles, 16 en `think_on`), projection et absence de `data/` vérifiés.

- low | second avis 1 | corrigé | signal de succès de la story 10 (`docs/spec/stories.yaml`) : 23 modèles en `think_off`, 16 en `think_on`.
- low | second avis 2 | corrigé | commentaire d'`admission-20261018.yaml` (« aux 23 modèles ») ; commentaire seul, section `generation` inchangée.
- low | second avis 3 | rejeté | `ollama show` de la tour confirme `qwen3.5:0.8b` thinking (false, true) et `granite4:350m` sans thinking.
- low | revue | corrigé | `SOURCES.md` (projection « par modèle des 21 ») : 23.
- low | revue | signalé | les 20 et 21 restants de `docs/spec/` (SPEC, statistiques, stories 8, mémo) sont des textes historiques de spec ou de pilote (4 modèles, 21 de pilot.yaml à l'époque) : non touchés.

## Revue de la campagne d'admission réduite de Nemotron

Revue des commits `4f40a80` et `06abab7` (branche `bench/admission-nemotron-reduite`, 2026-10-18, une passe, second avis compris). Effectifs 1 / 9 / 2 / 3 vérifiés sur le `set-v3` construit (graines 0 à 59 rejouées : 50 est la première à donner au moins 2 questions à 16 384 et 3 à 32 768).

- medium | second avis 1 | corrigé | ce document prescrivait encore `precheck` et `generate` d'`admission-20261018` (280 lignes) : réécrit au passé, avec « ne pas la relancer » (88 lignes : 70 `think_off`, 18 `think_on`).
- medium | second avis 2 | corrigé | « contexte 32 768 tenu » : la ligne RAG en `context_exceeded` à 32 768 a un prompt de 31 095 jetons + plafond 2 048 > 32 768 (statut « banc », non imputable au modèle) ; `modeles.md` le dit.
- medium | second avis 3 | corrigé | scores AA (Nemotron 13, LFM2 24B 6, qwen3.6 18, LFM2.5 sans page) : sources et date du relevé citées dans `modeles.md`, sans nouveau fichier `references/`.
- medium | second avis 4 | rejeté | le test des paliers saute en CI faute de `set-v3` : même situation que le test existant de l'admission, accepté ; consigné dans la docstring.
- low | second avis 5 | corrigé | docstring « au moins 2 » alignée sur l'égalité exacte.
- low | second avis 6 | corrigé | « 17 lignes think_on » : 18.
- low | second avis 7 | corrigé | unités de `memory.jsonl` écrites en MiB (18 400 à 26 827 sur 31 861 ; VRAM 6 251).
- low | second avis 8 | corrigé | choix de la graine 50 consigné dans le YAML.

## Revue de la campagne bonsai2-20261023 (composition du 2026-10-24, avant la scission du 2026-10-26)

Revue du commit `faf052e` (branche `bench/campagne-bonsai2`, 2026-10-23, une passe, second avis compris), base à jour d'`origin/main`. Section `generation` identique à `full-20261018` hors modèles (test). Durées relues dans `generation.jsonl` de `full-20261018` (agrégats seulement).

- medium | décision d'Anaël 2026-10-23 | corrigé | famille `bonsai2` à part (ni `qwen`, ni `bonsai`) dans le YAML, `models.yaml`, les tests et les docs. Aucune liste fermée de familles : chaîne non vide dans `config.py`, `registry.py` et les schémas (`models_resolved`, `qb.results/1`) ; `report/calibration.py` et `calibration_measures.py` ne testent que `family == "qwen"`, donc ces modèles comptent non-Qwen dans `qwen_bias` (AD-16). Cohérence registre et campagne vérifiée par `test_shipped_registry_families_match_the_campaign_configuration`.
- decision | Anaël 2026-10-23 | fait | 27B retiré de la campagne (durée projetée non mesurée, 30 à 130 h ; pas de modèle d'origine au banc) : 3 tailles (2B, 4B, 9B), 30 à 50 h ; YAML, `models.yaml`, tests et docs alignés.
- medium | second avis 1 | corrigé | 27B projeté depuis un autre modèle : « non mesuré », 30 à 130 h (~2,4 millions de jetons à 5 à 20 tok/s selon la décharge sur le CPU) ; total 60 à 180 h. Mesure tôt : `size_vram` de la chauffe (`warmups.jsonl`) et débit des premières lignes (`status`), pause et arbitrage au-delà de ~40 h ; reporté dans `docs/deferred-work.md`.
- medium | second avis 2 | corrigé | Q2_0 « lisible par llama.cpp amont » et suffixe « historique » donnés comme affirmations de PrismML (docs.prismml.com/download/models), non vérifiées sous Ollama 0.40.5 ; conduite décidée d'avance : taille refusée au `pull` ou au `precheck` retirée par une PR avant le premier `generate`, accord donné d'avance par Anaël le 2026-10-23.
- medium | second avis 3 | rejeté | les valeurs déduites suivent la convention de l'en-tête de `models.yaml` (valeur déduite avec note « à vérifier par ollama show » dans `sources`, comme les candidats d'admission) ; `moe` ne peut pas être null (booléen exigé par `registry.py`), `capabilities` doit être une liste non vide ; `params_*` et `context_length` acceptent null mais les bases publiées les donnent. Confirmation par `ollama show` reportée dans `docs/deferred-work.md`.
- medium | second avis 4 | corrigé | test tautologique remplacé : la sélection de la campagne appliquée à l'index public (`selected_ids`) ne restreint rien (800 par piste). `build_plan` exige paliers et tailles de prompt, absents de l'index public : il ne tourne que sur le jeu construit, test sauté en CI comme celui de `full-20261018` (passé en local). Le test des valeurs `think` est documenté comme figeant la configuration, pas le comportement réel.
- low | second avis 5 | corrigé | réglé par la famille `bonsai2` (voir plus haut).
- low | second avis 6 | corrigé | `docs/deferred-work.md` : entrée sortie de « Candidats écartés (2026-10-18) » vers une section datée du 2026-10-23.
- low | second avis 7 | corrigé | 4B : 271 lignes `think_on` en 2,8 h, ~10 h au total extrapolées ; fourchette 9 à 14 h.
- low | second avis 8 | corrigé | coût du jugement : `grading.judge: haiku` comme `full-20261018`, section non bloquante, juge fixé à la calibration ; les deux coûts donnés comme ordres de grandeur.
- decision | Anaël 2026-10-24 | fait | NVIDIA Nemotron-3.5-Bolt-E4B ajouté à la campagne non lancée (identifiant gardé exprès) : 4 modèles, 6 400 lignes, 38 à 60 h ; famille `nemotron` (Bonsai 2 : `bonsai2`) ; commit `f71a098`.

### Revue de l'ajout de Bolt-E4B

Revue du commit `f71a098` (branche `bench/bonsai2-ajout-bolt-e4b`, 2026-10-24, une passe, second avis compris).

- low | second avis 1 | corrigé | projection « 30 à 50 h pour 2B, 4B et 9B » sans Bolt : ligne Bolt (8 à 10 h, base `gemma4:e4b-it-qat` 6,2 h réelles) et total 38 à 60 h ajoutés au tableau.
- low | second avis 2 | corrigé | « quatre tailles » (`modeles.md`) et « les trois tailles » (en-tête du YAML) : 3 tailles Bonsai 2 (27B retiré), Bolt-E4B en plus.
- low | second avis 3 | corrigé | décision du 2026-10-24 consignée ci-dessus ; `docs/deferred-work.md` : famille `bonsai2` pour les Bonsai 2, `nemotron` pour Bolt-E4B.
- medium | second avis 4 | corrigé | `precheck` ne prouve pas que `think: false` est honoré par Bolt : contrôle ajouté au guide et au YAML (médiane de `tokens.thinking_est`, fragments de flux, et de `tokens.completion` par piste, lignes de Bolt) ; `STOP` dans `campaigns\bonsai2-20261023\` et arbitrage d'Anaël si `think_off` raisonne autant que `think_on` ou si `think_on` ne raisonne pas. Champs relus dans `generation/conversation.py` (`Outcome.add_call`) ; précédent `lfm2.5:8b-a1b` (raisonne en `think_off`). Contrôle non exécutable ici (aucun Ollama).
- low | second avis 5 | corrigé | `moe`, paramètres et « dense » donnés comme déduits de la fiche Unsloth, « à vérifier par ollama show » (`models.yaml`, YAML, `modeles.md`) ; `moe: false` gardé (booléen exigé).
- low | second avis 6 | signalé | `family: nemotron` range Bolt avec les Nemotron dans les tableaux du rapport (`report/markdown.py`), pas avec Gemma : choix assumé (éditeur), base Gemma 4 notée.
- low | second avis 7 | corrigé | le test de famille recopie le YAML : repéré comme test de configuration dans son commentaire.
- low | second avis 8 | corrigé | référence QAT contre UD-Q4_K_XL : l'écart confond quantification et réentraînement, écrit dans `modeles.md`.
- low | second avis 9 | corrigé | ordre par débit (56 contre 58 tok/s) non robuste, sans effet sur les résultats : écrit dans le YAML.
- low | second avis 10 | corrigé | retrait de piste après `precheck` : tests mis à jour dans la même PR, écrit dans la conduite du guide.

## Revue de la scission de bonsai2-20261023 et d'admission-20261026

Revue du commit `cf56b6f` (branche `bench/campagne-admission-20261026`, 2026-10-26, une passe, second avis compris), base `origin/main` `70e70cb` à jour. Durées de référence : relevé de `generation.jsonl` de `full-20261018` (somme de `wall_s`, 800 lignes par piste, agrégats seulement).

- medium | second avis 1 | corrigé | ancien tableau « 38 à 60 h pour les quatre modèles » (Bolt compris, 9B « pas commencé ») resté sous la composition du 2026-10-26 : remplacé par le tableau des six modèles (bases rejouées et Bonsai 2 estimés).
- medium | second avis 2 | corrigé | `qwen3.5:9b` « sans durée mesurée » et 4B « ~10 h » : durées réelles 8,2 h, 11,4 h et 18,9 h (38,5 h) ; Bonsai 2 31 à 50 h (0,8 à 1,3 fois sa base), total 69 à 89 h au lieu de 63 à 93 h (guide, YAML, `deferred-work.md`).
- medium | second avis 3 | corrigé | juge `opus` gardé (comparabilité, décision d'Anaël) ; jugement d'`admission-20261026` et de `bonsai2-20261023` probablement après le 31/10, hors crédits : coût réel à annoncer à Anaël avant `judge` (~2,85 $ pour 1 000 critères), écrit dans le guide et les deux YAML.
- low | second avis 4 | corrigé | `deferred-work.md` : « Bolt-E4B s'y ajoute le 2026-10-24 » complété par son déplacement du 2026-10-26.
- low | second avis 5 | corrigé | K2 3.7B : base `qwen3.5:4b` à 11,4 h, fourchette 11 à 18 h ; K2 7B 19 à 30 h (`qwen3.5:9b` 18,9 h) ; bornes hautes : toutes les lignes `think_on` au plafond de 4 096 ; total 38 à 58 h au lieu de 33 à 56 h.
- low | second avis 6 | rejeté | pas de test `build_plan` pour `admission-20261026` : il ne tourne que sur le jeu construit (sauté en CI) ; réglages identiques à `full-20261018` vérifiés par test.
- low | revue | corrigé | en-tête de `bonsai2-20261023.yaml` : « mêmes réglages … (version d'Ollama …) » contredisait 0.40.6.
- low | revue | corrigé | K2 3.7B : capacités `[chat, tools, thinking]` comme le catalogue figé de wavelocalai (source ajoutée) ; 7B absent du catalogue, `tools` non retenu faute de source ; à vérifier par `ollama show`.
- low | revue | corrigé | `modeles.md` : Bolt « ajouté à la même campagne » devenu ambigu après déplacement.
