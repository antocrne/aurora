"""Flux RSS utilisés par Aurora, regroupés par catégorie.

Chaque source peut déclarer plusieurs URLs : la première est l'URL principale,
les suivantes sont des URLs de secours essayées dans l'ordre si la précédente
échoue (erreur HTTP, timeout ou flux vide).

`generic=True` signale un flux « tout-venant » (une, titres) dont les articles
ne relèvent pas forcément de la catégorie. Leur vote pèse moins lors du
classement d'un sujet couvert par plusieurs catégories (voir classifier.py).

Flux vérifiés le 24/10/2026. Retirés ou remplacés :
- Reuters (`reuters.com/rssFeed/worldNews`) : flux public fermé (HTTP 401).
  Remplacé par France Info Monde et Le Figaro International.
- Libération (`liberation.fr/rss/`) : HTTP 403. Remplacé par le flux Arc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Feed:
    name: str
    urls: Tuple[str, ...]
    lang: str = "fr"
    generic: bool = False


CATEGORY_ORDER: List[str] = ["monde", "europe", "france"]

CATEGORY_LABELS: Dict[str, str] = {
    "monde": "Monde",
    "europe": "Europe",
    "france": "France",
}

FEEDS: Dict[str, List[Feed]] = {
    "monde": [
        Feed("France 24", ("https://www.france24.com/fr/rss",), generic=True),
        Feed("BBC", ("https://feeds.bbci.co.uk/news/world/rss.xml",), lang="en"),
        Feed("Le Monde", ("https://www.lemonde.fr/international/rss_full.xml",)),
        Feed("RFI", ("https://www.rfi.fr/fr/rss",), generic=True),
        Feed(
            "Courrier International",
            ("https://www.courrierinternational.com/feed/all/rss.xml",),
            generic=True,
        ),
        Feed("France Info", ("https://www.francetvinfo.fr/monde.rss",)),
        Feed("Le Figaro", ("https://www.lefigaro.fr/rss/figaro_international.xml",)),
    ],
    "europe": [
        Feed("Le Monde", ("https://www.lemonde.fr/europe/rss_full.xml",)),
        Feed("Euronews", ("https://fr.euronews.com/rss",), generic=True),
        Feed("France Info", ("https://www.francetvinfo.fr/monde/europe.rss",)),
        Feed("Toute l'Europe", ("https://www.touteleurope.eu/feed/",)),
        Feed("EURACTIV", ("https://www.euractiv.fr/feed/",)),
        Feed("France 24", ("https://www.france24.com/fr/europe/rss",)),
        Feed("RFI", ("https://www.rfi.fr/fr/europe/rss",)),
    ],
    "france": [
        Feed("Le Monde", ("https://www.lemonde.fr/rss/une.xml",), generic=True),
        Feed("France Info", ("https://www.francetvinfo.fr/titres.rss",), generic=True),
        Feed(
            "Libération",
            (
                "https://www.liberation.fr/arc/outboundfeeds/rss-all/?outputType=xml",
                "https://www.liberation.fr/arc/outboundfeeds/rss/?outputType=xml",
                "https://www.liberation.fr/rss/",
            ),
            generic=True,
        ),
        Feed(
            "Le Figaro",
            ("https://www.lefigaro.fr/rss/figaro_actualites.xml",),
            generic=True,
        ),
        Feed("20 Minutes", ("https://www.20minutes.fr/feeds/rss-une.xml",), generic=True),
        Feed("Mediapart", ("https://www.mediapart.fr/articles/feed",), generic=True),
        Feed("France 24", ("https://www.france24.com/fr/france/rss",)),
        Feed("Le Figaro", ("https://www.lefigaro.fr/rss/figaro_politique.xml",)),
    ],
}


def all_source_names() -> List[str]:
    names = {feed.name for feeds in FEEDS.values() for feed in feeds}
    return sorted(names)
