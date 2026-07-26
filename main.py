"""
Uruchom: python main.py

Pipeline:
  1. warframe.market: mapuje url_name -> item_name, ciągnie orders + statistics
  2. WFCD warframe-items: kategoria, crafting uses ("parents"), acquisition note
  3. (opcjonalnie) Overframe: sygnał użycia w buildach
  4. Liczy input do Market Demand Index (sama normalizacja/formuła siedzi w Excelu, patrz build_excel.py)
  5. Zapisuje output/warframe_demand_tracker.xlsx

Do automatycznego, cyklicznego odpalania: patrz README.md (Windows Task Scheduler / cron).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from config import (
    WATCHLIST,
    OUTPUT_XLSX,
    SCAN_CACHE_JSON,
    OVERFRAME_ENABLED,
    OVERFRAME_MAX_ITEMS_PER_RUN,
    TRADABLE_ONLY,
    MAX_ITEMS_OUTPUT,
    TOP_N_BY,
    USE_ALL_MARKET_ITEMS,
    ALL_MARKET_ITEMS_LIMIT,
)
from sources import market, items_db
from demand import compute_demand_scores
from build_excel import build_workbook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def build_url_name_to_item_name_map() -> tuple[dict[str, str], list[dict[str, str]]]:
    log.info("Pobieram pełną listę itemów z warframe.market...")
    all_items = market.get_all_items()
    if not all_items:
        log.error(
            "Nie udało się pobrać listy itemów z warframe.market. "
            "Sprawdź połączenie sieciowe / czy api.warframe.market nie zmienił kontraktu."
        )
        sys.exit(1)
    return ({i["slug"]: i["item_name"] for i in all_items}, all_items)


def save_scan_cache(rows: list[dict], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created": dt.datetime.now().isoformat(),
        "rows": rows,
    }
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_scan_cache(cache_path: Path) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception("Nie udało się wczytać cache skanu z %s", cache_path)
        return None


def estimate_platinum_per_minute_from_market(market_summary: dict[str, Any]) -> float | None:
    price = market_summary.get("avg_sell_price_top5") or market_summary.get("lowest_sell_price")
    if price is None or price <= 0:
        return None
    vol_90d = market_summary.get("volume_90d_avg") or 0
    vol_48h = market_summary.get("volume_48h") or 0
    daily_volume = vol_90d if vol_90d > 0 else (vol_48h / 48 if vol_48h > 0 else 0)
    if daily_volume <= 0:
        return None
    return round(price * daily_volume / 1440, 2)


def process_item(url_name: str, item_name: str, overframe_budget: list[int], use_statistics: bool = True, tradable_only: bool = True) -> dict | None:
    log.info("Przetwarzam: %s (%s)", item_name, url_name)

    market_summary = market.summarize_item(url_name, use_statistics=use_statistics)
    if tradable_only and market_summary.get("tradable") is False:
        log.info("Pominięto niehandlowalny item: %s (%s)", item_name, url_name)
        return None

    category = items_db.get_category(item_name)
    crafting_uses = items_db.get_crafting_uses(item_name)
    acquisition_note = items_db.get_acquisition_note(item_name)

    overframe_usage_text = "N/A (Overframe wyłączony w config.py)"
    if OVERFRAME_ENABLED and overframe_budget[0] > 0:
        from sources import overframe  # import lokalny - moduł eksperymentalny

        signal = overframe.get_build_usage_signal(item_name)
        overframe_budget[0] -= 1
        if signal["raw_found"]:
            overframe_usage_text = f"{signal['build_count']} buildów, {signal['total_votes']} głosów"
        else:
            overframe_usage_text = "Nie udało się sparsować (patrz sources/overframe.py)"

    crafting_uses_text = ", ".join(crafting_uses[:8]) if crafting_uses else "brak (surowiec końcowy / nie jest komponentem)"
    if len(crafting_uses) > 8:
        crafting_uses_text += f" (+{len(crafting_uses) - 8} więcej)"

    avg_sell_price = market_summary.get("avg_sell_price_top5") or market_summary.get("lowest_sell_price") or 0
    estimated_grind_yield = items_db.estimate_platinum_per_minute(item_name, avg_sell_price)

    volume_48h = market_summary.get("volume_48h", 0)
    volume_90d_avg = market_summary.get("volume_90d_avg", 0)
    if volume_48h > 0 and volume_90d_avg > 0:
        sales_count = int(round(((volume_48h / 2) + volume_90d_avg) / 2))
    else:
        sales_count = int(round(volume_90d_avg or (volume_48h / 2)))

    return {
        "slug": url_name,
        "item_name": item_name,
        "category": category or "?",
        "tradable": market_summary.get("tradable"),
        "lowest_sell_price": market_summary.get("lowest_sell_price"),
        "avg_sell_price_top5": market_summary.get("avg_sell_price_top5"),
        "buy_orders_count": market_summary.get("buy_orders_count", 0),
        "sell_orders_count": market_summary.get("sell_orders_count", 0),
        "volume_48h": volume_48h,
        "volume_90d_avg": volume_90d_avg,
        "sales_count": sales_count,
        "avg_sell_price": avg_sell_price,
        "crafting_uses_count": len(crafting_uses),
        "estimated_grind_yield": estimated_grind_yield,
        "crafting_uses_text": crafting_uses_text,
        "overframe_usage_text": overframe_usage_text,
        "acquisition_note": acquisition_note,
    }


def resolve_item_name(
    url_name: str,
    url_to_name: dict[str, str],
    all_items: list[dict[str, str]],
) -> str | None:
    item_name = url_to_name.get(url_name)
    if item_name:
        return item_name
    return market.find_matching_item_name(url_name, all_items)


def estimate_run_time(
    item_count: int,
    use_statistics: bool = True,
    rate_limit: int = 3,
    overhead_requests: int = 1,
) -> dict[str, float]:
    requests_per_item = 3 if use_statistics else 2
    total_requests = item_count * requests_per_item + overhead_requests
    seconds = total_requests / rate_limit
    return {
        "item_count": item_count,
        "requests_per_item": requests_per_item,
        "total_requests": total_requests,
        "rate_limit": rate_limit,
        "seconds": seconds,
        "minutes": round(seconds / 60, 1),
    }


def process_slug_batch(
    slugs: list[str],
    top_n_by: str = "market_demand_index",
    max_output: int = 200,
    tradable_only: bool = True,
    use_statistics: bool = True,
    overframe_budget: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    url_to_name, all_items = build_url_name_to_item_name_map()
    rows: list[dict] = []
    budget = [overframe_budget]
    total_items = len(slugs)

    for idx, url_name in enumerate(slugs, start=1):
        if progress_callback:
            progress_callback(idx - 1, total_items)

        item_name = resolve_item_name(url_name, url_to_name, all_items)
        if not item_name:
            log.warning("Nie znaleziono '%s' na warframe.market - pomijam", url_name)
            continue
        try:
            item_data = process_item(
                url_name,
                item_name,
                budget,
                use_statistics=use_statistics,
                tradable_only=tradable_only,
            )
            if item_data:
                rows.append(item_data)
        except Exception:
            log.exception("Błąd przy przetwarzaniu %s - pomijam", url_name)

    if progress_callback:
        progress_callback(total_items, total_items)

    rows = compute_demand_scores(rows)
    if top_n_by in {"estimated_grind_yield", "market_demand_index", "buy_orders_count", "sell_orders_count"}:
        metric = top_n_by
    else:
        metric = "market_demand_index"
    rows.sort(key=lambda row: row.get(metric) or 0, reverse=True)
    if max_output and len(rows) > max_output:
        rows = rows[:max_output]

    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    return rows


def main() -> None:
    url_to_name, all_items = build_url_name_to_item_name_map()

    rows = []
    overframe_budget = [OVERFRAME_MAX_ITEMS_PER_RUN]
    if USE_ALL_MARKET_ITEMS:
        slugs = [item["slug"] for item in all_items]
        if ALL_MARKET_ITEMS_LIMIT > 0:
            slugs = slugs[:ALL_MARKET_ITEMS_LIMIT]
        log.info("Przetwarzam %d itemów z całego warframe.market...", len(slugs))
    else:
        slugs = WATCHLIST

    for url_name in slugs:
        item_name = url_to_name.get(url_name)
        if not item_name:
            item_name = market.find_matching_item_name(url_name, all_items)
            if item_name:
                log.warning("Nie znaleziono slug '%s' bezpośrednio na warframe.market; używam dopasowanej nazwy: %s", url_name, item_name)
            else:
                log.warning("Nie znaleziono '%s' na warframe.market - pomijam", url_name)
                continue

        try:
            item_data = process_item(url_name, item_name, overframe_budget)
            if item_data:
                rows.append(item_data)
        except Exception:
            log.exception("Błąd przy przetwarzaniu %s - pomijam", url_name)

    if not rows:
        log.error("Brak jakichkolwiek danych do zapisania - sprawdź WATCHLIST i połączenie sieciowe.")
        sys.exit(1)

    rows = compute_demand_scores(rows)
    if MAX_ITEMS_OUTPUT and len(rows) > MAX_ITEMS_OUTPUT:
        metric = TOP_N_BY if TOP_N_BY in {"estimated_grind_yield", "market_demand_index", "buy_orders_count", "sell_orders_count"} else "market_demand_index"
        rows.sort(key=lambda row: row.get(metric) or 0, reverse=True)
        rows = rows[:MAX_ITEMS_OUTPUT]

    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    log.info("Zapisuję %d itemów do %s", len(rows), OUTPUT_XLSX)
    metric_label = {
        "market_demand_index": "Market Demand Index",
        "estimated_grind_yield": "Estimated Grind Yield",
        "buy_orders_count": "Buy Orders Count",
        "sell_orders_count": "Sell Orders Count",
    }.get(TOP_N_BY, "Market Demand Index")
    build_workbook(rows, OUTPUT_XLSX, report_name=f"Demand Tracker - {metric_label}")
    save_scan_cache(rows, SCAN_CACHE_JSON)
    log.info("Zapisano cache skanu do %s", SCAN_CACHE_JSON)
    log.info("Gotowe: %s", OUTPUT_XLSX)
    log.info("WAŻNE: otwórz plik w Excelu / LibreOffice i pozwól przeliczyć formuły (Ctrl+Shift+F9),")
    log.info("openpyxl nie liczy formuł - kolumna Market Demand Index pokaże wartość dopiero po przeliczeniu.")


if __name__ == "__main__":
    main()
