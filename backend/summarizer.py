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
from fetcher import Article
from sources import all_source_names

log = logging.getLogger(__name__)

API_URL = "https://api.mistral.ai/v1/chat/completions"
# Sur l'offre Free, Mistral Small/Medium ont un quota nul et Large est interdit ;
# les Ministral et Nemo restent accessibles. On essaie ces modèles dans l'ordre.
DEFAULT_MODELS = ["ministral-14b-latest", "ministral-8b-latest", "open-mistral-nemo"]
MAX_TOPICS = 6
MAX_SOURCES = 5
MAX_PROMPT_CHARS = 30_000
MAX_EXCERPT_CHARS = 300  # longueur max d'un chapô par média dans le prompt
MAX_ATTEMPTS = 6  # jusqu'à ~4 min d'attente cumulée en cas de 429

PROMPT_TEMPLATE = """Tu es un rédacteur en chef d'un journal de qualité. Tu rédiges un briefing quotidien factuel et concis.

Nous sommes le {today}.

{definitions}
Voici les articles récents pour la catégorie "{category}". Chaque bloc [S…] regroupe les articles de plusieurs médias sur un même événement :

---
{articles}
---

À partir de ces articles :

1. Identifie les 3 à 6 sujets principaux (un sujet peut regrouper plusieurs blocs qui parlent du même événement)
2. Pour chaque sujet, rédige :
   - Un titre court et informatif (style manchette de journal, max 10 mots)
   - Un résumé factuel de 3 à 5 phrases qui couvre l'essentiel : quoi, qui, où, quand, pourquoi
   - La liste des numéros des blocs utilisés (ex. [3, 7] pour S3 et S7)
{angles_step}
Règles :
- Langue : français
- Ton : neutre, factuel, sans opinion ni éditorialisation
- Pas de formules comme "selon nos sources" ou "il semblerait que"
- Va droit au fait
- Si un sujet est couvert par plusieurs sources avec des infos contradictoires, mentionne-le
- Ne dépasse pas 6 sujets par catégorie
- Ignore les articles qui ne relèvent pas de la catégorie "{category}" selon les définitions ci-dessus
- Privilégie les sujets couverts par plusieurs sources
- N'invente aucune date, aucun chiffre ni aucun nom absent des articles
- Texte brut uniquement : pas de Markdown (ni gras, ni italique, ni astérisques)
{covered}
Réponds au format JSON suivant :
{{
  "topics": [
    {{
      "headline": "...",
      "summary": "...",
      "stories": [1, 2]{angles_field}
    }}
  ]
}}"""

CATEGORY_DEFINITIONS = """Définition des rubriques :
- Monde : événements hors d'Europe (Amériques, Asie, Afrique, Océanie, Moyen-Orient dont Israël, la Palestine, l'Iran et les pays du Golfe), et organisations internationales
- Europe : pays européens autres que la France (dont Royaume-Uni, Suisse, Ukraine, Russie, Balkans), Union européenne et ses institutions
- France : politique, société, économie, justice et faits divers en France, y compris la diplomatie française
"""

ANGLES_STEP = """3. Pour chaque sujet couvert par au moins deux médias, compare leur traitement à partir de leurs titres et chapôs : faits mis en avant, cadrage, ton. Rédige "angles" en une ou deux phrases qui nomment les médias (ex. « Libération met l'accent sur …, Le Figaro insiste sur … »). Si les traitements ne diffèrent pas vraiment, ou si un seul média couvre le sujet, mets "angles": null. N'attribue jamais à un média un point de vue absent de son texte.
"""


class SummarizerError(RuntimeError):
    pass


class ModelUnavailable(SummarizerError):
    """Modèle refusé par l'offre Mistral (quota nul ou modèle non inclus)."""


# Modèles refusés lors de cette exécution, pour ne pas les réessayer à chaque catégorie.
_unavailable_models: set = set()


def _one_per_source(story: Story) -> List[Article]:
    """Le premier article de chaque média, dans l'ordre du sujet."""
    seen: Dict[str, Article] = {}
    for article in story.articles:
        seen.setdefault(article.source, article)
    return list(seen.values())


def format_stories(stories: List[Story], limit: int = MAX_PROMPT_CHARS) -> str:
    """Un bloc numéroté [S1], [S2]… par sujet, avec le titre et le chapô de chaque média."""
    blocks: List[str] = []
    total = 0
    for number, story in enumerate(stories, start=1):
        lines = [f"[S{number}] Sources : {', '.join(story.sources)}"]
        for article in _one_per_source(story)[:MAX_SOURCES]:
            text = article.title
            if article.description:
                text += f" — {article.description[:MAX_EXCERPT_CHARS]}"
            lines.append(f"- {article.source} : {text}")
        block = "\n".join(lines)
        if total + len(block) > limit and blocks:
            break
        blocks.append(block)
        total += len(block) + 5
    return "\n---\n".join(blocks)


def build_prompt(
    label: str,
    stories: List[Story],
    today: str = "",
    covered: Sequence[str] = (),
    angles: bool = False,
) -> str:
    covered_rule = ""
    if covered:
        headlines = "; ".join(covered)
        covered_rule = (
            "- Ces sujets sont déjà traités dans d'autres rubriques, ne les reprends pas : "
            f"{headlines}\n"
        )
    return PROMPT_TEMPLATE.format(
        definitions=CATEGORY_DEFINITIONS,
        today=today,
        category=label,
        articles=format_stories(stories),
        covered=covered_rule,
        angles_step=ANGLES_STEP if angles else "",
        angles_field=',\n      "angles": "..." ou null' if angles else "",
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


def topic_links(story_ids: object, stories: List[Story]) -> List[Dict[str, str]]:
    """Un lien par média (au plus MAX_SOURCES), tiré des blocs [S…] cités par le modèle."""
    if not isinstance(story_ids, list):
        return []
    links: List[Dict[str, str]] = []
    for raw in story_ids:
        try:
            index = int(str(raw).lstrip("Ss")) - 1
        except ValueError:
            continue
        if not 0 <= index < len(stories):
            continue
        for article in _one_per_source(stories[index]):
            if not article.link.startswith(("https://", "http://")):
                continue
            if any(_source_key(l["source"]) == _source_key(article.source) for l in links):
                continue
            links.append({"source": article.source, "url": article.link})
    return links[:MAX_SOURCES]


def _source_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip().casefold()


_MARKDOWN_RE = re.compile(r"(\*\*|__|\*|`)")


def clean_markdown(text: str) -> str:
    """L'app affiche du texte brut : on retire gras, italique et code Markdown."""
    return re.sub(r"\s+", " ", _MARKDOWN_RE.sub("", text)).strip()


# Références internes aux blocs du prompt : « (S3, S4) », « ([8, 9]) », « [S2] », « S5 ».
_STORY_REF_RE = re.compile(
    r"\s*\((?:\s*\[?\s*S?\d+\s*\]?\s*,?)+\)"
    r"|\s*\[(?:\s*S?\d+\s*,?)+\]"
    r"|\s*\bS\d+\b"
)


def check_angles(raw: object, topic_sources: object) -> str:
    """Valide la « lecture croisée » : renvoie "" si elle est vide ou douteuse.

    Attribuer à un journal un point de vue qu'il n'a pas exprimé est l'erreur la
    plus grave possible ici : on rejette tout texte qui cite un média absent
    des sources du sujet, ou qui en cite moins de deux.
    """
    if not isinstance(raw, str) or not isinstance(topic_sources, list):
        return ""
    text = clean_markdown(_STORY_REF_RE.sub("", raw))
    if not text or text.lower() in ("null", "none"):
        return ""
    allowed = {_source_key(s) for s in topic_sources}
    lowered = _source_key(text)
    cited = {name for name in all_source_names() if _source_key(name) in lowered}
    if len(cited) < 2 or any(_source_key(name) not in allowed for name in cited):
        return ""
    return text


def parse_topics(
    content: str, stories: List[Story], angles: bool = False
) -> List[Dict[str, object]]:
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
        links = topic_links(item.get("stories"), stories)
        topic: Dict[str, object] = {
            "headline": headline,
            "summary": summary,
            "sources": [link["source"] for link in links],
            "links": links,
        }
        if angles:
            checked = check_angles(item.get("angles"), topic["sources"])
            if checked:
                topic["angles"] = checked
        topics.append(topic)
    if not topics:
        raise SummarizerError("Aucun sujet exploitable dans la réponse")
    return topics[:MAX_TOPICS]


def _complete(prompt: str, model: str = "") -> str:
    """Appelle le premier modèle accessible (préféré, puis DEFAULT_MODELS)."""
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise SummarizerError("MISTRAL_API_KEY n'est pas défini")
    preferred = model or os.environ.get("MISTRAL_MODEL") or ""
    for candidate in dict.fromkeys([preferred, *DEFAULT_MODELS]):
        if not candidate or candidate in _unavailable_models:
            continue
        try:
            return _call_mistral(prompt, api_key, candidate)
        except ModelUnavailable as exc:
            log.warning("%s — modèle suivant", exc)
            _unavailable_models.add(candidate)
    raise SummarizerError("Aucun modèle Mistral accessible")


CHECK_TEMPLATE = """Tu vérifies le classement des sujets d'un journal dans ses trois rubriques.

{definitions}
Voici les sujets, chacun avec un identifiant, sa rubrique actuelle, son titre et le début de son résumé :

{topics}

Pour chaque sujet, indique la rubrique correcte selon les définitions ci-dessus, en te fondant sur le lieu où se déroule l'événement.
Réponds au format JSON suivant, avec une entrée par sujet ("category" vaut "monde", "europe" ou "france") :
{{"placements": [{{"id": "E4", "category": "monde"}}]}}"""

_PREFIXES = {"monde": "M", "europe": "E", "france": "F"}


def check_placements(written: Dict[str, List[Dict[str, object]]], model: str = "") -> int:
    """Relit le classement de tous les sujets et déplace ceux qui sont mal rangés.

    Un sujet déplacé vers une rubrique déjà pleine est retiré ; une rubrique
    n'est jamais vidée. Renvoie le nombre de sujets déplacés ou retirés.
    """
    lines = []
    for category, topics in written.items():
        for index, topic in enumerate(topics, start=1):
            excerpt = str(topic["summary"])[:160]
            lines.append(f"{_PREFIXES[category]}{index} [{category}] {topic['headline']} — {excerpt}")
    content = _complete(CHECK_TEMPLATE.format(definitions=CATEGORY_DEFINITIONS, topics="\n".join(lines)), model)
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        placements = json.loads(content).get("placements", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise SummarizerError(f"Réponse de vérification invalide : {exc}") from exc

    targets = {
        str(p.get("id", "")).strip().upper(): str(p.get("category", "")).strip().lower()
        for p in placements
        if isinstance(p, dict)
    }
    moves = []
    for category, topics in written.items():
        for index, topic in enumerate(topics, start=1):
            target = targets.get(f"{_PREFIXES[category]}{index}")
            if target in written and target != category:
                moves.append((category, topic, target))

    changed = 0
    for source, topic, target in moves:
        if len(written[source]) <= 1:
            continue
        written[source].remove(topic)
        changed += 1
        if len(written[target]) < MAX_TOPICS:
            written[target].append(topic)
            log.info("Vérification : « %s » déplacé de %s vers %s", topic["headline"], source, target)
        else:
            log.info("Vérification : « %s » retiré de %s (rubrique %s pleine)", topic["headline"], source, target)
    return changed


def summarize(
    label: str,
    stories: List[Story],
    model: str = "",
    today: str = "",
    covered: Sequence[str] = (),
    angles: bool = False,
) -> List[Dict[str, object]]:
    """`covered` : manchettes déjà rédigées pour d'autres rubriques, à ne pas reprendre.
    `angles` : demander en plus une comparaison du traitement entre médias."""
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise SummarizerError("MISTRAL_API_KEY n'est pas défini")
    preferred = model or os.environ.get("MISTRAL_MODEL") or ""
    candidates = [m for m in dict.fromkeys([preferred, *DEFAULT_MODELS]) if m]
    prompt = build_prompt(label, stories, today, covered, angles)
    for candidate in candidates:
        if candidate in _unavailable_models:
            continue
        log.info("%s : %d sujets envoyés à %s (%d caractères)", label, len(stories), candidate, len(prompt))
        try:
            return _summarize_with(candidate, prompt, api_key, stories, angles, label)
        except ModelUnavailable as exc:
            log.warning("%s — modèle suivant", exc)
            _unavailable_models.add(candidate)
    raise SummarizerError(f"Aucun modèle Mistral accessible parmi {', '.join(candidates)}")


def _summarize_with(
    model: str, prompt: str, api_key: str, stories: List[Story], angles: bool, label: str
) -> List[Dict[str, object]]:
    for attempt in range(2):
        content = _call_mistral(prompt, api_key, model)
        try:
            return parse_topics(content, stories, angles)
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
        links = topic_links([1], [story])
        topics.append(
            {
                "headline": lead.title,
                "summary": " ".join(sentences[:4]),
                "sources": [link["source"] for link in links],
                "links": links,
            }
        )
        if len(topics) == 5:
            break
    return topics
