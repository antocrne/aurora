"""Tri des articles par catégorie et dédoublonnage des sujets.

Plusieurs sources couvrent souvent le même événement : on regroupe les articles
dont les titres se ressemblent en « sujets » (clusters). Chaque sujet reçoit
ensuite une seule catégorie, ce qui évite qu'une même actu apparaisse à la fois
dans Monde et dans Europe.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, FrozenSet, List, Optional

from fetcher import Article
from sources import CATEGORY_ORDER

STOPWORDS = frozenset(
    """
    le la les un une des de du d l au aux et ou en dans sur sous pour par avec
    sans ce cet cette ces son sa ses leur leurs qui que quoi dont est sont a ont
    ete etre plus moins pas ne n se s y il elle ils elles on nous vous apres avant
    entre contre vers selon comme mais tout tous toute toutes fait faire va
    the a an of to in on for with and or by at from as is are was were be has have
    after over into says said new
    """.split()
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def title_tokens(title: str) -> FrozenSet[str]:
    text = unicodedata.normalize("NFKD", title.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return frozenset(
        w for w in _WORD_RE.findall(text) if len(w) > 2 and w not in STOPWORDS
    )


def similarity(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    if not a or not b:
        return 0.0
    shared = len(a & b)
    jaccard = shared / len(a | b)
    overlap = shared / min(len(a), len(b))
    # Les titres d'un même sujet varient beaucoup d'un journal à l'autre : on
    # accepte aussi un fort recouvrement quand plusieurs mots-clés sont partagés.
    return max(jaccard, overlap if shared >= 3 else 0.0)


SIMILARITY_THRESHOLD = 0.5


@dataclass
class Story:
    articles: List[Article] = field(default_factory=list)
    tokens: List[FrozenSet[str]] = field(default_factory=list)
    category: str = ""

    @property
    def sources(self) -> List[str]:
        seen: Dict[str, None] = {}
        for article in self.articles:
            seen.setdefault(article.source, None)
        return list(seen)

    @property
    def latest(self) -> Optional[datetime]:
        dates = [a.published for a in self.articles if a.published]
        return max(dates) if dates else None

    @property
    def lead(self) -> Article:
        """Article le plus informatif : français, avec la plus longue description."""
        return max(
            self.articles,
            key=lambda a: (a.lang == "fr", not a.generic, len(a.description)),
        )

    def matches(self, tokens: FrozenSet[str]) -> bool:
        return any(similarity(tokens, t) >= SIMILARITY_THRESHOLD for t in self.tokens)


def filter_recent(
    articles: List[Article],
    now: datetime,
    hours: int = 24,
    fallback_hours: int = 48,
    min_per_category: int = 10,
) -> List[Article]:
    """Garde les articles des dernières `hours` heures.

    Si une catégorie est trop maigre (week-end, flux en panne), on élargit la
    fenêtre à `fallback_hours` pour cette catégorie. Les articles sans date
    sont conservés : beaucoup de flux n'en fournissent pas.
    """

    def within(article: Article, window: int) -> bool:
        if article.published is None:
            return True
        return now - article.published <= timedelta(hours=window)

    kept: List[Article] = []
    for category in CATEGORY_ORDER:
        pool = [a for a in articles if a.category == category]
        recent = [a for a in pool if within(a, hours)]
        if len(recent) < min_per_category:
            recent = [a for a in pool if within(a, fallback_hours)]
        kept.extend(recent)
    return kept


def _dedupe_exact(articles: List[Article]) -> List[Article]:
    """Un même article peut figurer dans plusieurs flux d'une même source."""
    seen = set()
    unique = []
    for article in articles:
        key = article.link or (article.source, article.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def cluster(articles: List[Article]) -> List[Story]:
    """Regroupe les articles traitant du même événement, toutes catégories confondues."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(
        _dedupe_exact(articles), key=lambda a: a.published or epoch, reverse=True
    )
    stories: List[Story] = []
    for article in ordered:
        tokens = title_tokens(article.title)
        story = next((s for s in stories if s.matches(tokens)), None)
        if story is None:
            story = Story()
            stories.append(story)
        story.articles.append(article)
        story.tokens.append(tokens)

    for story in stories:
        story.category = _vote_category(story)
    return stories


def _vote_category(story: Story) -> str:
    # Un flux de rubrique (Le Monde Europe) est plus fiable qu'un flux de une.
    votes: Dict[str, float] = defaultdict(float)
    for article in story.articles:
        votes[article.category] += 0.5 if article.generic else 1.0
    # En cas d'égalité, la catégorie la plus spécifique l'emporte (France > Europe > Monde).
    return max(votes, key=lambda c: (votes[c], CATEGORY_ORDER.index(c)))


def stories_by_category(
    stories: List[Story], max_per_category: int = 40
) -> Dict[str, List[Story]]:
    """Classe les sujets : les plus couverts d'abord, puis les plus récents."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    grouped: Dict[str, List[Story]] = {c: [] for c in CATEGORY_ORDER}
    for story in stories:
        grouped[story.category].append(story)
    for category, items in grouped.items():
        items.sort(key=lambda s: (len(s.sources), s.latest or epoch), reverse=True)
        grouped[category] = items[:max_per_category]
    return grouped
