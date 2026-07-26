"""
Dla części Prime (np. "Ash Prime Systems") pole 'description' w WFCD warframe-items
zwraca tylko generyczny tekst typu "Systems component of the Ash Prime Warframe" -
bez informacji, z jakich reliktów dropi. Ten moduł domapowuje relikty z
WFCD/warframe-drop-data (MIT/permissive, dane z Warframe Wikia zagregowane do JSON,
NIE jest to live-scraping wiki - jednorazowy, cache'owany plik danych).

Zweryfikowane w tym środowisku: endpoint odpowiada 200, schemat jak w komentarzach niżej.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from config import CACHE_DIR, WFCD_CACHE_TTL_HOURS, USER_AGENT

log = logging.getLogger(__name__)

RELICS_URL = "https://raw.githubusercontent.com/WFCD/warframe-drop-data/gh-pages/data/relics.json"
CACHE_FILE = CACHE_DIR / "wfcd_relics.json"

_index: dict[str, list[dict[str, Any]]] | None = None


def _cache_is_fresh() -> bool:
    if not CACHE_FILE.exists():
        return False
    age_hours = (time.time() - CACHE_FILE.stat().st_mtime) / 3600
    return age_hours < WFCD_CACHE_TTL_HOURS


def _load_index() -> dict[str, list[dict[str, Any]]]:
    global _index
    if _index is not None:
        return _index

    if not _cache_is_fresh():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(RELICS_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        CACHE_FILE.write_bytes(resp.content)

    with open(CACHE_FILE, encoding="utf-8") as f:
        data = json.load(f)

    idx: dict[str, list[dict[str, Any]]] = {}
    # struktura: {"relics": [{"tier": "Axi", "relicName": "A1", "state": "Intact",
    #             "rewards": [{"itemName": "...", "rarity": "...", "chance": 11}, ...]}, ...]}
    for relic in data.get("relics", []):
        for reward in relic.get("rewards", []):
            key = reward.get("itemName", "").strip().lower()
            if not key:
                continue
            relic_label = f"{relic['tier']} {relic['relicName']}" if "relicName" in relic else relic["tier"]
            idx.setdefault(key, []).append({
                "relic": relic_label,
                "state": relic.get("state"),
                "rarity": reward.get("rarity"),
                "chance": reward.get("chance"),
            })

    _index = idx
    log.info("Załadowano relikty dla %d itemów z WFCD warframe-drop-data", len(_index))
    return _index


def get_relic_sources(display_name: str) -> list[dict[str, Any]] | None:
    """
    display_name: np. "Ash Prime Systems" (jak sprzedawane na warframe.market).
    Relics.json trzyma nagrody jako "Ash Prime Systems Blueprint" - dopisujemy
    " Blueprint" jeśli sam item name nie trafi, co pokrywa większość części Prime
    (Systems/Chassis/Neuroptics/Blueprint samego seta wymagają BP, komponenty broni
    i akcesoria zwykle nie).
    """
    idx = _load_index()
    key = display_name.strip().lower()
    if key in idx:
        return idx[key]
    alt_key = f"{key} blueprint"
    if alt_key in idx:
        return idx[alt_key]
    return None


def format_relic_note(sources: list[dict[str, Any]]) -> str:
    # Bierzemy relikt o najwyższym chance (najbardziej "wydajny" do zdobycia), max 3
    best = sorted(sources, key=lambda s: s.get("chance") or 0, reverse=True)[:3]
    parts = [f"{s['relic']} ({s['state']}, {s['rarity']}, {s['chance']}%)" for s in best]
    return "Relikty: " + "; ".join(parts)
