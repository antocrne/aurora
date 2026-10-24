"""Diagnostic de la clé Mistral : modèles accessibles et quotas annoncés.

Usage : MISTRAL_API_KEY=... python backend/check_mistral.py

Liste les modèles visibles par la clé, puis envoie une requête minuscule
(1 token) à quelques modèles candidats et affiche le code HTTP et les en-têtes
de quota. Sort toujours avec le code 0 : c'est un outil d'inspection.
"""

from __future__ import annotations

import os
import time

import requests

BASE_URL = "https://api.mistral.ai/v1"
CANDIDATES = [
    "ministral-14b-latest",
    "mistral-small-latest",
    "ministral-8b-latest",
    "ministral-3b-latest",
    "open-mistral-nemo",
    "mistral-medium-latest",
    "mistral-large-latest",
]


def quota_headers(response: requests.Response) -> dict:
    return {k: v for k, v in response.headers.items() if "ratelimit" in k.lower()}


def main() -> None:
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        print("MISTRAL_API_KEY n'est pas défini")
        return
    headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(f"{BASE_URL}/models", headers=headers, timeout=30)
    print(f"GET /models → HTTP {response.status_code} {quota_headers(response)}")
    if response.ok:
        models = sorted({m.get("id", "") for m in response.json().get("data", [])})
        print(f"{len(models)} modèles visibles : {', '.join(models)}")
    else:
        print(response.text[:300])

    for model in CANDIDATES:
        time.sleep(3)
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Bonjour"}],
                "max_tokens": 1,
            },
            timeout=60,
        )
        detail = "" if response.ok else " " + response.text[:200]
        print(f"{model:24} → HTTP {response.status_code} {quota_headers(response)}{detail}")


if __name__ == "__main__":
    main()
