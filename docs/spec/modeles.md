# Modèles

Le périmètre est tiré des mesures de l'ancien banc sur tour-rtx3050 (`benchmarks/results/tour-rtx3050-a2b6baf5.json`) et des capacités déclarées dans `config/models_catalog.json`. La capacité thinking réelle se relit dans `/api/show` au lancement.

## Les 23 modèles de la campagne

Ils sont classés par débit de génération.

| Modèle | Tag Ollama | tok/s | Thinking | Raisonnement | Consignes | Outils | Rôle |
|---|---|---|---|---|---|---|---|
| LFM 2.5 1.2B Thinking | `lfm2.5-thinking:1.2b` | 230 | oui | 9/14 | 6/8 | 4/4 | |
| Granite 4.0 350M | `granite4:350m` | 195 | non | 3/14 | 3/8 | 3/4 | référence |
| Qwen 3.5 0.8B | `qwen3.5:0.8b` | 154 | oui | 6/14 | 4/8 | 4/4 | référence |
| LFM 2.5 8B-A1B (MoE) | `lfm2.5:8b-a1b-q4_K_M` | 145 | non | 14/14 | 8/8 | 4/4 | pilote |
| Ling 3.0 Tiny | `ling3-tiny:8b-q4_k_m` | 130 | oui | 13/14 | 7/8 | 4/4 | pilote |
| MiniCPM5 2B | `minicpm5:2b-q4_k_m` | 111 | oui | 9/14 | 7/8 | 4/4 | |
| LFM 2.5 2.6B | `LiquidAI/lfm2.5-2.6b` | 103 | oui | 14/14 | 7/8 | 4/4 | pilote |
| Gemma 4 E2B (QAT) | `gemma4:e2b-it-qat` | 103 | oui | 12/14 | 8/8 | 4/4 | pilote |
| Bonsai 8B (1-bit) | `bonsai:8b-q1_0` | 85 | non | 10/14 | 7/8 | 4/4 | |
| Qwen 3.5 2B | `qwen3.5:2b` | 83 | oui | 9/14 | 7/8 | 4/4 | |
| Ministral 3 3B | `ministral-3:3b` | 76 | non | 10/14 | 7/8 | 4/4 | |
| Granite 4.2 3B | `granite4.2:3b` | 75 | oui | 9/14 | 7/8 | 4/4 | |
| Phi 4 Mini 3.8B | `phi4-mini:3.8b` | 68 | non | 9/14 | 7/8 | 2/4 | |
| Nemotron 3 Nano 4B | `nemotron-3-nano:4b` | 65 | oui | 11/14 | 7/8 | 4/4 | |
| Qwen 3.5 4B | `qwen3.5:4b` | 59 | oui | 12/14 | 7/8 | 4/4 | pilote |
| Gemma 4 E4B (QAT) | `gemma4:e4b-it-qat` | 57 | oui | 12/14 | 7/8 | 4/4 | |
| Qwen 3.5 9B | `qwen3.5:9b` | 35 | oui | 13/14 | 7/8 | 4/4 | |
| Qwen 3.6 35B-A3B (MoE) | `qwen3.6:35b-a3b` | 32 | oui | 13/14 | 7/8 | 2/4 | |
| Granite 4.2 8B | `granite4.2:8b` | 31 | oui | 10/14 | 7/8 | 4/4 | |
| Gemma 4 12B (Unsloth IQ3_XXS) | `gemma4-ud:12b-iq3_xxs` | 31 | oui | 14/14 | 7/8 | 4/4 | |
| Ministral 3 8B | `ministral-3:8b` | 29 | non | 13/14 | 7/8 | 4/4 | |
| Bonsai 27B (1-bit) | `bonsai:27b-q1_0` | 27 | oui | 10/14 | 7/8 | 4/4 | |
| Ministral 3 14B (Unsloth IQ2_M) | `ministral3-ud:14b-iq2_m` | 27 | non | 10/14 | 7/8 | 3/4 | |

14 modèles passent les deux pistes, 7 seulement la piste coupée et 2 (LFM 2.5 1.2B Thinking, `lfm2.5-thinking:1.2b`, et LFM 2.5 2.6B, `LiquidAI/lfm2.5-2.6b`) seulement la piste avec réflexion : 21 modèles en piste coupée, 16 en piste avec réflexion.

LFM 2.5 1.2B Thinking : relevé `ollama show` du 2026-10-18 sur la tour (Ollama 0.40.5), capacités completion, tools, thinking, niveaux `true` seulement (défaut true). `/api/show` publie `thinking.values = [true]` et le préflight refuse think false : piste avec réflexion seule, comme LFM 2.5 2.6B.

LFM 2.5 8B-A1B déclare la capacité thinking, mais Ollama le rend avec son renderer intégré `lfm2` (non thinking) : `/api/show` publie `thinking.values = [false]` (code d'Ollama 0.40.5), d'où la piste coupée seule. Au pilote, vérifier qu'il ne réfléchit pas quand même sous `think: false` (parseur `lfm2-thinking`).

Le compte est de 23 : les deux références de la décision du 2026-10-18 (ci-dessous) s'ajoutent aux 21 d'avant. `qwen3.6:35b-a3b`, d'abord écarté pour la RAM, tourne finalement sur la tour (pic à 27,5 Go), et LFM 2.5 8B-A1B est ajouté le 2026-10-17 après son essai sur l'ancien banc (145 tok/s, 100 % sur GPU, contexte validé à 16K).

## Campagne bonsai2-20261023 : Ternary Bonsai 2 (hors des 23)

Décision d'Anaël du 2026-10-26 : la campagne est scindée, car Ollama ne lit Q2_0 qu'à partir de la 0.40.6 (« v0.40.6 : adds q2_0 tensor and file types ») alors que les campagnes sont épinglées sur 0.40.5. `bonsai2-20261023` (identifiant gardé) compte désormais les trois Ternary Bonsai 2 PLUS leurs trois références rejouées (`qwen3.5:2b`, `4b`, `9b`, entrées identiques à `full-20261018`), sous `ollama_version: "0.40.6"` : la comparaison Bonsai 2 contre sa base se fait dans cette campagne (même moteur), contre les autres modèles de `full-20261018` elle n'est qu'indicative. **Révisé le 2026-10-29 (Ollama 0.40.13, dernière version, au lieu de 0.40.6) : la campagne ne compte plus que les trois Bonsai 2 ; les références `qwen3.5:2b` et `4b` sont rejouées dans la campagne `replay-20261029` (`slm_quality_bench/campaigns/replay-20261029.yaml`, Ollama 0.40.13, mêmes réglages, 19,7 h) pour vérifier les bases des Bonsai 2 2B et 4B et la stabilité des Qwen ; `qwen3.5:9b` n'est PAS rejoué (règle du 2026-10-29 : 18,9 h et 32/34 couches sur le GPU à 16 384, donc des couches sur le CPU et moins de 1 Gio de marge : règle non tenue) : le Bonsai 2 9B se compare au `qwen3.5:9b` de `full-20261018`, comparaison indicative †. Ordre : `flint-20261029`, `bonsai2-20261023` puis `replay-20261029`, chacune jugée au juge cloud pendant la génération de la suivante.** Nemotron 3.5 Bolt E4B (tableau ci-dessous) est passé dans `admission-20261026` (section suivante). Ordre : `full-20261018` et ses juges, `admission-20261026` (0.40.5), mise à jour d'Ollama vers 0.40.6 par Anaël, puis `bonsai2-20261023` (ordre du 2026-10-26, remplacé par celui du 2026-10-29 ci-dessus).

Décision d'Anaël du 2026-10-23 : ajouter trois tailles de Ternary Bonsai 2 (2B, 4B, 9B ; le 27B a été retiré le jour même) (PrismML, quantification ternaire, format Q2_0, Apache 2.0, contexte annoncé 262 144), sans notation indépendante (aucune page Artificial Analysis au 2026-10-23). Campagne distincte (`slm_quality_bench/campaigns/bonsai2-20261023.yaml`), mêmes réglages que `full-20261018`, deux pistes ; `family: bonsai2`, famille à part décidée par Anaël le 2026-10-23 (ni `qwen`, lignée de leurs bases, ni `bonsai`, Bonsai 1 bit de première génération ; la mesure `qwen_bias` de la calibration les compte donc non-Qwen). Hors des 23 modèles de `full-20261018`.

| Modèle | Tag Ollama | Taille | Base | Référence au banc |
|---|---|---|---|---|
| Ternary Bonsai 2 2B | `hf.co/prism-ml/Ternary-Bonsai-2-2B-gguf:Q2_0` | 0,55 Go | Qwen3.5 2B | `qwen3.5:2b` |
| Ternary Bonsai 2 4B | `hf.co/prism-ml/Ternary-Bonsai-2-4B-gguf:Q2_0` | 1,21 Go | Qwen3.5 4B | `qwen3.5:4b` |
| Ternary Bonsai 2 9B | `hf.co/prism-ml/Ternary-Bonsai-2-9B-gguf:Q2_0` | 2,56 Go | Qwen3.5 9B | `qwen3.5:9b` † |

† Comparaison indicative : référence mesurée sous Ollama 0.40.5 (`full-20261018`), Bonsai 2 sous 0.40.13.

Sources : fiches Hugging Face `prism-ml/Ternary-Bonsai-2-<taille>-gguf` et docs.prismml.com/download/models (Q2_0 lisible par llama.cpp amont et suffixe `prism-fork-required` « historique » : affirmations du fournisseur, non vérifiées sous Ollama 0.40.5). PTQ1_0 et PQ2_0 exigent les binaires de PrismML : exclus. Les valeurs `think` sont à confirmer par `precheck` et `ollama pull`.

Ternary Bonsai 2 27B (`hf.co/prism-ml/Ternary-Bonsai-2-27B-gguf-dev:Q2_0`) : écarté le 2026-10-23 (durée projetée non mesurée, 30 à 130 h ; pas de modèle d'origine au banc), voir `docs/deferred-work.md`.

## Campagne admission-20261026 : K2 Horizon 3.7B, Nemotron 3.5 Bolt E4B, Gemma 4 12B et Bonsai 27B

Décision d'Anaël du 2026-10-26 : campagne `admission-20261026` (`slm_quality_bench/campaigns/admission-20261026.yaml`), Ollama 0.40.5 et exactement les réglages de `full-20261018`, donc comparable ligne à ligne ; deux pistes. Elle reçoit Bolt-E4B (retiré de `bonsai2-20261023`) et K2 Horizon 3.7B (le 7B est retiré, voir plus bas) de l'Institute of Foundation Models (MBZUAI), dense, Apache 2.0, contexte 524 288, raisonnement, sortis le 2026-09-03, langue déclarée sur la fiche : anglais seulement (`family: k2horizon`, famille à part, non qwen). Architecture `k2-horizon` lue par Ollama depuis la 0.40.4 (issue ollama/ollama#18698 fermée le 2026-10-14 : 3.7B Q4_K_M confirmé ; llama.cpp PR #29535, build b11454) . Très verbeux (180 M tokens sur l'indice AA contre une médiane de 74 M) : l'éditeur recommande >= 32 768 tokens de sortie, nos plafonds de 4 096 les sous-évalueront probablement, à noter.

| Modèle | Tag Ollama | Taille | Indice AA v4.3.2 | Référence au banc |
|---|---|---|---|---|
| K2 Horizon 3.7B (piste `think_off` seule : pas de capacité « thinking » au precheck du 2026-10-27) | `hf.co/IFM/K2-Horizon-3.7B-GGUF:Q4_K_M` (fichier K2-Horizon-4B-Q4_K_M.gguf) | 3,16 Go | 16 (reasoning) | aucune base ; ordre de grandeur `qwen3.5:4b` |
| Nemotron 3.5 Bolt E4B (`nemotron` ; piste `think_off` seule : pas de capacité « thinking » au precheck du 2026-10-27) | `hf.co/unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF:UD-Q4_K_XL` | 4,76 Go | aucun (chiffres du fournisseur) | `gemma4:e4b-it-qat` |
| Gemma 4 12B (Unsloth IQ3_XXS) | `gemma4-ud:12b-iq3_xxs` | 4,3 Gio (estimation) | n/a | repris de `full-20261018` (2026-10-27) |
| Bonsai 27B (1 bit) | `bonsai:27b-q1_0` | 3,5 Gio (estimation) | n/a | repris de `full-20261018` (2026-10-27) ; ARRÊTÉ par `STOP` le 2026-10-29 à 06:35 (157 lignes, 65/65 couches sur le GPU, 28,8 tok/s, 25 à 38 h projetées : plafond de 20 h dépassé) ; EXCLU du rapport (lignes partielles) |

K2 Horizon 7B (`hf.co/IFM/K2-Horizon-7B-GGUF:Q4_K_M`, 5,59 Go, indice AA 21) est retiré le 2026-10-27 : dense, ~144 Kio de cache KV f16 par jeton, il déborderait de la VRAM dès 8 192 comme `granite4.2:8b` (règle de mémoire dans `docs/LANCER-LA-CAMPAGNE.md`). `ministral-3:8b` et `ministral3-ud:14b-iq2_m` de `full-20261018` sont abandonnés pour la même raison ; `full-20261018` s'arrête après `granite4.2:8b`.

Conduite décidée d'avance : si `ollama pull` ou `precheck` refuse un modèle ou une piste sous 0.40.5, le retirer ou restreindre ses pistes par une PR avant le premier `generate`. Aucune référence `references/aa-<date>.json` n'est créée par cette décision (relevé à la main et daté, à faire à part ; les indices 16 et 21 ci-dessus sont cités des fiches, sans fichier de référence).

Bolt-E4B (décision d'Anaël du 2026-10-24, déplacé le 2026-10-26) :

Nemotron 3.5 Bolt E4B : décision d'Anaël du 2026-10-24, ajouté alors à `bonsai2-20261023` (identifiant inchangé), déplacé ici le 2026-10-26. 8B paramètres au total, 4B effectifs, dense, contexte 64K (65 536), texte seul, raisonnement activable, licence OpenMDW-1.1 (Apache 2.0 pour la part Gemma 4), publié sur Hugging Face le 2026-10-23. Chiffres du fournisseur seulement (aucune notation Artificial Analysis de l'E4B) ; NVIDIA le compare à Gemma 4 E4B-it en BF16 et Q4_K_M, pas à la version QAT du banc. Valeurs DÉDUITES de la fiche Unsloth (8B au total, 4B effectifs, dense, base Gemma 4 E4B), à vérifier par `ollama show`. Limite de la comparaison avec la référence `gemma4:e4b-it-qat` : Bolt est en UD-Q4_K_XL (Unsloth), la référence en QAT de Google ; l'écart mesuré confond donc la quantification et le réentraînement de NVIDIA, il ne mesure pas le seul réentraînement. `family: nemotron` range Bolt avec les Nemotron dans les tableaux du rapport (`report/markdown.py`), pas avec les Gemma : choix assumé (éditeur, comme `nemotron-3-nano:4b`), base Gemma 4 notée. Sources : fiche `unsloth/NVIDIA-Nemotron-3.5-Bolt-E4B-GGUF` et unsloth.ai/docs/models/nemotron-3.5-bolt, lues le 2026-10-24.

## Exclus

| Modèle | Raison |
|---|---|
| `minicpm5:1b-q4_k_m` | faible : raisonnement 5/14 |
| `gemma3:1b` | faible : raisonnement 6/14, outils 0/4 |
| `llama3.2:3b` | faible : raisonnement 8/14 (p = 0,016) |
| `olmo-3:7b` | faible : outils 0/4, aiguille 0/3 |
| `ling3-tiny:8b-iq4_xs` | doublon plus lent que `q4_k_m` (118 contre 130 tok/s) |
| `qwen3.5-ud:9b-q3_k_xl` | doublon plus lent que `qwen3.5:9b` (34,8 contre 35,2 tok/s) |
| `gemma4:12b` (Q4_K_M), `saluki:27b-iq2_mix` | supprimés de la tour, à ne pas réinstaller (trop lents) |

**Candidats écartés (décision d'Anaël, 2026-10-18)**, qualité jugée sur Artificial Analysis (index v4.3.2, comme `benchmarks/quality/references/aa-2026-10-17.json`) :

| Modèle | Raison |
|---|---|
| `nemotron-3.5-lightning:30b-a3b-q4_K_M` | 13 sur l'index AA (reasoning, v4.3.2), sous `qwen3.6:35b-a3b` (18, `references/aa-2026-10-17.json`) de même gabarit ; page https://artificialanalysis.ai/models/nemotron-3-5-lightning relue le 2026-10-18. Campagne `admission-20261018-nemotron` gardée par curiosité (débit, mémoire, contexte), non bloquante. |
| `lfm2.5:24b-a2b-q4_K_M` | aucune page AA pour LFM2.5-24B-A2B au 2026-10-18 (sorti le 2026-10-13) ; prédécesseur LFM2 24B A2B à 6 (non-reasoning, https://artificialanalysis.ai/models/lfm2-24b-a2b, relevé le 2026-10-18). Mesuré sur la tour (`memory.jsonl`) : ~44 tok/s, RAM de 18 400 à 26 827 MiB sur 31 861 MiB, VRAM de pointe 6 251 MiB, palier 32 768 chargé et utilisé (une question RAG dépasse ce palier : prompt de 31 095 jetons + plafond de 2 048, statut `context_exceeded` « banc », non imputable au modèle) ; semble raisonner même en `think_off` (27 % de réponses tronquées) ; coût projeté ~22 h dans la campagne complète. À réévaluer après `full-20261018` si une notation indépendante paraît. |

**Références réintégrées (décision d'Anaël, 2026-10-18) :** `granite4:350m` (Granite 4.0 350M, piste coupée seule : pas de thinking) et `qwen3.5:0.8b` (deux pistes) étaient écartés comme faibles. Ils reviennent dans la campagne complète comme références (baselines) des plus petits modèles : ils sont les plus rapides après LFM 2.5 1.2B Thinking, donc leur coût en durée est faible. Ils restent hors du pilote. Relevé `ollama show` du 2026-10-18 (Ollama 0.40.5) : Granite 350M, architecture granite, 352M paramètres, contexte 32 768, BF16 ; Qwen 3.5 0.8B, architecture qwen35, 873M paramètres, contexte 262 144, Q8_0, `thinking` (false, true).

**Critère « faible » :** sur l'ancien banc, le modèle est nettement sous le meilleur sur au moins un usage (Fisher exact, p < 0,02), ou obtient 0 sur un usage. Les cinq modèles à 9/14 en raisonnement (p = 0,041) sont gardés : cet écart reste dans le bruit des tests multiples.

## Pilote

Cinq modèles, dont quatre sur les deux pistes (LFM 2.5 8B-A1B en piste coupée seule) :
- **LFM 2.5 8B-A1B**, **Ling 3.0 Tiny**, **LFM 2.5 2.6B** et **Gemma 4 E2B** forment le front de Pareto précision/vitesse de l'ancien banc. LFM 2.5 8B-A1B (ajouté le 2026-10-17) y est le plus rapide des modèles sans faute : 145 tok/s, 14/14, 8/8, 4/4, 100 % sur GPU.
- **Qwen 3.5 4B** est le meilleur rapport parmi les Qwen. Il en faut un pour mesurer le biais Qwen du juge sur les réponses du pilote.

La projection de durée extrapole aux modèles lents : tokens mesurés au pilote, divisés par le débit de chaque modèle.
