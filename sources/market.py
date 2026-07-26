"""
Wrapper na oficjalne (publiczne, nieautoryzowane) API warframe.market.

POPRAWKA (po realnym teście u Huberta): stare API v1 zwraca 404 - v1 zostało
wyłączone. Dokumentacja (https://docs.warframe.market/) potwierdza:
  "The legacy v1 API is deprecated and unsupported."

Przepisane na v2, potwierdzone w dokumentacji:
  GET /v2/items                       - lista wszystkich itemów (pole 'slug', nie 'url_name')
  GET /v2/orders/item/{slug}          - aktywne oferty dla itemu

NIE POTWIERDZONE w 100% (dokumentacja v2 nie wystawia jeszcze publicznie strony
dla statystyk historycznych w momencie pisania tego kodu):
  GET /v1/items/{slug}/statistics     - próbujemy starego v1 jako best-effort;
                                         jeśli zwróci 404, kod NIE wywala się -
                                         po prostu volume_48h/90d wychodzi 0,
                                         a Market Demand Index liczy się z pozostałych sygnałów.

"""

from __future__ import annotations

import time
import logging
from typing import Any

import requests

from config import USER_AGENT

log = logging.getLogger(__name__)

BASE_URL_V2 = "https://api.warframe.market/v2"
BASE_URL_V1 = "https://api.warframe.market/v1"  # tylko jako fallback dla statistics

HEADERS = {
    "accept": "application/json",
    "Platform": "pc",
    "Language": "en",
    "User-Agent": USER_AGENT,
}

REQUEST_DELAY = 0.4  # bezpieczny margines pod limit 3 req/s
MAX_RETRIES = 3


def _get(url: str) -> dict[str, Any] | None:
    """GET z retry/backoff. Zwraca cały zdekodowany JSON (nie tylko payload/data)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException as exc:
            log.warning("Network error on %s (attempt %d/%d): %s", url, attempt, MAX_RETRIES, exc)
            time.sleep(REQUEST_DELAY * attempt)
            continue

        if resp.status_code == 200:
            time.sleep(REQUEST_DELAY)
            try:
                return resp.json()
            except ValueError:
                log.warning("Odpowiedź z %s nie jest poprawnym JSON-em", url)
                return None

        if resp.status_code == 429:
            wait = 2 ** attempt
            log.warning("Rate limited na %s, czekam %ds", url, wait)
            time.sleep(wait)
            continue

        if resp.status_code == 404:
            log.warning("404 na %s", url)
            return None

        log.warning("Nieoczekiwany status %d na %s", resp.status_code, url)
        time.sleep(REQUEST_DELAY * attempt)

    log.error("Poddaję się przy %s po %d próbach", url, MAX_RETRIES)
    return None


def get_all_items() -> list[dict[str, Any]]:
    """
    Pełna lista itemów z warframe.market (v2). Każdy item ma m.in. 'slug' i 'i18n'
    (nazwa w różnych językach - angielska pod i18n['en']['name'] wg modelu v2).
    Zwraca listę znormalizowaną do kluczy: slug, item_name.
    """
    body = _get(f"{BASE_URL_V2}/items")
    if not body:
        return []

    raw_items = body.get("data", [])
    if not raw_items:
        log.warning("GET /v2/items zwrócił pustą listę lub nieoczekiwany kształt: %s", list(body.keys()))
        return []

    normalized = []
    for item in raw_items:
        slug = item.get("slug")
        # Nazwa bywa albo bezpośrednio w 'name', albo zagnieżdżona w i18n - próbujemy obu
        name = item.get("name") or (item.get("i18n", {}).get("en", {}).get("name"))
        if slug and name:
            normalized.append({"slug": slug, "item_name": name})
    return normalized


def find_matching_item_name(query: str, all_items: list[dict[str, Any]]) -> str | None:
    """Znajdź najlepiej pasującą nazwę itemu dla starego slug/aliasu."""
    normalized_query = query.replace("_", " ").strip().lower()
    exact_matches = [item for item in all_items if item["slug"] == query]
    if exact_matches:
        return exact_matches[0]["item_name"]

    by_name = [item for item in all_items if item["item_name"].strip().lower() == normalized_query]
    if by_name:
        return by_name[0]["item_name"]

    fuzzy = [item for item in all_items if normalized_query in item["slug"] or normalized_query in item["item_name"].lower()]
    if fuzzy:
        return fuzzy[0]["item_name"]

    return None


def get_orders(slug: str) -> list[dict[str, Any]]:
    """Aktywne oferty (kupno + sprzedaż) dla itemu, v2: GET /v2/orders/item/{slug}."""
    body = _get(f"{BASE_URL_V2}/orders/item/{slug}")
    if not body:
        return []
    return body.get("data", [])


def get_statistics(slug: str) -> dict[str, Any]:
    """
    Best-effort: v1 statistics endpoint. Może nie istnieć / zwrócić 404 skoro
    v1 jest wyłączane. Jeśli tak, zwracamy pusty dict - reszta pipeline'u
    działa dalej (Demand Score po prostu nie uwzględni wolumenu).
    """
    body = _get(f"{BASE_URL_V1}/items/{slug}/statistics")
    if not body:
        return {}
    return body.get("payload", {}).get("statistics_closed", {})


def get_item_details(slug: str) -> dict[str, Any]:
    """Szczegóły itemu v2, w tym informacja czy jest tradowalny."""
    body = _get(f"{BASE_URL_V2}/items/{slug}")
    if not body:
        return {}
    return body.get("data", {})


def _order_platinum(order: dict[str, Any]) -> int | None:
    return order.get("platinum")


def _order_type(order: dict[str, Any]) -> str | None:
    return order.get("type") or order.get("order_type")


def _order_user_status(order: dict[str, Any]) -> str | None:
    user = order.get("user", {})
    return user.get("status") if isinstance(user, dict) else None


def summarize_item(slug: str, use_statistics: bool = True) -> dict[str, Any]:
    """Ujednolicone dane rynkowe dla jednego itemu - patrz market.py docstring modułu."""
    orders = get_orders(slug)
    details = get_item_details(slug)
    tradable = details.get("tradable")

    sell_orders = sorted(
        (o for o in orders if _order_type(o) == "sell" and _order_user_status(o) in ("ingame", "online")),
        key=lambda o: _order_platinum(o) or 10**9,
    )
    buy_orders = [o for o in orders if _order_type(o) == "buy"]

    lowest_sell = _order_platinum(sell_orders[0]) if sell_orders else None
    top5 = sell_orders[:5]
    prices = [p for o in top5 if (p := _order_platinum(o)) is not None]
    avg_sell_top5 = round(sum(prices) / len(prices), 1) if prices else None

    stats = get_statistics(slug)
    vol_48h = sum(entry.get("volume", 0) for entry in stats.get("48hours", []))
    entries_90d = stats.get("90days", [])
    vol_90d_avg = round(sum(e.get("volume", 0) for e in entries_90d) / len(entries_90d), 2) if entries_90d else 0

    return {
        "slug": slug,
        "tradable": tradable,
        "lowest_sell_price": lowest_sell,
        "avg_sell_price_top5": avg_sell_top5,
        "buy_orders_count": len(buy_orders),
        "sell_orders_count": len(sell_orders),
        "total_buy_quantity": sum(o.get("quantity", 1) for o in buy_orders),
        "volume_48h": vol_48h,
        "volume_90d_avg": vol_90d_avg,
    }
