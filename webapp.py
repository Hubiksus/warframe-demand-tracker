from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_file

from build_excel import build_workbook
from config import OUTPUT_XLSX, SCAN_CACHE_JSON, WATCHLIST
from main import estimate_run_time, load_scan_cache, process_slug_batch, save_scan_cache
from sources import items_db, market

PRESET_GROUPS = [
    {
        "id": "resources",
        "label": "Zasoby wysokiego popytu",
        "description": "Szybko obracane zasoby do craftingu i sprzedaży.",
        "slugs": ["orokin_cell", "neurodes", "tellurium", "netrine", "oxium", "morphics", "salvage", "gallium"],
    },
    {
        "id": "prime_sets",
        "label": "Prime oraz kompletne zestawy",
        "description": "Popularne komplety Prime oraz zestawy kolekcjonerskie.",
        "slugs": ["gara_prime_set", "wisp_prime_set", "ash_prime_set", "braton_prime_receiver", "dex_furis_prime_set", "ember_prime_set"],
    },
    {
        "id": "primed_mods",
        "label": "Primed Mods",
        "description": "Wybór modów Primed o wysokim popycie.",
        "slugs": ["primed_fury", "primed_chamber", "primed_pressure_point", "primed_flow", "primed_shred"],
    },
    {
        "id": "arcanes",
        "label": "Arcana i wyższe",
        "description": "Arcana oraz silne dodatki z rynku.",
        "slugs": ["arcane_energy_regen", "arcane_aura_brutal_accuracy", "arcane_aura_chilling_reload", "arcane_heartbeat", "arcane_energize"],
    },
    {
        "id": "trade_starters",
        "label": "Szybkie starty handlowe",
        "description": "Mieszanka itemów o dobrym obrocie i niskim ryzyku stagnacji.",
        "slugs": ["orokin_cell", "neurodes", "gara_prime_set", "ash_prime_set", "kuva", "oxium"],
    },
    {
        "id": "full_watchlist",
        "label": "Pełna WATCHLIST",
        "description": "Użyj całej listy monitorowanych itemów jako bazę do analizy.",
        "slugs": WATCHLIST,
    },
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("webapp")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

_cached_market_items: list[dict[str, Any]] | None = None
scan_state: dict[str, Any] = {
    "status": "idle",
    "processed": 0,
    "total": 0,
    "percent": 0.0,
    "eta_seconds": 0.0,
    "message": "Gotowe do skanu.",
    "finished": False,
    "error": None,
    "count": 0,
    "download_url": None,
    "download_name": None,
    "preview": [],
}
scan_thread: threading.Thread | None = None
scan_lock = threading.Lock()


def load_market_items() -> list[dict[str, Any]]:
    global _cached_market_items
    if _cached_market_items is None:
        log.info("Ładuję listę itemów z warframe.market...")
        all_items = market.get_all_items()
        _cached_market_items = []
        if not all_items:
            log.error("Nie udało się pobrać listy itemów z warframe.market.")
            return _cached_market_items

        for item in all_items:
            name = item.get("item_name", "")
            category = items_db.get_category(name) or ""
            name_lower = name.lower()
            lower_category = category.lower()
            _cached_market_items.append(
                {
                    "slug": item["slug"],
                    "item_name": name,
                    "category": category,
                    "prime_set": "prime set" in name_lower or item["slug"].endswith("_prime_set"),
                    "primed_mod": "primed" in name_lower and ("mod" in lower_category or "mod" in item["slug"]),
                    "arcane": "arcane" in name_lower or "arcane" in lower_category or item["slug"].endswith("_arcane"),
                    "resource": "resource" in lower_category or name_lower.endswith(" cell") or name_lower.endswith(" alloy"),
                    "prime": "prime" in name_lower,
                }
            )
    return _cached_market_items


@app.route("/")
def index() -> str:
    return render_template("index.html", watchlist=WATCHLIST, presets=PRESET_GROUPS)


@app.route("/instructions")
def instructions() -> str:
    return render_template("instructions.html")


@app.route("/api/items")
def api_items() -> Any:
    items = load_market_items()
    cache_data = load_scan_cache(SCAN_CACHE_JSON)
    top_demand_slugs = []
    if cache_data and isinstance(cache_data.get("rows"), list):
        cached_rows = cache_data["rows"]
        if cached_rows and isinstance(cached_rows[0], dict) and "market_demand_index" in cached_rows[0]:
            sorted_rows = sorted(cached_rows, key=lambda row: row.get("market_demand_index", 0), reverse=True)
        else:
            sorted_rows = sorted(
                cached_rows,
                key=lambda row: (
                    (row.get("volume_48h", 0) or 0)
                    + (row.get("buy_orders_count", 0) or 0)
                ),
                reverse=True,
            )
        top_demand_slugs = [row.get("slug") for row in sorted_rows if row.get("slug")][:200]

    presets = [
        {
            "id": "resources",
            "label": "Zasoby",
            "description": "Najbardziej płynne surowce i komponenty do craftingu.",
            "slugs": [item["slug"] for item in items if item["resource"]][:200],
        },
        {
            "id": "prime_sets",
            "label": "Prime Sets",
            "description": "Przedmioty typu Prime Set i kompletne zestawy.",
            "slugs": [item["slug"] for item in items if item["prime_set"]][:200],
        },
        {
            "id": "primed_mods",
            "label": "Primed Mods",
            "description": "Primed mody o silnym popycie.",
            "slugs": [item["slug"] for item in items if item["primed_mod"]][:200],
        },
        {
            "id": "arcanes",
            "label": "Arcanes",
            "description": "Arcana i ich warianty z rynku.",
            "slugs": [item["slug"] for item in items if item["arcane"]][:200],
        },
        {
            "id": "prime_components",
            "label": "Prime komponenty",
            "description": "Popularne komponenty Prime do craftingu i handlu.",
            "slugs": [item["slug"] for item in items if item["prime"] and "set" not in item["slug"]][:200],
        },
        {
            "id": "popular_resources",
            "label": "Popularne zasoby",
            "description": "Często używane surowce i komponenty, które szybko się sprzedają.",
            "slugs": [item["slug"] for item in items if item["resource"] and item["slug"] in ["orokin_cell", "neurodes", "tellurium", "oxium", "plastids"]][:200],
        },
        {
            "id": "pokemon_top_demand",
            "label": "Największy popyt",
            "description": "Top items z ostatniego pełnego skanu cache; wymaga wcześniejszego skanu.",
            "slugs": top_demand_slugs,
            "cache_based": True,
        },
    ]

    return jsonify(
        {
            "items": items,
            "watchlist": WATCHLIST,
            "presets": presets,
            "cache": {
                "exists": bool(cache_data),
                "created": cache_data.get("created") if cache_data else None,
                "count": len(cache_data["rows"]) if cache_data and isinstance(cache_data.get("rows"), list) else 0,
            },
        }
    )


@app.route("/api/progress")
def api_progress() -> Any:
    return jsonify(scan_state)


@app.route("/api/estimate", methods=["POST"])
def api_estimate() -> Any:
    payload = request.get_json(force=True)
    slugs = payload.get("slugs", []) or []
    use_statistics = bool(payload.get("use_statistics", True))
    rate_limit = int(payload.get("rate_limit", 3))
    estimate = estimate_run_time(
        item_count=len(slugs),
        use_statistics=use_statistics,
        rate_limit=rate_limit,
    )
    return jsonify(estimate)


@app.route("/api/run", methods=["POST"])
def api_run() -> Any:
    global scan_thread, scan_state
    payload = request.get_json(force=True)
    slugs = payload.get("slugs", []) or []
    top_n_by = payload.get("top_n_by", "market_demand_index")
    max_output = int(payload.get("max_output", 200))
    tradable_only = bool(payload.get("tradable_only", True))
    use_statistics = bool(payload.get("use_statistics", True))
    overframe_budget = int(payload.get("overframe_budget", 0))

    if not slugs:
        return jsonify({"error": "Brak wybranych itemów."}), 400

    with scan_lock:
        if scan_thread and scan_thread.is_alive():
            return jsonify({"error": "Skanowanie już trwa."}), 409

        scan_state.update({
            "status": "running",
            "processed": 0,
            "total": len(slugs),
            "percent": 0.0,
            "eta_seconds": 0.0,
            "message": "Skanowanie w toku...",
            "finished": False,
            "error": None,
            "count": 0,
            "download_url": None,
        })

        started_at = time.time()

        def progress_callback(processed: int, total: int) -> None:
            elapsed = time.time() - started_at
            remaining = max(total - processed, 0)
            rate = processed / elapsed if elapsed > 0 else 0.0
            eta = remaining / rate if rate > 0 else 0.0
            scan_state.update({
                "processed": processed,
                "total": total,
                "percent": round((processed / total) * 100, 1) if total else 100.0,
                "eta_seconds": round(eta, 1),
                "message": f"Przetworzono {processed}/{total} itemów.",
            })

        def background_scan() -> None:
            try:
                rows = process_slug_batch(
                    slugs=slugs,
                    top_n_by=top_n_by,
                    max_output=max_output,
                    tradable_only=tradable_only,
                    use_statistics=use_statistics,
                    overframe_budget=overframe_budget,
                    progress_callback=progress_callback,
                )
                report_name = "Estimated Grind Yield" if top_n_by == "estimated_grind_yield" else "Market Demand Index"
                build_workbook(rows, Path(OUTPUT_XLSX), report_name=f"Demand Tracker - {report_name}")
                if rows:
                    save_scan_cache(rows, SCAN_CACHE_JSON)
                scan_state.update({
                    "status": "finished",
                    "percent": 100.0,
                    "eta_seconds": 0.0,
                    "message": f"Zakończono skan. {len(rows)} itemów zapisano.",
                    "finished": True,
                    "count": len(rows),
                    "download_url": "/download/output.xlsx",
                    "download_name": f"warframe_demand_tracker_{report_name.replace(' ', '_').replace('/', '-')}.xlsx",
                    "preview": [
                        {
                            "rank": row["rank"],
                            "item_name": row["item_name"],
                            "category": row["category"],
                            "lowest_sell_price": row["lowest_sell_price"],
                            "avg_sell_price_top5": row["avg_sell_price_top5"],
                            "buy_orders_count": row["buy_orders_count"],
                            "sell_orders_count": row["sell_orders_count"],
                            "volume_48h": row["volume_48h"],
                            "volume_90d_avg": row["volume_90d_avg"],
                            "estimated_grind_yield": row.get("estimated_grind_yield"),
                        }
                        for row in rows[:25]
                    ],
                })
            except Exception as exc:
                log.exception("Błąd w tle skanowania")
                scan_state.update({
                    "status": "error",
                    "message": str(exc),
                    "finished": True,
                    "error": str(exc),
                    "download_url": None,
                    "download_name": None,
                    "count": 0,
                    "preview": [],
                })

        scan_thread = threading.Thread(target=background_scan, daemon=True)
        scan_thread.start()

    return jsonify({"started": True})


@app.route("/download/output.xlsx")
def download_output() -> Any:
    file_path = Path(OUTPUT_XLSX)
    if not file_path.exists():
        return jsonify({"error": "Plik wynikowy nie istnieje."}), 404
    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=scan_state.get("download_name") or file_path.name,
    )


@app.route("/api/build-cache", methods=["POST"])
def api_build_cache() -> Any:
    payload = request.get_json(force=True)
    top_n_by = payload.get("top_n_by", "market_demand_index")
    max_output = int(payload.get("max_output", 200))
    tradable_only = bool(payload.get("tradable_only", True))

    cache_data = load_scan_cache(SCAN_CACHE_JSON)
    if not cache_data or not isinstance(cache_data.get("rows"), list):
        return jsonify({"error": "Brak wcześniejszego pełnego skanu cache."}), 400

    rows = list(cache_data["rows"])
    if tradable_only:
        rows = [row for row in rows if row.get("tradable") is not False]

    valid_metrics = {"estimated_grind_yield", "market_demand_index", "buy_orders_count", "sell_orders_count"}
    if top_n_by not in valid_metrics:
        top_n_by = "market_demand_index"

    if top_n_by == "estimated_grind_yield":
        rows.sort(key=lambda row: row.get("estimated_grind_yield") or 0, reverse=True)
    else:
        if top_n_by == "market_demand_index":
            if not rows or "market_demand_index" not in rows[0]:
                from demand import compute_demand_scores
                rows = compute_demand_scores(rows)
        rows.sort(key=lambda row: row.get(top_n_by) or 0, reverse=True)

    if max_output and len(rows) > max_output:
        rows = rows[:max_output]

    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    report_name = "Estimated Grind Yield" if top_n_by == "estimated_grind_yield" else "Market Demand Index"
    build_workbook(rows, Path(OUTPUT_XLSX), report_name=f"Demand Tracker - {report_name}")
    return jsonify({"count": len(rows), "download_url": "/download/output.xlsx"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
