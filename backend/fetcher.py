"""Récupération et parsing des flux RSS."""

from __future__ import annotations

import calendar
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sources import Feed

log = logging.getLogger(__name__)

# Certains sites (Toute l'Europe notamment) refusent les user-agents de bots.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT_SECONDS = 20
MAX_DESCRIPTION_CHARS = 600


@dataclass
class Article:
    title: str
    description: str
    link: str
    source: str
    category: str
    lang: str
    generic: bool
    published: Optional[datetime]


def _session() -> requests.Session:
    retry = Retry(
        total=2,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        }
    )
    return session


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
# Caractères invisibles (espaces de largeur nulle) que certains flux glissent dans le texte.
_INVISIBLE_RE = re.compile("[​-‍⁠﻿]")


def clean_text(raw: str, limit: int = MAX_DESCRIPTION_CHARS) -> str:
    text = html.unescape(_TAG_RE.sub(" ", raw or ""))
    text = _INVISIBLE_RE.sub("", text)
    text = _SPACE_RE.sub(" ", text).strip()
    if len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut.rstrip(",;:") + "…"
    return text


def _entry_date(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def _parse_entries(feed: Feed, category: str, parsed) -> List[Article]:
    articles = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title", ""), limit=300)
        if not title:
            continue
        description = clean_text(entry.get("summary", "") or entry.get("description", ""))
        # Certains flux (Mediapart…) répètent le titre en guise de description.
        if description == title:
            description = ""
        articles.append(
            Article(
                title=title,
                description=description,
                link=entry.get("link", ""),
                source=feed.name,
                category=category,
                lang=feed.lang,
                generic=feed.generic,
                published=_entry_date(entry),
            )
        )
    return articles


def fetch_feed(
    feed: Feed, category: str, session: requests.Session
) -> Tuple[List[Article], Optional[str]]:
    """Essaie chaque URL du flux dans l'ordre. Renvoie (articles, erreur)."""
    errors = []
    for url in feed.urls:
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            articles = _parse_entries(feed, category, parsed)
            if articles:
                return articles, None
            errors.append(f"{url}: flux vide")
        except requests.RequestException as exc:
            errors.append(f"{url}: {exc.__class__.__name__} {exc}")
    return [], "; ".join(errors)


def fetch_all(feeds: Dict[str, List[Feed]]) -> Tuple[List[Article], List[str]]:
    """Récupère tous les flux en parallèle. Renvoie (articles, flux en échec)."""
    session = _session()
    jobs = [(feed, category) for category, items in feeds.items() for feed in items]
    articles: List[Article] = []
    failures: List[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = pool.map(lambda job: fetch_feed(job[0], job[1], session), jobs)
        for (feed, category), (items, error) in zip(jobs, results):
            if error:
                log.warning("Flux en échec — %s (%s) : %s", feed.name, category, error)
                failures.append(f"{feed.name} ({category})")
            else:
                log.info("%-22s %-7s %3d articles", feed.name, category, len(items))
            articles.extend(items)
    return articles, failures
