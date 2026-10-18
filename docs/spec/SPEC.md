---
id: SPEC-benchmark-qualite-difficile
companions:
  - ../architecture/ARCHITECTURE-SPINE.md
  - modeles.md
  - pistes-et-questions.md
  - campagne-et-reprise.md
  - juge-et-calibration.md
  - statistiques.md
  - ../../AGENTS.md
sources:
  - wavelocalai:_bmad-output/planning-artifacts/research/technical-benchmark-qualite-slm-2026-10-10/research.md (non repris dans ce dépôt)
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Benchmark de qualité difficile pour les SLM locaux

## Why

C'est une douleur à résoudre. Le banc qualité actuel compte environ 30 items (14 de raisonnement, 8 de consignes, 4 d'outils). Il sature et ne départage plus les meilleurs modèles : un écart de 10 points n'y est détecté que dans 8 à 10 % des cas. Le catalogue de wavelocalai doit pourtant dire, usage par usage, quel petit modèle local choisir parmi 20. Les jeux publics connus sont saturés, contaminés ou biaisés pour des SLM, et aucun framework existant ne parle l'API native d'Ollama ni ne fait de comparaison appariée. D'où un banc maison, plus dur, en grande partie en français et protégé contre la contamination.

**Amendement du 2026-10-18 (décision d'Anaël) :** le banc devient un projet séparé de wavelocalai. wavelocalai ne produit plus aucun résultat de banc : l'admission des nouveaux modèles, la vitesse et la mémoire par machine se mesurent ici (CAP-9), et les résultats sont publiés dans un fichier versionné que wavelocalai récupère (CAP-10). Les objectifs d'utilisation comptent autant que la qualité : un modèle retenu doit rester utilisable en parallèle de tâches bureautiques sur la machine de référence.

## Capabilities

- **CAP-1** — Jeu de questions difficile et non contaminé
  - **intent:** Chaque usage dispose de questions discriminantes, reproductibles depuis une graine, sous licence compatible ou privées.
  - **success:**
    - régénérer avec la même graine redonne les mêmes empreintes ;
    - chaque question porte `usage`, `group`, `source` et `license` ;
    - ~800 questions en piste coupée et 400 en piste activée (composition dans `pistes-et-questions.md`) ;
    - aucune question privée dans le dépôt, seulement son empreinte.
- **CAP-2** — Génération sur les deux pistes
  - **intent:** Chaque modèle répond en raisonnement coupé, et ceux qui en sont capables aussi en raisonnement activé, dans des conditions fixées et consignées.
  - **success:**
    - chaque ligne de `generation.jsonl` porte les champs de `campagne-et-reprise.md` (sortie brute, tokens, durées, `think`, `seed`, `num_ctx`, version d'Ollama…), sans score ;
    - un modèle sans capacité thinking n'est pas lancé en piste activée ;
    - une troncature au plafond de tokens est enregistrée (`status = truncated`), puis comptée comme échec, à part.
- **CAP-3** — Campagne reprenable sans perte
  - **intent:** L'opérateur arrête, plante ou redémarre la campagne et la reprend en ne perdant au plus que la question en cours.
  - **success:**
    - un arrêt brutal du processus puis une reprise donnent un JSONL sans doublon de clé ni trou ;
    - Ctrl+C ou le fichier `STOP` termine la question en cours, puis sort ;
    - un manifeste différent bloque la reprise : jeu de questions, configuration, digest d'un modèle, version d'Ollama, machine ou empreinte du harnais ;
    - une panne d'Ollama déclenche un nouvel essai de la question une fois le service revenu ;
    - la machine ne se met pas en veille pendant la campagne.
- **CAP-4** — Correction déterministe
  - **intent:** Toute question hors rédaction est notée sans juge, et sa note se recalcule hors ligne depuis `generation.jsonl`.
  - **success:**
    - chaque correcteur passe des tests sur des cas à verdict connu ;
    - seule la phase de correction écrit les scores, dans `grading.jsonl`, rédaction comprise (depuis les verdicts du juge retenu) ;
    - recorriger le même `generation.jsonl` redonne un `grading.jsonl` identique, sans régénérer.
- **CAP-5** — Jugement découplé de la rédaction en français
  - **intent:** Les réponses de rédaction sont notées par le juge retenu, critère par critère en questions fermées, dans une phase séparée et reprenable.
  - **success:**
    - le jugement relit `generation.jsonl` et écrit son propre `judgment.jsonl` en ajout seul, avec la clé de génération plus le critère ;
    - il reprend après un arrêt sans re-juger ce qui est fait.
- **CAP-6** — Juge calibré
  - **intent:** Le juge de campagne est choisi sur son accord avec des étiquettes humaines, et son biais envers Qwen est mesuré.
  - **success:**
    - sur ~100 étiquettes produites par Anaël, un rapport donne l'accord et le coût de chacune des 5 configurations de `juge-et-calibration.md` (Winnow seul, MiMo, Haiku, Opus, et la cascade Winnow vers Haiku ou vers Opus) ;
    - il donne l'écart d'accord entre candidats Qwen et non-Qwen ;
    - le choix du juge est consigné avant la campagne.
- **CAP-7** — Classement statistiquement fondé
  - **intent:** Le rapport dit quels modèles se distinguent vraiment, par piste et par usage, et si le classement concorde avec une référence externe.
  - **success:** à partir de `grading.jsonl` et de `generation.jsonl` seulement, le rapport produit :
    - le score par question ;
    - un intervalle de Wilson par modèle ;
    - des comparaisons appariées corrigées pour les tests multiples ;
    - des groupes de modèles indiscernables ;
    - le taux de troncature ;
    - la corrélation de Spearman avec l'indice Artificial Analysis selon le critère de `statistiques.md`.
- **CAP-8** — Pilote de validation
  - **intent:** Avant la campagne complète, un pilote sur 4 modèles vérifie que le banc discrimine et tient le budget.
  - **success:** le rapport de pilote donne :
    - la part de questions discordantes entre modèles ;
    - les usages au plafond ou au plancher ;
    - le taux de réponses changeantes sur un sous-ensemble rejoué ;
    - la distribution des tokens de réflexion et le taux de troncature ;
    - une projection de durée de la campagne complète ;
    - un contrôle de cohérence de l'ordre des modèles avec l'ancien banc et l'indice AA.
- **CAP-9** — Admission, vitesse et mémoire par machine (amendement du 2026-10-18)
  - **intent:** Chaque modèle est mesuré sur la machine de référence en débit, en mémoire et, si la carte le permet, en puissance GPU. Un nouveau candidat passe une campagne d'admission courte avant d'entrer dans la campagne complète.
  - **success:**
    - débit de décodage par ligne de génération ; débit de préremplissage, durée de chargement, `size` et `size_vram` par chauffe ;
    - mémoire de la machine par modèle dans `memory.jsonl` (`qb.memory/1`, AD-14) : RAM et VRAM au repos et de pointe, pointes par palier, sans jamais faire échouer la génération ;
    - contexte validé : plus grand palier `num_ctx` chargé sans contexte dépassé ;
    - puissance GPU relevée au mieux (valeur nulle si la carte ne la publie pas) ; énergie publiée seulement si la mesure est validée à l'admission ;
    - la campagne d'admission (`admission-<date>`) donne ces mesures et un aperçu de qualité ; l'admission ou l'écart de chaque candidat est consigné avant la campagne complète.
- **CAP-10** — Publication des résultats (amendement du 2026-10-18)
  - **intent:** Les résultats par modèle, machine et piste sont publiés en release GitHub dans un fichier versionné au schéma documenté, que wavelocalai récupère sans dépendre du code du banc.
  - **success:**
    - `export-release` écrit `slm-quality-results.json` au schéma `qb.results/1` (AD-18), validé par `docs/schemas/qb.results-1.schema.json` ;
    - le fichier est joint à chaque release SemVer, sous ce nom (URL stable `releases/latest/download/slm-quality-results.json`) et sous `slm-quality-results-vX.Y.Z.json` ;
    - il se recalcule à l'identique depuis les fichiers de la campagne, sans réseau ni Ollama ;
    - rien de privé : ni texte de question, ni sortie de modèle, ni empreinte d'un fichier privé (AD-6).

## Constraints

- **Projet séparé (amendement du 2026-10-18) :** aucune dépendance au code de wavelocalai ; ce dépôt ne le modifie jamais et ne le consulte qu'en lecture. L'ancien banc et le catalogue de wavelocalai ne servent qu'au pilote, en copies définitives sous `$QUALITY_BENCH_DATA/wavelocalai/`. Les métadonnées des modèles vivent dans le registre versionné `slm_quality_bench/models.yaml` (AD-18). wavelocalai ne lit que l'asset de release.
- **Langue :** identifiants en anglais (paquet, champs JSON, valeurs fermées, sous-commandes). Docs, journaux et rapports en français.
- **Ollama :**
  - API native `/api/chat` seulement, jamais `/v1` ;
  - une seule version pour toute la campagne, épinglée par `ollama_version` dans le YAML de campagne (0.40.5 au 2026-10-18) : une autre version au manifeste interdit la reprise ;
  - hygiène de requête détaillée dans `campagne-et-reprise.md`.
- **Hors ligne :** aucun téléchargement ni appel réseau pendant la génération. Le juge, cloud ou local, n'intervient que dans la phase de jugement, découplée. Le juge local est défini par le contrat `POST /v1/systemone` sur `localhost`, pas par un serveur précis, et ne tourne jamais en même temps que la génération.
- **Correction :** déterministe pour tous les usages sauf la rédaction en français. Le score ne vit que dans `grading.jsonl` ; `generation.jsonl` reste brut (AD-3).
- **Machine :** tour-rtx3050 seule pour les campagnes (RTX 3050 8 Go, 31 Go de RAM). Contexte long plafonné entre 8K et 32K selon la mémoire. Windows se met en veille après 5 h. Le schéma `qb.results/1` prévoit plusieurs machines.
- **Budget :** campagne complète en 216 h au plus (6 jours plus 50 %, décision du 2026-10-18 après le pilote : jeu `set-v3`, piste activée sur les 800 questions, plafonds de 4 096 tokens sauf RAG à 2 048, K = 1). Ordre de réduction prévu à l'origine, si une projection dépasse le budget :
  1. abaisser les plafonds de tokens ;
  2. vérifier que la piste activée reste réservée aux modèles qui déclarent la capacité thinking dans `/api/show` ;
  3. ramener le N de la piste activée vers ~330.
- **Puissance acceptée :** un écart de 10 points est détectable sur le score global de chaque piste, de 20 points par usage. Avec `set-v3` et le ψ mesuré au pilote, l'écart détectable attendu est d'environ 6 points en global et 13 à 16 points par usage.
- **Dépôt public :** aucune question privée, aucune réponse brute à une question privée et aucune clé d'API dans un commit ou une PR. Aucune question privée n'est envoyée à un juge cloud. Exclusions de licence dans `pistes-et-questions.md`.
- **Python :**
  - 3.10+ ;
  - versions de dépendances vérifiées sur PyPI ou par une installation réelle ;
  - `disable_telemetry()` avant tout import de Hugging Face, Chroma, CrewAI, Ragas ou `langchain_community` ;
  - toutes les dépendances installées et les données NLTK téléchargées avant la campagne ; M-IFEval réduit aux vérificateurs FR, sans spaCy.

## Non-goals

- Élimination adaptative des modèles en cours de campagne (O'Brien-Fleming, Hoeffding races).
- Campagne sur d'autres machines que tour-rtx3050, pour l'instant (le format publié les prévoit).
- Précision au-delà du plafond de tokens : le banc ne mesure pas ce que ferait un modèle avec 32K tokens de réflexion.
- Alimenter ou modifier le banc de vitesse de wavelocalai (abandonné le 2026-10-18).
- Énergie par question, et énergie de la machine entière (processeur, RAM) : seule la puissance GPU est relevée, par modèle, sans wattmètre.
- Affichage des résultats : rôle de wavelocalai.
- Plusieurs tirages par question (K > 1), sauf si le pilote les impose (voir `statistiques.md`).

## Success signal

- Les 20 modèles sont passés en 5 à 6 jours sur la tour, malgré au moins un arrêt et une reprise : les 20 en piste coupée, et ceux capables de raisonnement en piste activée.
- Le rapport final classe les modèles en groupes indiscernables par piste et par usage, avec des intervalles. Il rapporte la corrélation de Spearman avec l'indice AA selon le critère de `statistiques.md`.

## Assumptions

- Répartition indicative des ~800 questions de la piste coupée : raisonnement 130, consignes 130, outils 130, extraction 110, RAG 110, abstention 110, rédaction 80. Elle sera réajustée après le pilote. La piste activée en prend la moitié par strates.
- Le N de puissance se compte en groupes indépendants (passage, gabarit, conversation multi-tours), pas en questions.
- L'estimation de budget repose sur les débits de l'ancien banc, un prompt RAG de 16K en moyenne et des réponses de 350 tokens. Le pilote la remplace par des mesures.
- Pas de mesure d'énergie par question. La RTX 3050 rend `power.draw` N/A (vérifié le 2026-10-18, pilote NVIDIA 610.62) ; `nvidia-smi -q -d POWER` publie une moyenne glissante (« Power Samples ») restée constante à 46,3 W au repos, donc douteuse : la puissance GPU est relevée au mieux et validée sous charge à la campagne d'admission avant toute publication d'énergie.
- Les JSONL bruts restent hors du dépôt, comme `data/`. Sont versionnés : les scores par question indexés par empreinte, les agrégats et le manifeste (liste blanche AD-6).
- La tenue en français de Winnow-E4B et son serveur sur la tour (Windows, 8 Go de VRAM) sont à vérifier au début de la story 7, avec Perplexity Decider hébergé en repli.

## Open Questions

- Quel seuil d'accord entre juge et humain pour retenir un juge, et quel biais Qwen maximal tolérer ? À fixer par Anaël au plus tard à la calibration (story 9).
- La moyenne « Power Samples » de `nvidia-smi` suit-elle la charge réelle de la RTX 3050 ? À vérifier sur la campagne d'admission (CAP-9).
- Quel serveur pour le juge local : WSL2 avec `winnow-inference`, Winnow-E4B importé dans Ollama comme modèle `decision`, ou Perplexity Decider hébergé ? À trancher au début de la story 7, par mesure sur la tour.

## Revue

Revue d'avant publication du dépôt (2026-10-17, une passe, second avis compris). Historique réécrit par `git filter-repo --replace-text` (fichiers et messages de commit) avant les correctifs.

- medium | second avis 1 | corrigé | chemins locaux `C:\Users\<nom>\…` et nom d'un autre projet dans l'historique (`tests/gpu_fakes.py`, guide de lancement) : remplacés partout par `C:\Users\user\…`, `autre-projet` et `<dossier-de-données>` ; `git log -p --all` n'en contient plus.
- medium | second avis 2 | rejeté | e-mail des commits : gardé (décision d'Anaël).
- medium | second avis 3 | corrigé | journaux internes gardés mais nettoyés, historique compris : crédit d'API mensuel retiré (juge-et-calibration.md, .memlog, message du commit Opus ; coûts estimés par campagne gardés), budget cloud du run neutralisé (PROMPT-ORCHESTRATION-7-9.md), juge propriétaire tiers nommé « un juge propriétaire écarté », chemins locaux retirés ; étiquette `tour-rtx3050` gardée.
- medium | second avis 4 | corrigé | version d'Ollama en dur : clé `ollama_version` du YAML de campagne (hors `generation_hash`), contrôlée par `precheck` (avec `--ollama-version` en remplacement, chaîne vide : aucun contrôle ; rejeu à la même version exigé) et par `generate` (code 2) ; `pilot-20261017*.yaml` à `0.40.6` ; `server_version` du juge local lu sur `/api/version` au lancement, comparé à `judges.yaml` s'il y est renseigné (`null` par défaut) et figé dans `blocking.judge.server_version` du manifeste (bloquant à la reprise). Un juge local sans Ollama joignable est désormais refusé (avant : lancement permis).
- medium | second avis 5 | corrigé | `max_tokens` 2048 avec réflexion adaptative : 8192 pour `haiku`, `opus` et leurs rejeux (même risque chez Haiku) ; `--max-cost-usd` inchangé.
- medium | revue | corrigé | conséquence du point 5 : l'estimation d'un lot compte chaque sortie au plafond ; un lot Opus de 1 000 (≈ 82 $ estimés) aurait dépassé tout plafond raisonnable avant le premier envoi (déjà ≈ 26 $ à 2048). `batch_size` d'Opus à 100 (≈ 8,5 $ estimés par lot), guide de lancement : `--max-cost-usd 25` pour le pilote.
- low | second avis 6 | corrigé | Python 3.14 exigé (syntaxe `except A, B:`) : prérequis explicite dans le README.
- low | second avis 7 | corrigé | installation non éditable : `generate`, `judge` et `grade` refusent (code 2) sans `QUALITY_BENCH_DATA` si aucun `pyproject.toml` ne se trouve au-dessus du paquet ; README et guide recommandent la variable.
- low | second avis 8 | corrigé | CI : `permissions: contents: read`, ruff 0.17.1, black 26.10.1 et isort 9.0.2 épinglés sur l'extra `dev` ; tags `actions/checkout@v7`, `actions/setup-python@v7`, `actions/cache@v6` vérifiés (`git ls-remote`).
- low | second avis 9 | corrigé | NOTICE : « The Google Research Authors » pour les fichiers d'IFBench et de M-IFEval FR qui le portent.
- low | second avis 10 | corrigé | valeurs Artificial Analysis : source et attribution (relevé manuel du 2026-10-17) dans le README et la NOTICE.
- low | second avis 11 | rejeté | identifiants de questions privées dans l'index : voulu (AD-6).
- low | second avis 12 | corrigé | `.venv-quality` et chemin à nom d'utilisateur dans `requirements.txt`, `deferred-work.md` et le guide de lancement ; les stories, le spine et les journaux historiques gardent les anciens noms (`.venv-quality`, `src.core.telemetry`, Python ≥ 3.10 dans le spine).
- reporté | revue | à vérifier sur la tour, sans agent : `/api/version` d'Ollama 0.40.6 rend exactement `0.40.6` (comparé à `ollama_version`) ; un premier lot réel Haiku et Opus à `max_tokens` 8192 ne rend aucun `stop_reason: max_tokens` ; le manifeste du juge Winnow porte `server_version: ollama-0.40.6`.
