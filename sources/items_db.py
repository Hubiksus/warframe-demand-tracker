"""
Wrapper na WFCD/warframe-items (https://github.com/WFCD/warframe-items).

To NIE jest scraping wiki.warframe.com. To community-maintained, MIT-licencjonowana
paczka danych zasilana bezpośrednio danymi z gry (Warframe Public Export) - zawiera
opis/lokalizację dropu, kategorię, komponenty i pole "parents" (w czym item jest
używany jako składnik craftingu). Bardziej stabilne niż parsowanie prozy z wiki.

Plik All.json ma ~54 MB, więc cache'ujemy go lokalnie na WFCD_CACHE_TTL_HOURS.
Zweryfikowane w tym środowisku: endpoint odpowiada 200 i zwraca oczekiwany schemat.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

from config import CACHE_DIR, WFCD_CACHE_TTL_HOURS, USER_AGENT

log = logging.getLogger(__name__)

ALL_ITEMS_URL = "https://raw.githubusercontent.com/WFCD/warframe-items/master/data/json/All.json"
CACHE_FILE = CACHE_DIR / "wfcd_all_items.json"

_index: dict[str, dict[str, Any]] | None = None  # lazy-loaded, normalized-name -> item dict


def _cache_is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age_hours = (time.time() - CACHE_FILE.stat().st_mtime) / 3600
    return age_hours < WFCD_CACHE_TTL_HOURS


def _download_all_items() -> None:
    log.info("Pobieram WFCD warframe-items All.json (~54MB, raz na %dh)...", WFCD_CACHE_TTL_HOURS)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(ALL_ITEMS_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    CACHE_FILE.write_bytes(resp.content)


def _normalize(name: str) -> str:
    return name.strip().lower()


def _load_index() -> dict[str, dict[str, Any]]:
    """
    Buduje indeks nazwa -> item. WAŻNA PUŁAPKA (potwierdzona empirycznie):
    warframe.market sprzedaje osobno komponenty setów (np. "Ash Prime Systems",
    "Ash Prime Blueprint"), ale w WFCD warframe-items te komponenty NIE są
    osobnymi top-level itemami - siedzą zagnieżdżone w polu "components"
    rodzica (item "Ash Prime" -> components: [{"name": "Systems", ...}, ...]).
    Dlatego oprócz top-level itemów indeksujemy też "{Rodzic} {Komponent}"
    (np. "Ash Prime Systems") jako klucz wskazujący na dict komponentu.
    """
    global _index
    if _index is not None:
        return _index

    if not _cache_is_fresh():
        _download_all_items()

    with open(CACHE_FILE, encoding="utf-8") as f:
        items = json.load(f)

    idx: dict[str, dict[str, Any]] = {}
    for item in items:
        name = item.get("name")
        if not name:
            continue
        idx[_normalize(name)] = item

        for comp in item.get("components", []) or []:
            comp_name = comp.get("name")
            if not comp_name:
                continue
            composite_key = _normalize(f"{name} {comp_name}")
            idx.setdefault(composite_key, {**comp, "category": item.get("category"), "_parent": name})

    _index = idx
    log.info("Załadowano %d kluczy (itemy + komponenty setów) z WFCD warframe-items", len(_index))
    return _index


def find_item(display_name: str) -> dict[str, Any] | None:
    """
    Szuka itemu po nazwie wyświetlanej, np. "Orokin Cell" albo "Ash Prime Systems".
    Warframe.market czasem używa nazw typu "ash_prime_set" (url_name) zamiast pełnej nazwy -
    w main.py mapujemy url_name -> item_name przez get_all_items() z market.py.
    """
    idx = _load_index()
    return idx.get(_normalize(display_name))


def get_best_drop_entry(display_name: str) -> dict[str, Any] | None:
    item = find_item(display_name)
    if not item:
        return None
    drops = item.get("drops") or []
    if not drops:
        return None
    return max(drops, key=lambda d: (d.get("chance") or 0))


def estimate_mission_duration_from_drop(drop: dict[str, Any]) -> float | None:
    if not drop:
        return None
    location = (drop.get("location") or "").lower()
    if not location:
        return None

    vendor_keywords = [
        "general",
        "partner",
        "syndicate",
        "new loka",
        "steel meridian",
        "arbiter",
        "red veil",
        "cephalon",
        "baro",
        "simaris",
        "prime vault",
        "nightmare mode rewards",
    ]
    if any(keyword in location for keyword in vendor_keywords):
        return None

    if any(keyword in location for keyword in [
        "survival",
        "defense",
        "interception",
        "excavation",
        "exterminate",
        "assassinate",
        "sabotage",
        "capture",
        "spy",
        "rescue",
        "disruption",
        "mobile defense",
        "raid",
    ]):
        return 6.0

    if any(keyword in location for keyword in [
        "bounty",
        "open world",
        "cetus",
        "orb vallis",
        "deimos",
        "steel path",
        "sortie",
        "nightmare",
    ]):
        return 10.0

    if "void" in location or "relic" in location or "apothic" in location:
        return 7.0

    return 7.0


def estimate_platinum_per_minute(display_name: str, price: float | None) -> float | None:
    if price is None:
        return None
    drop = get_best_drop_entry(display_name)
    if not drop:
        return None
    chance = drop.get("chance")
    if chance is None or chance <= 0:
        return None
    duration = estimate_mission_duration_from_drop(drop)
    if duration is None or duration <= 0:
        return None
    return round(price * chance / 100 / duration, 2)


def get_category(display_name: str) -> str | None:
    item = find_item(display_name)
    return item.get("category") if item else None


def get_crafting_uses(display_name: str) -> list[str]:
    """
    Lista itemów, do których zbudowania potrzebny jest ten item.
    Dla top-level itemów (surowce, mody) -> pole 'parents'.
    Dla komponentów setów (np. "Ash Prime Systems") -> sam rodzic (Warframe/broń),
    bo do tego dokładnie ten komponent służy.
    """
    item = find_item(display_name)
    if not item:
        return []
    if "_parent" in item:
        return [item["_parent"]]
    return item.get("parents", []) or []


def get_acquisition_note(display_name: str) -> str:
    """
    Notatka 'jak zdobyć'. Priorytet:
      1. Relikty (sources/relics.py) - najbardziej precyzyjne dla części Prime
      2. Pole 'description' z WFCD (zwykle zawiera linię 'Location: ...')
      3. Fallback: link do wiki.warframe.com do ręcznej weryfikacji
    """
    from sources import relics  # import lokalny, żeby uniknąć cyklicznych importów

    relic_sources = relics.get_relic_sources(display_name)
    if relic_sources:
        return relics.format_relic_note(relic_sources)

    item = find_item(display_name)
    wiki_url = f"https://wiki.warframe.com/w/{display_name.replace(' ', '_')}"

    if not item:
        return f"Brak danych w WFCD - sprawdź ręcznie: {wiki_url}"

    description = (item.get("description") or "").strip()
    if description:
        note = " | ".join(line.strip() for line in description.splitlines() if line.strip())
        return note

    return f"Brak opisu w WFCD - sprawdź ręcznie: {wiki_url}"
