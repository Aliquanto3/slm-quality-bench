# Rapport de la campagne lfm3-20261029

Jeu `set-v3` (empreinte `8081ad7474a1`), manifeste de génération `43c89a46794e`, 1 tirage(s) par question. Seuil α = 0,05 ; bootstrap : 2 000 tirages, graine 20261011.

Unité statistique : (modèle, piste, unité) ; les questions d'une unité sont agrégées par minimum, puis les seeds par moyenne. Une unité sans score (erreur du banc, contexte du banc dépassé ; avec --partial, ligne absente, discordante ou en attente du juge) est écartée et comptée dans « Exclues ». Un contexte du modèle dépassé (le prompt seul ne tient pas dans son contexte maximal déclaré, moins une marge de 256 tokens) vaut un échec (score 0) ; un dépassement dû au plafond de réponse, au palier ou au plafond de la configuration est un contexte du banc dépassé. Un modèle est classé sur un périmètre si sa couverture (unités définies sur unités du périmètre) atteint 90,0 %. Le classement, le meneur, les groupes indiscernables, les comparaisons et la corrélation de Spearman portent sur les modèles classés et sur les unités définies pour chacun d'eux ; le score sur toutes les unités définies de chaque modèle est publié à côté, avec son effectif et sa couverture.

Source `oneruler-fr-cwe` exclue du score et de la couverture de tous les modèles (décision du 2026-10-29) : la tâche ne mesure plus le modèle : prompts sous-estimés d'environ 27 % par est_prompt_tokens, contexte dépassé pour presque tous les modèles (160 context_exceeded sur 248 lignes dès le palier 8 192, troncature silencieuse d'Ollama aux paliers 16 384 et 32 768). Ses lignes restent générées, notées et exportées.

## Complétude

| Contrôle | Valeur |
|---|---|
| Clés attendues | 2 400 |
| Lignes retenues | 2 400 |
| Génération manquante | 0 |
| Génération discordante | 0 |
| Correction manquante | 0 |
| Correction discordante | 0 |
| En attente du juge | 0 |
| Configuration | concordante |

## Modèles

| Modèle | Famille | Pistes | Empreinte | Usage bureautique |
|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | lfm | think_off, think_on | `b36a103fe2f8` | — |
| `lfm3-omni:2b-q4_K_M` | lfm | think_off | `4c0ee9400634` | — |

## Piste sans réflexion (think_off)

### Score global

Méthode : test z sur la différence appariée (erreur-type groupée), intervalle moyenne ± z·ET, IC bootstrap apparié de la différence. Unités : 736, dont 736 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : score global](charts/think_off-global.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 51,1 % | [47,6 % ; 54,6 %] | [47,1 % ; 55,1 %] | 0,018 | 736 | 51,1 % (736) | 100,0 % | 0 | 0 / 0 | 12,6 % (98/776) |
| 2 | 1 | `lfm3-omni:2b-q4_K_M` | 46,1 % | [42,6 % ; 49,6 %] | [42,1 % ; 50,1 %] | 0,018 | 736 | 46,1 % (736) | 100,0 % | 0 | 0 / 0 | 2,8 % (22/776) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | IC bootstrap | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 736 | +5,1 pts | 0,019 | [+1,4 pts ; +8,7 pts] | [+1,3 pts ; +8,6 pts] | 0,46 | 0,007 | 0,007 | oui |

Matrice exploratoire « qui bat qui » (BH) :

- `lfm3:1.7b-q4_K_M` devant `lfm3-omni:2b-q4_K_M` (+5,1 pts, p BH 0,007)

#### Raisonnement (`reasoning`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 90, dont 90 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : raisonnement](charts/think_off-reasoning.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 21,1 % | [14,0 % ; 30,6 %] | [13,1 % ; 32,1 %] | 0,043 | 90 | 21,1 % (90) | 100,0 % | 0 | 0 / 0 | 44,6 % (58/130) |
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 11,1 % | [6,1 % ; 19,3 %] | [5,7 % ; 20,7 %] | 0,033 | 90 | 11,1 % (90) | 100,0 % | 0 | 0 / 0 | 0,8 % (1/130) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 90 | +10,0 pts | 0,052 | [−0,2 pts ; +20,2 pts] | 16 | 7 | 0,08 | 0,093 | 0,093 | non |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Suivi de consignes (`instructions`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 130, dont 130 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : suivi de consignes](charts/think_off-instructions.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 41,5 % | [33,4 % ; 50,1 %] | [32,3 % ; 51,4 %] | 0,043 | 130 | 41,5 % (130) | 100,0 % | 0 | 0 / 0 | 6,9 % (9/130) |
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 38,5 % | [30,5 % ; 47,0 %] | [29,5 % ; 48,3 %] | 0,043 | 130 | 38,5 % (130) | 100,0 % | 0 | 0 / 0 | 13,1 % (17/130) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 130 | +3,1 pts | 0,047 | [−6,2 pts ; +12,4 pts] | 21 | 17 | 0,39 | 0,627 | 0,627 | non |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

Métrique continue : part de consignes suivies (`instructions_followed`), meneur `lfm3:1.7b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 56,1 % | 130 | 56,1 % (130) | 100,0 % | 0 |
| `lfm3-omni:2b-q4_K_M` | 49,9 % | 130 | 49,9 % (130) | 100,0 % | 0 |

Différence au meneur, IC bootstrap apparié à 95 % :

| Modèle | Unités | Différence | IC bootstrap |
|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 130 | +6,2 pts | [−1,7 pts ; +14,4 pts] |

#### Appels d'outils (`tools`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 130, dont 130 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : appels d'outils](charts/think_off-tools.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 66,2 % | [57,7 % ; 73,7 %] | [56,4 % ; 74,7 %] | 0,042 | 130 | 66,2 % (130) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/130) |
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 60,0 % | [51,4 % ; 68,0 %] | [50,2 % ; 69,1 %] | 0,043 | 130 | 60,0 % (130) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/130) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 130 | +6,2 pts | 0,040 | [−1,8 pts ; +14,1 pts] | 18 | 10 | 0,54 | 0,185 | 0,185 | non |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Extraction structurée (`extraction`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 110, dont 110 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : extraction structurée](charts/think_off-extraction.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 49,1 % | [39,9 % ; 58,3 %] | [38,7 % ; 59,6 %] | 0,048 | 110 | 49,1 % (110) | 100,0 % | 0 | 0 / 0 | 15,5 % (17/110) |
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 43,6 % | [34,7 % ; 53,0 %] | [33,5 % ; 54,3 %] | 0,047 | 110 | 43,6 % (110) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/110) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 110 | +5,5 pts | 0,038 | [−2,0 pts ; +12,9 pts] | 12 | 6 | 0,68 | 0,238 | 0,238 | non |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

Métrique continue : F1 (`f1`), meneur `lfm3-omni:2b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | — | 0 | 7,4 % (58) | 85,3 % (hors classement) | 52 |
| `lfm3-omni:2b-q4_K_M` | 12,0 % | 62 | 12,0 % (62) | 91,2 % | 48 |

#### Questions sur documents (RAG) (`rag`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 86, dont 86 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3-omni:2b-q4_K_M`.

![Piste sans réflexion (think_off) : questions sur documents (RAG)](charts/think_off-rag.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 57,0 % | [46,4 % ; 66,9 %] | [45,0 % ; 68,2 %] | 0,053 | 86 | 57,0 % (86) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/86) |
| 2 | 1 | `lfm3:1.7b-q4_K_M` | 33,7 % | [24,6 % ; 44,2 %] | [23,5 % ; 45,8 %] | 0,051 | 86 | 33,7 % (86) | 100,0 % | 0 | 0 / 0 | 4,7 % (4/86) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 86 | +23,3 pts | 0,056 | [+12,2 pts ; +34,3 pts] | 24 | 4 | 0,42 | < 0,001 | < 0,001 | oui |

Matrice exploratoire « qui bat qui » (BH) :

- `lfm3-omni:2b-q4_K_M` devant `lfm3:1.7b-q4_K_M` (+23,3 pts, p BH < 0,001)

Métrique continue : F1 (`f1`), meneur `lfm3-omni:2b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 47,2 % | 50 | 43,7 % (54) | 100,0 % | 32 |
| `lfm3-omni:2b-q4_K_M` | 68,7 % | 50 | 68,7 % (50) | 92,6 % | 36 |

Différence au meneur, IC bootstrap apparié à 95 % :

| Modèle | Unités | Différence | IC bootstrap |
|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 50 | +21,5 pts | [+11,7 pts ; +32,0 pts] |

#### Abstention (`abstention`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 110, dont 110 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : abstention](charts/think_off-abstention.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 63,6 % | [54,3 % ; 72,0 %] | [53,0 % ; 73,1 %] | 0,046 | 110 | 63,6 % (110) | 100,0 % | 0 | 0 / 0 | 9,1 % (10/110) |
| 2 | 2 | `lfm3-omni:2b-q4_K_M` | 38,2 % | [29,6 % ; 47,5 %] | [28,5 % ; 48,9 %] | 0,046 | 110 | 38,2 % (110) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/110) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | b | c | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 110 | +25,5 pts | 0,060 | [+13,8 pts ; +37,1 pts] | 39 | 11 | 0,17 | < 0,001 | < 0,001 | oui |

Matrice exploratoire « qui bat qui » (BH) :

- `lfm3:1.7b-q4_K_M` devant `lfm3-omni:2b-q4_K_M` (+25,5 pts, p BH < 0,001)

#### Rédaction (`writing`)

Méthode : test z sur la différence appariée (erreur-type groupée), intervalle moyenne ± z·ET, IC bootstrap apparié de la différence. Unités : 80, dont 80 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste sans réflexion (think_off) : rédaction](charts/think_off-writing.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 80,4 % | [76,0 % ; 84,7 %] | [75,3 % ; 85,4 %] | 0,022 | 80 | 80,4 % (80) | 100,0 % | 0 | 0 / 0 | 0,0 % (0/80) |
| 1 | 1 | `lfm3-omni:2b-q4_K_M` | 77,6 % | [72,1 % ; 83,1 %] | [71,3 % ; 83,9 %] | 0,028 | 80 | 77,6 % (80) | 100,0 % | 0 | 0 / 0 | 5,0 % (4/80) |

Comparaisons au meneur (Holm sur les m − 1 comparaisons au meneur, m modèles du périmètre) :

| Modèle | Unités | Différence | ET appariée | IC 95 % | IC bootstrap | Corrélation | p | p (Holm) | Distingué |
|---|---|---|---|---|---|---|---|---|---|
| `lfm3-omni:2b-q4_K_M` | 80 | +2,7 pts | 0,027 | [−2,6 pts ; +8,0 pts] | [−2,6 pts ; +8,3 pts] | 0,45 | 0,312 | 0,312 | non |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

### Conclusion transversale (k̂_Bonferroni)

Nombre d'usages, sur 7, où le meneur global `lfm3:1.7b-q4_K_M` bat chaque modèle au seuil α/m = 0,0071 :

| Modèle | Usages gagnés |
|---|---|
| `lfm3-omni:2b-q4_K_M` | 1 / 7 |

### Validation externe (Spearman contre l'indice AA)

Indice AA sans raisonnement, modèles mesurés appariés par tag : 0.

- ρ = —, p unilatérale = —, IC bootstrap à 95 % [— ; —]
- Conclusion : sans conclusion (moins de 8 modèles mesurés).

## Piste avec réflexion (think_on)

### Score global

Méthode : test z sur la différence appariée (erreur-type groupée), intervalle moyenne ± z·ET, IC bootstrap apparié de la différence. Unités : 736, dont 733 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : score global](charts/think_on-global.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 52,6 % | [49,1 % ; 56,2 %] | [49,1 % ; 56,2 %] | 0,018 | 733 | 52,6 % (733) | 100,0 % | 3 | 0 / 3 | 33,4 % (258/773) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Raisonnement (`reasoning`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 90, dont 90 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : raisonnement](charts/think_on-reasoning.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 23,3 % | [15,8 % ; 33,1 %] | [15,8 % ; 33,1 %] | 0,045 | 90 | 23,3 % (90) | 100,0 % | 0 | 0 / 0 | 48,5 % (63/130) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Suivi de consignes (`instructions`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 130, dont 130 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : suivi de consignes](charts/think_on-instructions.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 49,2 % | [40,8 % ; 57,7 %] | [40,8 % ; 57,7 %] | 0,044 | 130 | 49,2 % (130) | 100,0 % | 0 | 0 / 0 | 43,1 % (56/130) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

Métrique continue : part de consignes suivies (`instructions_followed`), meneur `lfm3:1.7b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 50,4 % | 130 | 50,4 % (130) | 100,0 % | 0 |

#### Appels d'outils (`tools`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 130, dont 127 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : appels d'outils](charts/think_on-tools.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 85,0 % | [77,8 % ; 90,2 %] | [77,8 % ; 90,2 %] | 0,032 | 127 | 85,0 % (127) | 100,0 % | 3 | 0 / 3 | 0,0 % (0/127) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Extraction structurée (`extraction`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 110, dont 110 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : extraction structurée](charts/think_on-extraction.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 46,4 % | [37,3 % ; 55,6 %] | [37,3 % ; 55,6 %] | 0,048 | 110 | 46,4 % (110) | 100,0 % | 0 | 0 / 0 | 51,8 % (57/110) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

Métrique continue : F1 (`f1`), meneur `lfm3:1.7b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 0,0 % | 59 | 0,0 % (59) | 100,0 % | 51 |

#### Questions sur documents (RAG) (`rag`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 86, dont 86 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : questions sur documents (RAG)](charts/think_on-rag.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 19,8 % | [12,7 % ; 29,4 %] | [12,7 % ; 29,4 %] | 0,043 | 86 | 19,8 % (86) | 100,0 % | 0 | 0 / 0 | 40,7 % (35/86) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

Métrique continue : F1 (`f1`), meneur `lfm3:1.7b-q4_K_M`.

| Modèle | Moyenne (unités communes) | Unités communes | Moyenne (toutes) | Couverture | Exclues |
|---|---|---|---|---|---|
| `lfm3:1.7b-q4_K_M` | 29,3 % | 74 | 29,3 % (74) | 100,0 % | 12 |

#### Abstention (`abstention`)

Méthode : McNemar exact apparié, intervalle de Wilson. Unités : 110, dont 110 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : abstention](charts/think_on-abstention.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 62,7 % | [53,4 % ; 71,2 %] | [53,4 % ; 71,2 %] | 0,046 | 110 | 62,7 % (110) | 100,0 % | 0 | 0 / 0 | 24,5 % (27/110) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

#### Rédaction (`writing`)

Méthode : test z sur la différence appariée (erreur-type groupée), intervalle moyenne ± z·ET, IC bootstrap apparié de la différence. Unités : 80, dont 80 communes aux modèles classés (classement, meneur et comparaisons). Meneur : `lfm3:1.7b-q4_K_M`.

![Piste avec réflexion (think_on) : rédaction](charts/think_on-writing.svg)

| Groupe | Rang | Modèle | Score (unités communes) | IC 95 % | IC simultané | ET groupée | Unités communes | Score (toutes unités définies) | Couverture | Exclues | Contexte dépassé : modèle / banc | Troncature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | `lfm3:1.7b-q4_K_M` | 69,8 % | [60,7 % ; 78,8 %] | [60,7 % ; 78,8 %] | 0,046 | 80 | 69,8 % (80) | 100,0 % | 0 | 0 / 0 | 25,0 % (20/80) |

Matrice exploratoire « qui bat qui » (BH) :

Aucune paire distinguée après correction de Benjamini-Hochberg.

### Conclusion transversale (k̂_Bonferroni)

Sans objet : moins de deux modèles comparables.

### Validation externe (Spearman contre l'indice AA)

Indice AA en raisonnement, modèles mesurés appariés par tag : 0.

- ρ = —, p unilatérale = —, IC bootstrap à 95 % [— ; —]
- Conclusion : sans conclusion (moins de 8 modèles mesurés).

## Références

Indice AA du 2026-10-17 : `references/aa-2026-10-17.json` (sha256 `14860c29f48f80cb9321905db49e52f812af791891665390732bf9c28a18770b`).
