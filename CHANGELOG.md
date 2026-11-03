# Journal des modifications

## 0.3.4 - 2026-11-03

- Références croisées : le projet d'origine `wavelocalai` s'appelle désormais Frugal AI Workbench (`frugal-ai-workbench`). URL, textes et documentation mis à jour. Les provenances de `models.yaml` et la définition figée de la campagne `full-20261018` gardent « wavelocalai ee472c8 » : ce sont des identifiants de données, et les modifier changerait les enregistrements exportés des releases 0.3.x.
- Dossier de données du pilote : `$QUALITY_BENCH_DATA/frugal-ai-workbench/` remplace `wavelocalai/`. Repli sans copie : si le nouveau dossier est absent et l'ancien présent, l'ancien est utilisé avec un `FutureWarning` (à renommer à la main).
- Les résultats publiés sous `benchmarks/quality/releases/` ne sont pas modifiés (historique).
- Le code de `common/` change : le `harness_hash` d'une campagne lancée avec une version antérieure ne correspond plus. Terminez une campagne en cours (`generate`, `judge`) avec la version qui l'a lancée.

## 0.3.3 - 2026-11-03

- Version publique générique : la charte graphique des graphiques SVG passe au bleu pétrole `#0B6B78` (texte `#141A1F`, texte atténué `#4B5560`, traits `#C9D1D3`, intervalle `#B8D6DB`). Les graphiques versionnés sous `benchmarks/quality/*/charts/` sont régénérés depuis les résumés stockés : seules les couleurs changent.
- Retrait de l'affiliation de l'auteur dans `CITATION.cff` et `NOTICE`, et des mentions de la charte précédente dans la documentation.
- Aucun changement de nom, de variable d'environnement ni de dossier de données.
