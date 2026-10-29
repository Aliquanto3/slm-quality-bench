"""Prompts tronqués en silence par Ollama (constat du 2026-10-28, AD-7) : reclassement à la
notation.

Ollama 0.40.5 coupe en silence le prompt de moitié pour certains modèles quand le prompt et le
plafond de réponse dépassent ``num_ctx`` : la ligne reste ``ok`` ou ``truncated`` et
``tokens.prompt`` vaut ``num_ctx / 2`` + 2 ou 3. Le contrôle ``prompt >= num_ctx - num_predict``
du générateur ne la voit pas. ``grade`` la reclasse en ``context_exceeded``, cause ``bench``
(unité nulle, hors comparaisons, comme tout dépassement du banc, AD-10), si :

- signature : ligne ``ok`` ou ``truncated`` en un seul appel, dont ``tokens.prompt`` est dans
  ``[num_ctx // 2, num_ctx // 2 + 8]`` ;
- prompt réel connu trop long : le prompt réel de la même question, majoré de 10 % pour l'écart
  entre tokenizers, dépasse ``num_ctx - num_predict``. Prompt réel = le plus grand prompt mesuré
  (``prompt + prompt_cached``, AD-7) sur les lignes en un seul appel de cette question dans la
  campagne (tous modèles, refus d'Ollama compris), borné en bas par ``est_prompt_tokens`` de la
  question (AD-5). La majoration vient de ``full-20261018`` : pour une question CWE au palier
  16 384, le plus grand prompt mesuré (tokenizer d'un modèle qui n'a pas tronqué) reste sous
  14 336 alors que des modèles dont le tokenizer compte davantage ont tronqué. Les prompts
  d'abstention OneRuler (moins de 10 000 au palier 16 384) restent loin du seuil majoré.

Seule la campagne notée est lue (``grade`` reste une fonction de ses entrées). Dans une campagne
à un seul modèle qui tronque en silence, le prompt réel n'est pas mesuré : la borne
``est_prompt_tokens`` sous-estime les prompts OneRuler d'environ 27 % et ne suffit pas, la ligne
n'est pas reclassée mais comptée comme suspecte dans le journal (``suspects``). Les lignes
multi-appels sont exclues des deux côtés : leurs prompts sont des sommes sur plusieurs appels.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, NamedTuple

SILENT_PROMPT_TRUNCATION = "silent_prompt_truncation"
# Écart toléré au-dessus de num_ctx / 2 (observé : + 2 ou + 3, gabarit de conversation).
SIGNATURE_SLACK = 8
# Écart toléré entre tokenizers sur le prompt réel (10 %, en entiers : réel × 11 > seuil × 10).
TOKENIZER_MARGIN_NUM, TOKENIZER_MARGIN_DEN = 11, 10
_SIGNATURE_STATUSES = ("ok", "truncated")


class Reclassification(NamedTuple):
    """Lignes de génération corrigées par clé et comptes pour le journal."""

    generations: dict[str, dict[str, Any]]
    reclassified: frozenset[str]
    suspects: int  # signature présente, prompt réel inconnu ou assez court : non reclassées


def measured_prompt(line: Mapping[str, Any]) -> int:
    """Prompt mesuré par Ollama (AD-7) : ``prompt + prompt_cached``."""
    return line["tokens"]["prompt"] + line["tokens"]["prompt_cached"]


def has_signature(line: Mapping[str, Any]) -> bool:
    """Ligne ``ok`` ou ``truncated`` en un appel, ``tokens.prompt`` à la moitié de ``num_ctx``."""
    if line["status"] not in _SIGNATURE_STATUSES or line["calls"] != 1:
        return False
    half = line["num_ctx"] // 2
    return half <= line["tokens"]["prompt"] <= half + SIGNATURE_SLACK


def real_prompts(
    lines: Iterable[Mapping[str, Any]], questions: Mapping[str, Mapping[str, Any]]
) -> dict[str, int]:
    """Prompt réel par question : le plus grand mesuré en un appel, borné par l'estimation."""
    real = {qid: question["est_prompt_tokens"] for qid, question in questions.items()}
    for line in lines:
        if line["calls"] == 1:
            qid = line["question_id"]
            real[qid] = max(real.get(qid, 0), measured_prompt(line))
    return real


def is_silently_truncated(line: Mapping[str, Any], real_prompt: int | None) -> bool:
    """Signature présente et prompt réel, majoré de 10 %, au-delà de ``num_ctx - num_predict``."""
    if not has_signature(line) or real_prompt is None:
        return False
    limit = line["num_ctx"] - line["num_predict"]
    return real_prompt * TOKENIZER_MARGIN_NUM > limit * TOKENIZER_MARGIN_DEN


def reclassify(
    generations: Mapping[str, Mapping[str, Any]], questions: Mapping[str, Mapping[str, Any]]
) -> Reclassification:
    """Reclasse en ``context_exceeded`` (cause ``bench``) les prompts tronqués en silence ; les
    autres lignes sont rendues telles quelles (les lignes d'entrée ne sont jamais modifiées)."""
    real = real_prompts(generations.values(), questions)
    out: dict[str, dict[str, Any]] = {}
    reclassified: set[str] = set()
    suspects = 0
    for key, line in generations.items():
        if is_silently_truncated(line, real.get(line["question_id"])):
            out[key] = {**line, "status": "context_exceeded", "context_limit": "bench"}
            reclassified.add(key)
        else:
            suspects += has_signature(line)
            out[key] = dict(line)
    return Reclassification(out, frozenset(reclassified), suspects)
