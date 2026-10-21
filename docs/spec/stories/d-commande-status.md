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
- Fin estimée par usage (`eta_method` `per_usage`) : le ratio réel/prévu global se trompait (0,2 à 2,4 selon le modèle, paires `estimated` qui le faussent, blocs d'usage de coût très inégal). `eta` = maintenant + reste par usage × prévu × facteur `F(piste, usage)` calibré sur les paires mesurées terminées, facteur propre rétréci pour la paire en cours ; ajouts `eta_low`, `eta_high` (quartiles des écarts par paire en validation croisée, `null` sous 3 paires terminées), `remaining_h` (global et par modèle), `eta_method`. `speed_ratio` inchangé. Limite : avec peu de paires mesurées, la variation entre modèles (verbosité) reste la première source d'erreur.

## Revue de l'estimation par usage

Revue du commit `dc8fb0e` (base `origin/main` à jour, aucun rebase nécessaire). Rétro-test hors dépôt sur `full-20261018` (5 modèles finis, horizon borné aux lignes faites après chaque coupe, réel = Σ `wall_s`) et validation croisée sur les 4 paires mesurées terminées (chacune prévue sans elle : Σ prévu 7,95 h pour 7,58 h réelles, +5 %).

- medium | second avis 4 (fourchette calibrée sur les paires qui ont fixé F, comprimée) | corrigé | écart de chaque paire mesuré avec `F` calibré sans elle (validation croisée) ; avant, fourchette de largeur nulle à certaines coupes (`[6,1-6,1]`) ; test à oracle calculé à la main.
- medium | second avis 2 (replis `track_ratio`/`global_ratio` sur des paires à 1 ligne) | corrigé | pas de chargement à froid mesuré (première ligne de chaque paire dans la norme), mais en validation croisée une piste sans autre paire retombait sur une paire à 1 ligne (écart de 24,8) ; replis calculés sur les seules paires de calibration.
- medium | revue (paire en cours dans la calibration) | corrigé | une paire en cours n'a vu que les premiers blocs d'usage du plan (les moins coûteux) : la médiane de `F` et les replis sautaient à chaque paire, d'où 15 toasts de dérive simulés sur l'historique (29 sauts ≥ 5 points entre deux tours de 20 lignes) contre 10 avec l'ancien calcul ; calibration sur les paires terminées seulement : 1 toast, 4 sauts, rétro-test inchangé (erreur moyenne 38 % contre 37 %) ; test.
- medium | second avis 1 (F brut sans rétrécissement, une paire fixe F) | rejeté | sans effet mesurable : rétrécissement vers le ratio de piste (−1 point) ou ratio pondéré par lignes (−0 à +2 points) ; le biais vient de la variation entre modèles (ling3-tiny think_off 2,5 fois plus rapide que lfm2.5:8b au regard du pilote), pas de la forme par usage. Rétrécir vers 1 (pilote juste) réduit l'erreur des coupes (19 %) mais sous-estime de 25 % en validation croisée : sur-ajustement à une paire, écarté.
- medium | second avis 3 (piste sans référence ni ligne : prévu 0, fin = maintenant) | corrigé | repli sur la médiane des références des autres pistes ; 0 seulement sans aucune référence ni ligne (même défaut dans l'ancien calcul) ; test.
- medium | second avis 6 (seuils de `notify.py` réglés sur l'ancien estimateur) | corrigé en partie | seuils inchangés (relatifs au prévu total, même sens) ; l'instabilité qui multipliait les toasts est traitée par la calibration sur paires terminées (ci-dessus).
- low | second avis 5 (paire en cours sans incertitude dans la fourchette) | corrigé | bornes appliquées à son reste, atténuées par le poids de ses lignes (`50/(n + 50)`) ; test.
- low | second avis 7 (`rest_override` sans appelant) | corrigé | gardé pour le rétro-test, mais il était faux : reste ramené au reste complet de la paire et paires absentes comptées en entier ; c'est désormais un horizon exact ; test.
- low | second avis 8 (tests manquants) | corrigé | tests fourchette en validation croisée, paire en cours, horizon, repli de prévu.
- low | second avis 9 (« ~0 min » à prévu nul) | corrigé | conséquence du constat 3.
- low | second avis (Pyright, code inatteignable `status.py:254`) | rejeté | branche non Windows de `lock_held`, inatteignable pour Pyright seulement sous `win32` ; antérieur au commit.
- Complexité : 0 constat | revue | signalé | `estimate_remaining` est linéaire en lignes (11 ms à 5 700 lignes, 53 ms à 28 500) ; écart propre de paire calculé sur les sommes par usage plutôt que ligne à ligne.
- info | revue | signalé | rétro-test : biais +37 % sur les coupes (ancien : erreur moyenne 51 %, biais +2 % par compensation de −62 % à +137 %) ; les coupes « après 3 et 4 modèles » restent à +70 % parce que leur horizon est dominé par deux paires rapides (ling3-tiny think_off, début de minicpm5), imprévisibles avant d'être observées. Fin au 28/10 (+76 %) crédible comme valeur centrale : les 4 paires mesurées terminées ont pris 0,8 à 2,5 fois leur prévu (1,8 pondéré) ; fourchette du 27/10 au 01/11.
