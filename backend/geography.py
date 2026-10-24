"""Contrôle géographique du classement Monde / Europe / France.

Un petit modèle range mal certains sujets (l'Allemagne dans Monde, Israël
dans Europe…). On compte ici les lieux, gentilés, institutions et quelques
dirigeants cités dans le titre (poids fort) et le résumé : quand une rubrique
l'emporte nettement, c'est elle qui fait foi.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Optional

# Termes sans accents ni majuscules. Un « * » final accepte toutes les
# terminaisons (« allemand* » couvre allemande, allemands…).
TERMS: Dict[str, str] = {
    "france": """
        france francais* paris* marseille lyon toulouse nantes strasbourg bordeaux lille rennes
        corse nouvelle-caledonie* mayotte guadeloupe martinique guyane yvelines
        elysee matignon assemblee-nationale gouvernement-francais
        macron bardella le-pen melenchon rassemblement-national
    """,
    "europe": """
        europe europeen* union-europeenne commission-europeenne parlement-europeen ue bce otan
        allemagne allemand* berlin munich baviere* autriche autrichien* belgique belge* bruxelles
        bulgarie bulgare* croatie croate* chypre chypriote* danemark danois* copenhague
        espagne espagnol* madrid barcelone estonie estonien* finlande finlandais* helsinki
        grece grec grecque* athenes hongrie hongrois* budapest irlande irlandais* dublin
        italie italien* rome milan lettonie letton* lituanie lituanien* luxembourg
        malte maltais* pays-bas neerlandais* amsterdam pologne polonais* varsovie
        portugal portugais* lisbonne roumanie roumain* bucarest slovaquie slovaque*
        slovenie slovene* suede suedois* stockholm royaume-uni britannique* londres ecosse
        suisse norvege norvegien* oslo islande ukraine ukrainien* kiev kyiv kharkiv odessa
        russie russe* moscou kremlin bielorussie belarus moldavie serbie serbe* belgrade
        bosnie kosovo albanie albanais* macedoine montenegro
        zelensky poutine meloni orban merz starmer
    """,
    "monde": """
        etats-unis americain* washington new-york maison-blanche trump canada canadien*
        mexique mexicain* bresil bresilien* argentine chili colombie venezuela perou cuba haiti
        lula bolsonaro chine chinois* pekin japon japonais* tokyo coree* inde indien* pakistan
        afghanistan bangladesh indonesie philippines vietnam thailande birmanie taiwan*
        australie nouvelle-zelande israel israelien* gaza cisjordanie palestin* netanyahou hamas
        liban libanais* hezbollah syrie syrien* irak iran iranien* teheran arabie-saoudite saoudien*
        yemen houthi* sanaa qatar emirats jordanie egypte libye tunisie algerie maroc soudan
        ethiopie kenya nairobi nigeria senegal mali niger burkina congo rdc afrique* cameroun
        tchad somalie rwanda madagascar onu nations-unies
    """,
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    # « Pays-Bas », « Union européenne » → un seul mot avec tirets.
    text = re.sub(r"[’'`]", " ", text)
    return re.sub(r"\s+", " ", text)


def _pattern(term: str) -> re.Pattern:
    word = re.escape(term.rstrip("*")).replace(r"\-", r"[\s-]")
    suffix = r"\w*" if term.endswith("*") else ""
    return re.compile(rf"\b{word}{suffix}\b")


PATTERNS = {
    category: [_pattern(term) for term in terms.split()]
    for category, terms in TERMS.items()
}

HEADLINE_WEIGHT = 3


def scores(headline: str, summary: str) -> Dict[str, int]:
    """Nombre de termes distincts de chaque rubrique, le titre comptant triple."""
    title, body = _normalize(headline), _normalize(summary)
    result = {}
    for category, patterns in PATTERNS.items():
        result[category] = sum(
            HEADLINE_WEIGHT * bool(p.search(title)) + bool(p.search(body)) for p in patterns
        )
    return result


def locate(headline: str, summary: str) -> Optional[str]:
    """Rubrique qui l'emporte nettement, ou None si c'est ambigu."""
    ranked = sorted(scores(headline, summary).items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top >= 3 and top >= 1.5 * second + 1:
        return best
    return None
