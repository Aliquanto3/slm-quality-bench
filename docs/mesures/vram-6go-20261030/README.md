# Essai de charge sur 6 Go de mémoire vidéo (2026-10-30)

Les 14 modèles de la frontière de Pareto des résultats v0.3.1, rechargés sur un second poste. L'essai vérifie que les modèles tiennent en mémoire vidéo et relève leur débit. Il ne note aucune réponse : les scores restent ceux de la tour (RTX 3050 8 Go). Ces mesures ne font pas partie des campagnes ni de l'export `qb.results/1`.

## Conclusion

- 13 modèles sur 14 tiennent entièrement sur le GPU jusqu'à leur contexte maximal testé (64K, 32K pour Granite 4.0 350M). Qwen 3.6 35B-A3B ne tient pas : 14 % sur le GPU dès 4K, essai arrêté à ce palier.
- Six modèles demandent `num_gpu: 999` pour y parvenir. Sans ce réglage, Ollama garde trop de marge : Nemotron 3.5 Bolt E4B reste à 57 % sur le GPU à 4K et 46 % à 64K.
- Nemotron 3.5 Bolt E4B à 64K : 5 861 Mio avec `num_gpu`, soit 283 Mio de marge, et 50 jetons/s. Jusqu'à 16K, il garde 1 099 Mio libres.

## Machine et protocole

- Asus TUF Gaming A17, RTX 3060 Laptop (6 144 Mio), Windows 11, Ollama 0.40.13. La plupart des scores ont été mesurés sous Ollama 0.40.5. Mémoire vidéo à 0 Mio au repos, sans doute parce que le Radeon intégré gère l'affichage.
- Un modèle chargé à la fois, déchargé entre deux paliers. Paliers : 4K, 8K, 16K, 32K et 64K, sans dépasser le contexte du modèle.
- Prompt synthétique en français (paragraphe répété, sans donnée du banc), suivi d'une demande de résumé. Température 0, graine 0, raisonnement coupé quand le modèle le permet.
- Série par défaut : 48 jetons générés, contexte rempli à 40 ou 50 % environ.
- Série `num_gpu: 999` : 128 jetons générés, contexte rempli à 70 % environ. Elle porte sur les modèles qui débordaient par défaut.
- Mesures : part sur le GPU (`/api/ps`), pic de mémoire vidéo de la carte (`nvidia-smi`, une lecture par seconde), débit de génération (réponse d'Ollama).

## Part du modèle sur le GPU, réglages par défaut

| Modèle | 4K | 8K | 16K | 32K | 64K |
|---|---|---|---|---|---|
| Nemotron 3.5 Bolt E4B | 57 % | 55 % | 54 % | 50 % | 46 % |
| Gemma 4 E4B (QAT) | 100 % | 100 % | 100 % | 47 % | 42 % |
| Qwen 3.5 4B | 100 % | 100 % | 100 % | 79 % | 62 % |
| Gemma 4 E2B (QAT) | 100 % | 100 % | 100 % | 100 % | 100 % |
| MiniCPM5 2B (‡) | 100 % | 100 % | 100 % | 100 % | 93 % |
| LFM 2.5 2.6B | 100 % | 100 % | 100 % | 100 % | 100 % |
| LFM3 1.7B | 100 % | 100 % | 100 % | 100 % | 100 % |
| LFM3 Omni 2B | 100 % | 100 % | 100 % | 100 % | 100 % |
| LFM 2.5 1.2B Thinking | 100 % | 100 % | 100 % | 100 % | 100 % |
| LFM 2.5 8B-A1B | 77 % | 76 % | 74 % | 70 % | 66 % |
| Ling 3.0 Tiny (‡) | 85 % | 84 % | 83 % | 81 % | 77 % |
| Qwen 3.5 0.8B | 100 % | 100 % | 100 % | 100 % | 100 % |
| Granite 4.0 350M | 100 % | 100 % | 100 % | 100 % | — |
| Qwen 3.6 35B-A3B | 14 % | — | — | — | — |

Qwen 3.6 35B-A3B : arrêt au premier débordement. Granite 4.0 350M : contexte limité à 32K.

## Pic de mémoire vidéo et débit avec `num_gpu: 999`

Tous ces paliers sont à 100 % sur le GPU.

| Modèle | 4K | 8K | 16K | 32K | 64K |
|---|---|---|---|---|---|
| Nemotron 3.5 Bolt E4B | 4841 Mio, 62 j/s | 4907 Mio, 61 j/s | 5045 Mio, 59 j/s | 5315 Mio, 56 j/s | 5861 Mio, 50 j/s |
| Gemma 4 E4B (QAT) | 4241 Mio, 72 j/s | 4309 Mio, 71 j/s | 4445 Mio, 68 j/s | 4717 Mio, 64 j/s | 5261 Mio, 56 j/s |
| Qwen 3.5 4B | 3773 Mio, 76 j/s | 3993 Mio, 74 j/s | 4169 Mio, 71 j/s | 4697 Mio, 65 j/s | 5753 Mio, 57 j/s |
| LFM 2.5 8B-A1B | 5157 Mio, 178 j/s | 5209 Mio, 178 j/s | 5311 Mio, 170 j/s | 5519 Mio, 159 j/s | 5937 Mio, 140 j/s |
| Ling 3.0 Tiny (‡) | 4747 Mio, 159 j/s | 4777 Mio, 160 j/s | 4839 Mio, 156 j/s | 4963 Mio, 152 j/s | 5211 Mio, 137 j/s |
| MiniCPM5 2B (‡) | 1691 Mio, 129 j/s | 1927 Mio, 125 j/s | 2279 Mio, 113 j/s | 2983 Mio, 94 j/s | 4271 Mio, 70 j/s |

## Pic de mémoire vidéo et débit, réglages par défaut

Modèles qui tiennent sans réglage.

| Modèle | 4K | 8K | 16K | 32K | 64K |
|---|---|---|---|---|---|
| Gemma 4 E2B (QAT) | 2801 Mio, 6 j/s | 2831 Mio, 124 j/s | 2887 Mio, 119 j/s | 3001 Mio, 116 j/s | 3225 Mio, 109 j/s |
| LFM 2.5 2.6B | 1865 Mio, 131 j/s | 2027 Mio, 124 j/s | 2171 Mio, 127 j/s | 2459 Mio, 121 j/s | 3035 Mio, 112 j/s |
| LFM3 1.7B | 1287 Mio, 180 j/s | 1423 Mio, 178 j/s | 1533 Mio, 168 j/s | 1757 Mio, 166 j/s | 2477 Mio, 150 j/s |
| LFM3 Omni 2B | 2999 Mio, 194 j/s | 3337 Mio, 187 j/s | 3447 Mio, 182 j/s | 3671 Mio, 176 j/s | 4801 Mio, 160 j/s |
| LFM 2.5 1.2B Thinking | 937 Mio, 289 j/s | 1065 Mio, 285 j/s | 1177 Mio, 296 j/s | 1401 Mio, 284 j/s | 2113 Mio, 254 j/s |
| Qwen 3.5 0.8B | 1711 Mio, 200 j/s | 1393 Mio, 174 j/s | 1987 Mio, 169 j/s | 2275 Mio, 182 j/s | 2845 Mio, 170 j/s |
| Granite 4.0 350M | 943 Mio, 241 j/s | 1089 Mio, 231 j/s | 1329 Mio, 211 j/s | 1809 Mio, 180 j/s | — |

## Limites

- Une génération courte par palier : l'essai ne prouve pas la stabilité sur des heures.
- Contexte jamais rempli à 100 %, et remplissage différent entre les deux séries : leurs débits ne se comparent pas strictement.
- Un écran branché sur la carte NVIDIA ou une autre application sur le GPU réduit la marge.
- ‡ MiniCPM5 2B et Ling 3.0 Tiny : les tags du banc (`minicpm5:2b-q4_k_m`, `ling3-tiny:8b-q4_k_m`) n'existent plus au registre d'Ollama. L'essai utilise les fichiers Q4_K_M des dépôts officiels (`openbmb/MiniCPM5-2B-GGUF`, `inclusionAI/Ling-3.0-tiny-GGUF`), peut-être différents de ceux du banc.
- Une série intermédiaire, mal calibrée (contexte rempli à 25 % environ), a été écartée et n'est pas publiée.

## Données

- `reglages-defaut.jsonl` : série par défaut.
- `num-gpu-force.jsonl` : série avec `num_gpu: 999`.

Champs : `m` modèle, `ctx` contexte, `base` et `peak` mémoire vidéo en Mio, `size` et `size_vram` en octets, `prompt` et `eval` jetons, `tps` et `prompt_tps` jetons/s, `wall` durée en secondes, `done` raison d'arrêt.
