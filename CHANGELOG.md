# Journal des modifications

## 0.3.5 - 2026-11-06

### Contenu

- Graphiques SVG de `report/charts.py` migrés vers la charte générique v2.1, thème clair (style « document ») : point du score en `primaire`, IC en `trait-fort` (au moins 3:1 sur `surface`), grille en `trait`, texte en `texte` et `texte-attenue`, fond `surface`. Une seule série par graphique, donc pas de palette de séries ; le renfort de la couleur est la forme (point plein pour le groupe de tête, creux sinon).
- Polices : Sora 600 pour le titre, Atkinson Hyperlegible pour le texte, avec les piles de repli de la charte, en attribut `font-family` du SVG (aucune police n'est embarquée ni enregistrée).
- Constante `PRIMARY_LIGHT` renommée `INTERVAL`.
- Tests : `tests/test_report_render.py` réaligné, avec un test de la palette (couleurs du SVG = jetons de la charte, contraste du texte à 4,5:1) et un test des piles de polices.
- Exemple de rendu produit depuis `benchmarks/quality/full-20261018/summary.json`, sans nouvelle mesure : `docs/media/charte-v2/exemple-think_off-global.svg`.
- Documentation : valeur de primaire alignée dans `ARCHITECTURE-SPINE.md` et dans la spec de la story 6 (section « Rendu » ; les entrées de revue passées restent inchangées).

### Limites

- Les graphiques versionnés sous `benchmarks/quality/*/charts/`, les `report.md` et les données sont des mesures : non régénérés, ils gardent les couleurs de l'ancienne version.
- Historique non migré : les notes de version antérieures, les revues (`docs/architecture/reviews/`), la passe de revue de la story 6 et les rapports sous `docs/mesures/`.
- `charts.py` n'utilise pas matplotlib (SVG écrit à la main) : `charte-document.mplstyle` n'est pas applicable, la palette est celle du style, en dur.
- Le README n'a ni badge, ni schéma mermaid, ni image : rien à migrer.

## 0.3.4 - 2026-11-03

- Références croisées : le projet d'origine `wavelocalai` s'appelle désormais Frugal AI Workbench (`frugal-ai-workbench`). URL, textes et documentation mis à jour. Les provenances de `models.yaml` et la définition figée de la campagne `full-20261018` gardent « wavelocalai ee472c8 » : ce sont des identifiants de données, et les modifier changerait les enregistrements exportés des releases 0.3.x.
- Dossier de données du pilote : `$QUALITY_BENCH_DATA/frugal-ai-workbench/` remplace `wavelocalai/`. Repli sans copie : si le nouveau dossier est absent et l'ancien présent, l'ancien est utilisé avec un `FutureWarning` (à renommer à la main).
- Les résultats publiés sous `benchmarks/quality/releases/` ne sont pas modifiés (historique).
- Le code de `common/` change : le `harness_hash` d'une campagne lancée avec une version antérieure ne correspond plus. Terminez une campagne en cours (`generate`, `judge`) avec la version qui l'a lancée.

## 0.3.3 - 2026-11-03

- Version publique générique : la charte graphique des graphiques SVG passe au bleu pétrole `#0B6B78` (texte `#141A1F`, texte atténué `#4B5560`, traits `#C9D1D3`, intervalle `#B8D6DB`). Les graphiques versionnés sous `benchmarks/quality/*/charts/` sont régénérés depuis les résumés stockés : seules les couleurs changent.
- Retrait de l'affiliation de l'auteur dans `CITATION.cff` et `NOTICE`, et des mentions de la charte précédente dans la documentation.
- Aucun changement de nom, de variable d'environnement ni de dossier de données.
