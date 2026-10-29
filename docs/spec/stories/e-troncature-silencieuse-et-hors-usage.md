---
title: 'Reclassement des prompts tronqués en silence et marquage « hors usage »'
type: 'feature'
created: '2026-10-29'
status: 'review'
route: 'dispatch'
context:
  - '{project-root}/docs/architecture/ARCHITECTURE-SPINE.md'
  - '{project-root}/docs/deferred-work.md'
---

## Intent

**Problème :** Ollama 0.40.5 coupe en silence le prompt de moitié pour certains modèles quand le prompt et `num_predict` dépassent `num_ctx` (constat du 2026-10-28, `rag/oneruler-fr-cwe` aux paliers 16 384 et 32 768) : la ligne reste `ok` ou `truncated` et compte comme un échec du modèle. Par ailleurs, la règle du 2026-10-29 (marge mémoire et durée) écarte de l'usage bureautique deux modèles déjà testés, `granite4.2:8b` et `qwen3.5:9b`, qui doivent rester au rapport, marqués.

**Approche :** reclassement à la notation (`grade`), sans toucher aux campagnes ; verdict d'usage bureautique dans le registre des modèles, publié par `report` et `export-release`.

## Livré

- `grading/silent_truncation.py` (fonction pure `reclassify`), appelée par `grade` avant la correction. Règle :
  - signature : ligne `ok` ou `truncated` en un seul appel, `tokens.prompt` dans `[num_ctx // 2, num_ctx // 2 + 8]` ;
  - prompt réel de la même question (le plus grand `prompt + prompt_cached` mesuré en un appel dans la campagne, refus d'Ollama compris, borné en bas par `est_prompt_tokens`), majoré de 10 % pour l'écart entre tokenizers, au-delà de `num_ctx - num_predict` ;
  - alors `context_exceeded`, `context_limit = bench` (score nul, hors comparaisons, AD-10).
- Traçabilité : champ facultatif `reclassified: "silent_prompt_truncation"` de `qb.grading/1`, permis seulement sur un `context_exceeded` à limite du banc ; journal de `grade` : « Prompts tronqués en silence reclassés en context_exceeded (bench) : N ; signature sans prompt réel trop long, non reclassées : M ».
- Registre `models.yaml` : champ facultatif `office_use: {fit, reason, decided}` validé par `common/registry.py` (`ModelInfo.office_use`, `office_unfit`), renseigné `fit: false` pour `granite4.2:8b` et `qwen3.5:9b`.
- `qb.results/1` : `models[].office_use` (objet ou `null`, ajout facultatif, schéma `docs/schemas/qb.results-1.schema.json`). `qb.report/1` : `models[].office_use`. Rapport Markdown : colonne « Usage bureautique », phrase qui liste les modèles hors usage et les exclut des recommandations, mention « (hors usage) » dans les tableaux de classement.
- Tests : `tests/test_silent_truncation.py`, `test_grade_command.py`, `test_release.py`, `test_report_render.py`, `test_report_command.py`.

## Choix

- Vérification en lecture seule sur `full-20261018` : 272 lignes reclassées, toutes `rag/oneruler-fr-cwe` aux paliers 16 384 et 32 768 (147 `ok`, 125 `truncated`) ; 25 lignes ont la signature sans être reclassées (abstention OneRuler au palier 16 384 et NIAH au palier 8 192 : taille réelle du prompt).
- Majoration de 10 % : sans elle, 255 lignes seulement. Pour une question CWE au palier 16 384, le plus grand prompt mesuré (tokenizer d'un modèle qui n'a pas tronqué) reste juste sous `num_ctx - num_predict` alors que des tokenizers qui comptent davantage ont tronqué. Les prompts d'abstention (moins de 10 000 au palier 16 384) restent loin du seuil majoré.
- `tokens.prompt` seul pour la signature (deux lignes portent 7 jetons en cache et resteraient sinon hors de la fenêtre) ; `prompt + prompt_cached` pour le prompt réel (mesure d'AD-7).
- Campagne notée seule : `grade` reste une fonction de ses entrées. Dans une campagne à un seul modèle qui tronque en silence, le prompt réel n'est pas mesuré et `est_prompt_tokens` (sous-estimé de 27 % sur OneRuler) ne suffit pas : la ligne n'est pas reclassée, mais comptée dans le journal.
- Lignes multi-appels exclues des deux côtés : leurs prompts sont des sommes sur plusieurs appels.
- Étiquettes `grader` inchangées : le champ `reclassified` dit quelle règle a produit la ligne.
- Le rapport de campagne ne produit aucune liste de recommandation : les modèles hors usage y restent classés (statistiques inchangées), marqués. L'exclusion du « que choisir » s'applique au rapport final hors dépôt, qui lit `office_use`.

## Reports

- Points 2 et 3 de la section CWE de `docs/deferred-work.md` (sortie de `rag/oneruler-fr-cwe` du score RAG commun, estimation des prompts pour `set-v4`).

## Revue

Revue du 2026-10-29 (Opus), branche rebasée sur `origin/main` (`a6fa30c`, PR #33) sans conflit. Mesure sur une copie hors dépôt de `set-v3`, `full-20261018` et `admission-20261026` (`grade` puis `load_inputs(partial=True)` et `build_summary`, sans écriture d'export) ; « avant » = `grade` sans reclassement (comportement d'`origin/main`).

Reclassées : 272 lignes sur `full-20261018` (32 pour chacun de `gemma4:e2b-it-qat`, `gemma4:e4b-it-qat`, `nemotron-3-nano:4b`, `qwen3.5:0.8b`, `qwen3.5:2b`, `qwen3.5:4b`, `qwen3.5:9b`, `qwen3.6:35b-a3b`, 16 pour `ministral-3:3b`), 32 sur `admission-20261026` (`gemma4-ud:12b-iq3_xxs`). Le compte de 272 dépend des données de campagne : aucun test sans `data/` ne peut le fixer ; il est reproduit ici.

Effet sur le RAG (seuil `common_min_coverage` = 0,9), avant → après :

| Campagne, piste | Unités communes | Éligibles | Détail |
|---|---|---|---|
| full, `think_off` | 91 → 99 | 12 → 3 (sur 21) | les 9 modèles reclassés passent de 0,927 à 0,782 de couverture et perdent l'éligibilité ; restent `lfm2.5:8b-a1b-q4_K_M`, `minicpm5:2b-q4_k_m`, `phi4-mini:3.8b` ; moyennes de ces derniers en baisse (CWE entre dans leurs unités communes) |
| full, `think_on` | 91 → 96 | 11 → 5 (sur 16) | 8 modèles reclassés : 0,927 → 0,827, inéligibles ; `granite4.2:3b` et `granite4.2:8b` deviennent éligibles (0,873 → 0,923) |
| admission, `think_off` | 102 → 110 | 2 → 1 | `gemma4-ud:12b-iq3_xxs` 0,927 → 0,782, inéligible |
| admission, `think_on` | 102 → 86 | 1 → 1 | seul modèle de la piste : CWE sort des unités communes |

Score global : couvertures en baisse d'environ 2 points pour les modèles reclassés (0,99 → 0,97), éligibilités et rangs inchangés.

| Sévérité | Source | Constat | Suite |
|---|---|---|---|
| medium | second avis 1 | Le reclassement rend nulles les unités CWE des seuls modèles qui ont tronqué : leur couverture RAG tombe sous 0,9, ils sortent du classement RAG au lieu que CWE sorte des unités communes (tableau ci-dessus). | Confirmé, mesuré ; règle inchangée sur consigne. **Point ouvert pour Anaël** : sortir `rag/oneruler-fr-cwe` des paliers 16 384 et 32 768 du score RAG commun (point 2 de la section CWE de `deferred-work.md`), ou exclure du calcul de couverture les unités à limite du banc partagée, avant de publier un classement RAG. |
| low | second avis 2 | `validated_ctx` de `qb.results/1` comptait une ligne reclassée comme palier validé. | Corrigé : `release.py` lit le statut noté (`inputs.rows`) ; test `test_reclassified_lines_do_not_validate_their_context`. |
| low | second avis 3 | `office_use: null` refusé alors que le schéma l'accepte. | Corrigé : `null` = aucun verdict ; test `test_registry_office_use_null_means_no_verdict`. |
| low | second avis 4 | Docstring « refus d'Ollama compris » imprécise. | Corrigé (commentaire). Constat en partie écarté : sur `full-20261018`, 278 lignes `context_exceeded` ont `calls = 1` et un prompt mesuré (seules 48 ont `calls = 0`, prompt 0) ; le test de `test_grade_command.py`, refus en un appel au prompt mesuré, est donc réaliste et reste tel quel. |
| low | second avis 5 | « exclus de toute recommandation » alors que le rapport n'en produit pas. | Corrigé : « à exclure des recommandations ». |
| low | second avis 6 | Registre lu au moment du `report` sans empreinte. | Écarté : aucun champ d'empreinte de configuration dans `qb.report/1`, et le verdict lu est recopié tel quel dans `summary.json` (`models[].office_use`), ce qui trace la valeur utilisée. |
| low | second avis 7 | Aucune trace du reclassement dans `qb.report/1` ni le Markdown. | Corrigé : `models[].silent_truncations` (compte, facultatif au schéma), phrase du rapport Markdown qui liste les comptes non nuls ; test `test_report_counts_silently_truncated_lines_per_model`. |
| — | revue | Complexité : 0 constat (reclassement, compte et filtre en O(n)). | — |
