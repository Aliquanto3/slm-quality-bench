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
- `validated_ctx` de `qb.results/1` lit encore les statuts de génération : une ligne tronquée en silence y compte comme un palier validé.
