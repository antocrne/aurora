"""Résumé des sujets d'une catégorie via l'API Mistral.

On appelle directement l'API REST (chat/completions) plutôt que le SDK
`mistralai`, dont l'interface change souvent d'une version majeure à l'autre.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from typing import Dict, List, Sequence

import requests

from classifier import Story

log = logging.getLogger(__name__)

API_URL = "https://api.mistral.ai/v1/chat/completions"
# Sur l'offre Free, Mistral Small/Medium ont un quota nul et Large est interdit ;
# les Ministral et Nemo restent accessibles. On essaie ces modèles dans l'ordre.
DEFAULT_MODELS = ["ministral-14b-latest", "ministral-8b-latest", "open-mistral-nemo"]
MAX_TOPICS = 6
MAX_SOURCES = 5
MAX_PROMPT_CHARS = 24_000
MAX_ATTEMPTS = 6  # jusqu'à ~4 min d'attente cumulée en cas de 429

PROMPT_TEMPLATE = """Tu es un rédacteur en chef d'un journal de qualité. Tu rédiges un briefing quotidien factuel et concis.

Nous sommes le {today}.

Voici les articles récents pour la catégorie "{category}" :

---
{articles}
---

À partir de ces articles :

1. Identifie les 3 à 6 sujets principaux (regroupe les articles qui parlent du même événement)
2. Pour chaque sujet, rédige :
   - Un titre court et informatif (style manchette de journal, max 10 mots)
   - Un résumé factuel de 3 à 5 phrases qui couvre l'essentiel : quoi, qui, où, quand, pourquoi
   - La liste des sources utilisées

Règles :
- Langue : français
- Ton : neutre, factuel, sans opinion ni éditorialisation
- Pas de formules comme "selon nos sources" ou "il semblerait que"
- Va droit au fait
- Si un sujet est couvert par plusieurs sources avec des infos contradictoires, mentionne-le
- Ne dépasse pas 6 sujets par catégorie
- Ignore les articles qui ne relèvent pas de la catégorie "{category}"
- Privilégie les sujets couverts par plusieurs sources
- Pour les sources, reprends exactement les noms indiqués dans les lignes "Sources :", un nom par élément de la liste
- N'invente aucune date, aucun chiffre ni aucun nom absent des articles
- Texte brut uniquement : pas de Markdown (ni gras, ni italique, ni astérisques)
{covered}
Réponds au format JSON suivant :
{{
  "topics": [
    {{
      "headline": "...",
      "summary": "...",
      "sources": ["source1", "source2"]
    }}
  ]
}}"""


class SummarizerError(RuntimeError):
    pass


class ModelUnavailable(SummarizerError):
    """Modèle refusé par l'offre Mistral (quota nul ou modèle non inclus)."""


# Modèles refusés lors de cette exécution, pour ne pas les réessayer à chaque catégorie.
_unavailable_models: set = set()


def format_stories(stories: List[Story], limit: int = MAX_PROMPT_CHARS) -> str:
    """Un bloc par sujet dédoublonné, séparés par ---, dans la limite de `limit` caractères."""
    blocks: List[str] = []
    total = 0
    for story in stories:
        lead = story.lead
        lines = [f"Sources : {', '.join(story.sources)}", f"Titre : {lead.title}"]
        other_titles = [a.title for a in story.articles if a.title != lead.title]
        for title in other_titles[:3]:
            lines.append(f"Autre titre : {title}")
        if lead.description:
            lines.append(f"Contenu : {lead.description}")
        block = "\n".join(lines)
        if total + len(block) > limit and blocks:
            break
        blocks.append(block)
        total += len(block) + 5
    return "\n---\n".join(blocks)


def build_prompt(
    label: str, stories: List[Story], today: str = "", covered: Sequence[str] = ()
) -> str:
    covered_rule = ""
    if covered:
        headlines = "; ".join(covered)
        covered_rule = (
            "- Ces sujets sont déjà traités dans d'autres rubriques, ne les reprends pas : "
            f"{headlines}\n"
        )
    return PROMPT_TEMPLATE.format(
        today=today,
        category=label,
        articles=format_stories(stories),
        covered=covered_rule,
    )


def _call_mistral(prompt: str, api_key: str, model: str) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        wait = 15 * (attempt + 1)
        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=180)
        except requests.RequestException as exc:
            last_error = str(exc)
        else:
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
            if response.status_code == 403 and "tier_not_allowed" in response.text:
                raise ModelUnavailable(f"{model} n'est pas inclus dans l'offre Mistral")
            if response.status_code not in (429, 500, 502, 503, 504):
                break
            if response.status_code == 429:
                # On respecte Retry-After et on journalise les quotas annoncés.
                limits = {k: v for k, v in response.headers.items() if "ratelimit" in k.lower()}
                if limits:
                    log.warning("Mistral : quotas %s", limits)
                if response.headers.get("x-ratelimit-limit-req-minute") == "0":
                    raise ModelUnavailable(f"{model} a un quota de 0 requête/minute sur cette offre")
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = max(wait, int(retry_after))
        if attempt == MAX_ATTEMPTS - 1:
            break
        log.warning("Mistral : %s — nouvel essai dans %ss", last_error, wait)
        time.sleep(wait)
    raise SummarizerError(f"Échec de l'appel Mistral : {last_error}")


def _canonical_sources(raw: object, known: List[str]) -> List[str]:
    if not isinstance(raw, list):
        return []
    by_key = {_source_key(k): k for k in known}
    result: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        # Le modèle recopie parfois une ligne « Sources : A, B, C » en un seul élément.
        for part in re.split(r"[,;]", item):
            name = by_key.get(_source_key(part), part.strip())
            if name and _source_key(name) not in {_source_key(r) for r in result}:
                result.append(name)
    return result[:MAX_SOURCES]


def _source_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip().casefold()


_MARKDOWN_RE = re.compile(r"(\*\*|__|\*|`)")


def clean_markdown(text: str) -> str:
    """L'app affiche du texte brut : on retire gras, italique et code Markdown."""
    return re.sub(r"\s+", " ", _MARKDOWN_RE.sub("", text)).strip()


def parse_topics(content: str, known_sources: List[str]) -> List[Dict[str, object]]:
    # Mistral renvoie parfois le JSON entouré d'un bloc ```json.
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise SummarizerError(f"Réponse JSON invalide : {exc}") from exc

    topics = []
    for item in data.get("topics", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        headline = clean_markdown(str(item.get("headline", ""))).rstrip(".")
        summary = clean_markdown(str(item.get("summary", "")))
        if not headline or not summary:
            continue
        topics.append(
            {
                "headline": headline,
                "summary": summary,
                "sources": _canonical_sources(item.get("sources"), known_sources),
            }
        )
    if not topics:
        raise SummarizerError("Aucun sujet exploitable dans la réponse")
    return topics[:MAX_TOPICS]


def summarize(
    label: str,
    stories: List[Story],
    model: str = "",
    today: str = "",
    covered: Sequence[str] = (),
) -> List[Dict[str, object]]:
    """`covered` : manchettes déjà rédigées pour d'autres rubriques, à ne pas reprendre."""
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise SummarizerError("MISTRAL_API_KEY n'est pas défini")
    preferred = model or os.environ.get("MISTRAL_MODEL") or ""
    candidates = [m for m in dict.fromkeys([preferred, *DEFAULT_MODELS]) if m]
    known = sorted({src for story in stories for src in story.sources})
    prompt = build_prompt(label, stories, today, covered)
    for candidate in candidates:
        if candidate in _unavailable_models:
            continue
        log.info("%s : %d sujets envoyés à %s (%d caractères)", label, len(stories), candidate, len(prompt))
        try:
            return _summarize_with(candidate, prompt, api_key, known, label)
        except ModelUnavailable as exc:
            log.warning("%s — modèle suivant", exc)
            _unavailable_models.add(candidate)
    raise SummarizerError(f"Aucun modèle Mistral accessible parmi {', '.join(candidates)}")


def _summarize_with(
    model: str, prompt: str, api_key: str, known: List[str], label: str
) -> List[Dict[str, object]]:
    for attempt in range(2):
        content = _call_mistral(prompt, api_key, model)
        try:
            return parse_topics(content, known)
        except SummarizerError as exc:
            if attempt == 1:
                raise
            log.warning("%s : %s — nouvel essai", label, exc)
    raise AssertionError("unreachable")


def summarize_offline(stories: List[Story]) -> List[Dict[str, object]]:
    """Mode --dry-run : résumé extractif sans appel API, pour tester la chaîne."""
    topics = []
    for story in stories:
        lead = story.lead
        if lead.lang != "fr" or not lead.description:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", lead.description)
        topics.append(
            {
                "headline": lead.title,
                "summary": " ".join(sentences[:4]),
                "sources": story.sources,
            }
        )
        if len(topics) == 5:
            break
    return topics
