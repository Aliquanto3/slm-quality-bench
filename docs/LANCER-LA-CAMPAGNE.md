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

## Après la campagne : LFM2.5-24B-A2B et Ternary Bonsai 2 4B

À la fin de `full-20261018`, relancer la recherche d'une notation indépendante (Artificial Analysis) de `lfm2.5:24b-a2b-q4_K_M` (aucun score au 2026-10-18, sorti le 2026-10-13) et de Ternary Bonsai 2 4B (`hf.co/prism-ml/Ternary-Bonsai-2-4B-gguf:Q2_0`, aucune page AA au 2026-10-18), puis arbitrer avec Anaël leur ajout au banc (voir `docs/deferred-work.md`).

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
