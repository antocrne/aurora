# Aurora

Le briefing quotidien de l'actualité, en texte seulement : **Monde**, **Europe**, **France**, lisible en moins de dix minutes, dans une app iOS au style de journal classique.

```
flux RSS ──► backend Python ──► Mistral ──► docs/summaries.json ──► GitHub Pages ──► app iOS
             (GitHub Actions, chaque matin)
```

## Backend (`backend/`)

| Fichier | Rôle |
|---|---|
| `sources.py` | Flux RSS par catégorie, avec URLs de secours |
| `fetcher.py` | Téléchargement parallèle et parsing des flux (retries, timeouts) |
| `classifier.py` | Fenêtre de 24 h, regroupement des articles par sujet, choix de la catégorie |
| `summarizer.py` | Prompt et appel de l'API Mistral (REST), validation du JSON renvoyé |
| `main.py` | Orchestration et écriture de `docs/summaries.json` |

### Lancer en local

```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
.venv/bin/python backend/main.py --dry-run            # sans Mistral : résumés extractifs
MISTRAL_API_KEY=... .venv/bin/python backend/main.py  # édition réelle
```

Modèle par défaut : `mistral-small-latest`. Options : `--model mistral-large-latest` (ou variable `MISTRAL_MODEL`) si ton offre Mistral y donne accès, `--output chemin.json`.

### Robustesse

- Chaque flux peut avoir plusieurs URLs : on passe à la suivante si l'une échoue ou renvoie un flux vide.
- Un flux en panne est ignoré ; si plus de la moitié tombent, l'édition est abandonnée.
- Si Mistral échoue (après plusieurs essais) ou si une catégorie est vide, le script sort en erreur **sans écraser** `summaries.json` : l'app garde l'édition de la veille et GitHub signale l'échec par e-mail.

### Sources

Vérifiées le 24/10/2026. Deux URLs de la spec d'origine ne répondaient plus :

- **Reuters** (`rssFeed/worldNews`, flux fermé) : remplacé par France Info Monde et Le Figaro International.
- **Libération** (`/rss/`, 403) : remplacé par le flux Arc `outboundfeeds/rss-all`.

France 24 Europe/France, RFI Europe et Le Figaro Politique ont été ajoutés pour mieux couvrir les rubriques.

## Publication (GitHub Actions + Pages)

1. Dans *Settings → Secrets and variables → Actions*, ajouter le secret `AURORA_KEY` (clé d'API Mistral). Facultatif : une variable `MISTRAL_MODEL`.
2. Dans *Settings → Pages*, servir la branche `main`, dossier `/docs`.
3. Le workflow [`.github/workflows/daily.yml`](.github/workflows/daily.yml) tourne chaque jour à 6 h UTC (et à la demande depuis l'onglet *Actions*).

Le JSON est ensuite servi à `https://antocrne.github.io/aurora/summaries.json`.

> Le workflow doit se trouver à la racine du dépôt (`.github/workflows/`) : GitHub Actions ignore les workflows placés dans un sous-dossier comme `backend/`.

## App iOS (`ios/`)

SwiftUI, iOS 17+, aucune dépendance. Le projet Xcode est généré par [XcodeGen](https://github.com/yonaskolb/XcodeGen) à partir de `ios/project.yml` :

```bash
cd ios && xcodegen generate && open Aurora.xcodeproj
```

- `Models/Summary.swift` : structures `Codable` (`Summary`, `Category`, `Topic`).
- `Services/SummaryService.swift` : téléchargement et cache disque (lecture hors ligne).
- `Services/BriefingStore.swift` : état observable, rechargement au retour au premier plan.
- `Views/` : en-tête, navigation MONDE · EUROPE · FRANCE (toucher ou balayer), liste des sujets avec lettrine, pied de page, pull-to-refresh.
- `Theme/AuroraTheme.swift` : couleurs clair/sombre, typographie New York (serif système), filets.

Pour tester l'app contre un JSON local :

```bash
cd docs && python3 -m http.server 8765
```

puis, dans le schéma Xcode (*Run → Arguments → Environment Variables*), définir `AURORA_FEED_URL=http://127.0.0.1:8765/summaries.json`.
