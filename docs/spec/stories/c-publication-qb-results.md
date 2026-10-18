---
title: 'Publication des résultats qb.results/1 et registre des modèles'
type: 'feature'
created: '2026-10-18'
status: 'review'
route: 'dispatch'
context:
  - '{project-root}/docs/architecture/ARCHITECTURE-SPINE.md'
---

## Intent

**Problème :** wavelocalai doit consommer les résultats du banc par un fichier publié, au schéma documenté, sans dépendre du code ni des fichiers internes (CAP-9, CAP-10, AD-18).

**Approche :** un registre versionné des modèles (`models.yaml`, `qb.models/1`), un schéma JSON `qb.results/1` et une commande hors ligne `export-release` qui assemble les statistiques d'AD-17, le débit, la mémoire et l'énergie des campagnes nommées.

## Livré

- `slm_quality_bench/models.yaml` et `common/registry.py` (`load_models`, clés fermées, `null` pour une valeur inconnue, source datée obligatoire) : les 21 modèles de `pilot.yaml` à l'époque (23 depuis le 2026-10-18) et les deux candidats d'`admission-20261018`.
- `docs/schemas/qb.results-1.schema.json` (2020-12, objets fermés).
- `report/release.py` : `export-release --campaign <c>… --version X.Y.Z` écrit `benchmarks/quality/releases/<version>/slm-quality-results.json` en JSON canonique (AD-4), sans retour à la ligne ni horodatage d'exécution. `paths.release_path`, dossier `releases` réservé.
- `tests/test_release.py` : registre, export validé par le schéma, octets identiques, rien de privé, campagne partielle, énergie, fautes attrapées par le schéma.

## Choix là où AD-18 laisse une marge

- Machine : `id` = `label` = `blocking.machine`, qui doit figurer dans `PUBLIC_MACHINES` (`report/release.py`, libellé public posé par `$env:QUALITY_BENCH_MACHINE`) : un nom d'hôte n'est jamais publié (AD-6), l'export refuse ; `gpu` et `os` viennent de cette table ; `ram_mib` et `vram_mib` = totaux de `memory.jsonl`.
- `prefill_tok_s`, `load_time_ms`, `model_size_mib`, `model_vram_mib` : dernière chauffe au palier de référence (4 096), communs aux deux pistes ; `decode_tok_s` : tokens / temps de décodage cumulés par piste.
- `validated_ctx` : plus grand `num_ctx` d'une ligne de génération du modèle hors `context_exceeded` et `error`.
- `energy.status` : `unavailable` sans puissance relevée, `unvalidated` sinon, `measured` seulement pour une machine de `VALIDATED_ENERGY_MACHINES` (vide).
- `quality.usages.writing.status` : `final` si campagne et piste complètes et jugement présent, `provisional` sinon.
- Score et intervalles : unités communes du rapport ; `null` pour un modèle non classé.

## Reports

Voir `docs/deferred-work.md` (« Publication qb.results/1 ») : rebranchement du juge sur le registre, valeurs du registre à vérifier par `ollama show`.
