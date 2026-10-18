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
- Écart en % : relatif à la durée prévue totale. Paliers de dérive : toast à chaque palier de 10 % franchi vers le haut et au retour sous +5 % ; une baisse entre deux paliers est silencieuse. Hystérésis de 5 points : un palier n'est quitté vers le bas que sous palier − 5 points, pour qu'un écart qui oscille autour d'un seuil ne déclenche pas un toast à chaque tour.
- Prévu d'un modèle connu : heures de la piste dans la référence, restreintes aux pistes activées du YAML.

## Reports

- Pas de notification sur le taux d'erreurs (seulement affiché).
- Le contrôle de l'affichage réel d'un toast reste à faire à l'œil (un essai du notifier a rendu le code 0).

## Revue

- medium, second avis 1 (paliers de dérive sans hystérésis, toast à chaque tour autour d'un seuil) : corrigé, hystérésis de 5 points (`DRIFT_HYSTERESIS_PCT`), test d'oscillation.
- low, second avis 2 (décalage fixe capté à `now`, heure décalée d'1 h après le 25/10) : corrigé, horodatages convertis au fuseau local de chaque instant quand `now` est à l'heure locale ; test.
- low, second avis 3 (`initial_end` part de la fin de la première requête) : rejeté, écart d'une requête (secondes à minutes) sur ~108 h prévues, négligeable ; `first_line_at` reste l'heure de la ligne, comme documenté.
- low, second avis 4 (lignes sans requête, `wall_s` 0, dans le ratio) : rejeté, la durée prévue d'un modèle mesuré vient du même plan, qui comprend ces lignes ; le biais est transitoire et s'annule à la fin du modèle.
- low, second avis 5 (`--watch` tué par une exception d'un tour) : corrigé, tour en échec journalisé, suivi poursuivi ; Ctrl+C sort toujours en code 0 ; test.
- low, second avis (test manquant sur l'échappement du toast) : corrigé, test du passage par variables d'environnement et de l'échappement XML.
