"""Aurora — génère le briefing quotidien dans docs/summaries.json.

Usage :
    python backend/main.py              # flux RSS → Mistral → docs/summaries.json
    python backend/main.py --dry-run    # sans appel Mistral (résumés extractifs)

En cas d'échec (Mistral injoignable, catégorie vide…), le script sort avec un
code non nul sans toucher au fichier existant : l'app continue d'afficher
l'édition précédente et GitHub Actions signale l'échec.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from classifier import cluster, filter_recent, stories_by_category
from fetcher import fetch_all
from sources import CATEGORY_LABELS, CATEGORY_ORDER, FEEDS
from summarizer import SummarizerError, check_placements, summarize, summarize_offline

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "docs" / "summaries.json"
PARIS = ZoneInfo("Europe/Paris")
# Espace les appels Mistral pour rester sous les limites de débit de l'offre gratuite.
PAUSE_BETWEEN_CALLS = 5
WRITING_ORDER = ["europe", "france", "monde"]
MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

log = logging.getLogger("aurora")


def edition_label(moment: datetime) -> str:
    local = moment.astimezone(PARIS)
    day = "1er" if local.day == 1 else str(local.day)
    return f"{day} {MONTHS[local.month - 1]} {local.year}"


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run(dry_run: bool, output: Path, model: str, angles: bool = True) -> int:
    now = datetime.now(timezone.utc)

    articles, failures = fetch_all(FEEDS)
    total_feeds = sum(len(feeds) for feeds in FEEDS.values())
    log.info("%d articles récupérés, %d/%d flux en échec", len(articles), len(failures), total_feeds)
    if len(failures) > total_feeds // 2:
        log.error("Plus de la moitié des flux sont en échec, abandon")
        return 1

    recent = filter_recent(articles, now)
    stories = cluster(recent)
    grouped = stories_by_category(stories)
    log.info(
        "%d articles récents → %d sujets (%s)",
        len(recent),
        len(stories),
        ", ".join(f"{c}: {len(grouped[c])}" for c in CATEGORY_ORDER),
    )

    # Les rubriques les plus spécifiques passent d'abord ; leurs manchettes sont
    # transmises aux suivantes pour qu'un même sujet (ex. l'Ukraine) ne figure
    # pas à la fois dans Europe et dans Monde.
    written: dict = {}
    covered: list = []
    for index, category in enumerate(WRITING_ORDER):
        if index and not dry_run:
            time.sleep(PAUSE_BETWEEN_CALLS)
        label = CATEGORY_LABELS[category]
        items = grouped[category]
        if not items:
            log.error("Aucun article pour %s, abandon", label)
            return 1
        try:
            if dry_run:
                topics = summarize_offline(items)
            else:
                topics = summarize(label, items, model, edition_label(now), covered, angles)
        except SummarizerError as exc:
            log.error("%s : %s", label, exc)
            return 1
        log.info("%s : %d sujets rédigés", label, len(topics))
        covered.extend(str(topic["headline"]) for topic in topics)
        written[category] = topics

    # Contrôle du classement (un article de « Toute l'Europe » sur Israël
    # relève de Monde) : géographie d'abord, Mistral pour les cas ambigus.
    # Un échec de Mistral ici ne bloque pas l'édition.
    if not dry_run:
        time.sleep(PAUSE_BETWEEN_CALLS)
    check_placements(written, model, ask_model=not dry_run)
    categories = [
        {"id": c, "label": CATEGORY_LABELS[c], "topics": written[c]} for c in CATEGORY_ORDER
    ]

    write_atomic(
        output,
        {
            "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "edition": edition_label(now),
            "categories": categories,
        },
    )
    log.info("Édition écrite dans %s", output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère le briefing Aurora")
    parser.add_argument("--dry-run", action="store_true", help="ne pas appeler Mistral")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-angles", action="store_true", help="ne pas rédiger la « lecture croisée » entre médias"
    )
    parser.add_argument("--model", default="", help="modèle Mistral (défaut : ministral-14b-latest, avec repli)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    return run(args.dry_run, args.output, args.model, not args.no_angles)


if __name__ == "__main__":
    sys.exit(main())
