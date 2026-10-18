---
title: 'Commande status : suivi en direct d''une campagne de génération'
type: 'feature'
created: '2026-10-18'
status: 'review'
route: 'dispatch'
context:
  - '{project-root}/docs/architecture/ARCHITECTURE-SPINE.md'
---

## Intent

**Problème :** la campagne `full-20261018` (23 modèles, environ 108 h) tourne dans un terminal à part ; il faut un tableau consultable d'un regard, des toasts sur les événements marquants et une sortie JSON stable pour un outil externe.

**Approche :** sous-commande `status`, strictement en lecture seule (aucun fichier écrit, `generation.lock` jamais pris, aucun réseau), dans `slm_quality_bench/monitor/` (hors `HARNESS_DIRS` : la reprise de la campagne n'est pas bloquée).

## Livré

- `monitor/status.py` : lecture incrémentale de `generation.jsonl` en mémoire (fragment final et lignes illisibles ignorés, dédoublonnage par `key`), plan attendu par `build_plan` (même sélection que `generate`), durée prévue de `projection.models[]` du rapport du pilote (`--baseline`), modèles absents estimés par la médiane de la piste (`"baseline": "estimated"`), ratio de vitesse, fin estimée, écart, `stalled`, taux d'erreurs sur 50 lignes, journal (`Ollama ne répond plus`, dernier déchargement), verrou et `STOP`. Schéma `qb.status/1` documenté dans la docstring du module.
- `monitor/notify.py` : protocole `Notifier`, toast WinRT via `powershell -NoProfile` (texte passé par variables d'environnement, échappé en XML, AppId `Microsoft.Windows.Shell.RunDialog`), détecteur de transitions en mémoire (première observation silencieuse).
- `monitor/commands.py` : options `--json`, `--watch`, `--notify`, `--baseline`, `--stall-minutes` ; codes 0 et 2.
- `tests/test_monitor.py` ; `docs/LANCER-LA-CAMPAGNE.md` (« Suivre l'avancement »).

## Choix

- Verrou : le fichier `generation.lock` persiste (vidé à la libération), donc sa seule présence ne dit rien. Sous Windows, détention sondée par lecture de l'octet verrouillé par `FileLock` (refusée tant qu'un autre processus le tient) ; ailleurs, fichier non vide.
- Écart en % : relatif à la durée prévue totale. Paliers de dérive : toast à chaque palier de 10 % franchi vers le haut et au retour sous 10 % ; une baisse entre deux paliers est silencieuse.
- Prévu d'un modèle connu : heures de la piste dans la référence, restreintes aux pistes activées du YAML.

## Reports

- Pas de notification sur le taux d'erreurs (seulement affiché).
- Le contrôle de l'affichage réel d'un toast reste à faire à l'œil (un essai du notifier a rendu le code 0).
