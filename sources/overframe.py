"""
EKSPERYMENTALNY moduł do overframe.gg.

WAŻNE - przeczytaj przed włączeniem OVERFRAME_ENABLED w config.py:

1. Overframe NIE ma publicznego, udokumentowanego API do "w ilu buildach jest
   używany dany item". To co jest dostępne to dane osadzone w HTML w tagu
   <script id="__NEXT_DATA__"> (potwierdzone przez community na WARFRAME Wiki:
   https://warframe.fandom.com/wiki/WARFRAME_Wiki:Overframe). Struktura tego
   JSON-a nie jest oficjalnie udokumentowana i może się zmienić bez ostrzeżenia.

2. Ten moduł NIE był testowany na żywo (środowisko, w którym go napisano, nie ma
   dostępu sieciowego do overframe.gg). Przed pierwszym pełnym uruchomieniem:
   - uruchom scripts/selftest_overframe.py na jednym znanym itemie
   - sprawdź w przeglądarce (Ctrl+U -> szukaj "__NEXT_DATA__") czy struktura
     JSON-a nadal pasuje do tego, co parsuje `_extract_next_data`
   - sprawdź https://overframe.gg/robots.txt i https://wearemoba.com/terms-of-service/
     przed zwiększaniem skali/częstotliwości requestów

3. Jako proxy na "popyt" z buildów używamy sumy głosów (votes) na topowych
   buildach danego itemu - to najbliższe realnemu use'owi, jakie widać w HTML
   bez zalogowanego dostępu do API.

4. Rate limiting jest celowo konserwatywny (OVERFRAME_DELAY_SECONDS,
   OVERFRAME_MAX_ITEMS_PER_RUN w config.py). Nie zwiększaj agresywnie bez
   sprawdzenia ToS.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from config import OVERFRAME_DELAY_SECONDS, USER_AGENT

log = logging.getLogger(__name__)

SEARCH_URL = "https://overframe.gg/items/all/"
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)
HEADERS = {"User-Agent": USER_AGENT}


def _fetch(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        time.sleep(OVERFRAME_DELAY_SECONDS)
        if resp.status_code != 200:
            log.warning("Overframe zwrócił status %d dla %s", resp.status_code, url)
            return None
        return resp.text
    except requests.RequestException as exc:
        log.warning("Błąd sieci przy %s: %s", url, exc)
        return None


def _extract_next_data(html: str) -> dict[str, Any] | None:
    match = NEXT_DATA_RE.search(html)
    if not match:
        log.warning("Nie znaleziono __NEXT_DATA__ w odpowiedzi - struktura strony mogła się zmienić")
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.warning("Nie udało się sparsować __NEXT_DATA__: %s", exc)
        return None


def slugify(item_name: str) -> str:
    """Best-effort slug w stylu overframe (np. 'Ember Prime' -> 'ember-prime')."""
    return item_name.strip().lower().replace(" ", "-").replace("'", "")


def get_build_usage_signal(item_name: str, item_type: str = "warframes") -> dict[str, Any]:
    """
    Próbuje pobrać sygnał "użycia w buildach" dla danego itemu z Overframe.

    item_type: segment URL overframe, np. "warframes" dla frame'ów, "weapons" dla broni.
    Zwraca dict z build_count / total_votes / raw_found (bool czy w ogóle coś sparsowano).

    Ten sygnał NIE jest precyzyjny - to najlepszy dostępny proxy bez oficjalnego API.
    Jeśli parsing zawiedzie (bardzo prawdopodobne bez lokalnej weryfikacji struktury),
    zwraca raw_found=False, a main.py wpisze do arkusza "N/A (do weryfikacji)".
    """
    slug = slugify(item_name)
    url = f"https://overframe.gg/builds/{item_type}/{slug}/"
    html = _fetch(url)
    if not html:
        return {"build_count": None, "total_votes": None, "raw_found": False, "source_url": url}

    data = _extract_next_data(html)
    if not data:
        return {"build_count": None, "total_votes": None, "raw_found": False, "source_url": url}

    # Struktura __NEXT_DATA__ jest niedokumentowana - próbujemy kilku prawdopodobnych ścieżek.
    # To najbardziej krucha część całego projektu - patrz docstring modułu.
    builds = None
    try:
        page_props = data.get("props", {}).get("pageProps", {})
        for key in ("builds", "buildList", "results"):
            if key in page_props:
                builds = page_props[key]
                break
    except AttributeError:
        pass

    if not builds:
        log.info("Nie znaleziono listy buildów w __NEXT_DATA__ dla %s - wymaga ręcznej weryfikacji struktury", item_name)
        return {"build_count": None, "total_votes": None, "raw_found": False, "source_url": url}

    total_votes = sum(b.get("votes", 0) for b in builds if isinstance(b, dict))
    return {
        "build_count": len(builds),
        "total_votes": total_votes,
        "raw_found": True,
        "source_url": url,
    }
