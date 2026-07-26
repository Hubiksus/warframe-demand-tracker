"""
Konfiguracja projektu wf_tracker.
Edytuj WATCHLIST, wagi i flagi tutaj - reszta kodu nie wymaga zmian.
"""

from pathlib import Path

# --- Ścieżki ---
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_XLSX = OUTPUT_DIR / "warframe_demand_tracker.xlsx"
SCAN_CACHE_JSON = OUTPUT_DIR / "warframe_demand_tracker_cache.json"

# --- Lista śledzonych itemów (slug z warframe.market, tak jak w URL-u strony) ---
# Znajdziesz slug w adresie strony itemu na warframe.market,
# np. https://warframe.market/items/orokin_cell -> "orokin_cell"
# (v1 API nazywało to "url_name" - w v2 to pole "slug", wartość ta sama)
# Uwaga: niektóre starsze slugi zasobów mogą być już nieobecne w aktualnej liście v2.
# Możesz podać dużo itemów - liczy się głównie limit 3 req/s (patrz sources/market.py)
WATCHLIST = [
    "orokin_cell",
    "neurodes",
    "tellurium",
    "nitain_extract",
    "kuva",
    "gara_prime_set",
    "wisp_prime_set",
    "braton_prime_receiver",
    "ash_prime_set",
]

# --- Only tradable items in the output spreadsheet? ---
# True: skip untradable items from the generated Excel file.
# False: include all WATCHLIST items regardless of tradability.
TRADABLE_ONLY = True

# --- Scan entire warframe.market instead of WATCHLIST ---
# True: ignore WATCHLIST and evaluate every item available on warframe.market.
# False: use only the WATCHLIST slugs.
USE_ALL_MARKET_ITEMS = True

# --- Optional cap when scanning the full market ---
# 0 = no cap.
ALL_MARKET_ITEMS_LIMIT = 0

# --- Limit output to the top N items by the chosen output metric ---
# If > 0, the generated spreadsheet will include only the top N rows
# after the output metric is computed. Set to 0 to disable the limit.
MAX_ITEMS_OUTPUT = 200

# --- Metric for selecting the top N output rows ---
# "market_demand_index" = top items by market demand index
# "estimated_grind_yield" = top items by estimated grind yield (plat/min)
TOP_N_BY = "market_demand_index"

# --- Wagi do wyliczania Market Demand Index ---
MARKET_DEMAND_WEIGHTS = {
    "sales_count": 0.50,      # liczba sprzedanych sztuk (volume/volume statistics)
    "avg_sell_price": 0.30,   # średnia cena wpisów sprzedaży (top5 zleceń sell)
    "buy_orders": 0.20,       # liczba aktywnych ofert kupna (warframe.market)
}

# --- Overframe (eksperymentalne, wyłączone domyślnie - patrz README) ---
OVERFRAME_ENABLED = False
OVERFRAME_MAX_ITEMS_PER_RUN = 20   # ile itemów maks. skrobać w jednym uruchomieniu (rate-limit safety)
OVERFRAME_DELAY_SECONDS = 2.0      # opóźnienie między requestami do overframe.gg

# --- Cache (żeby nie ściągać kilkudziesięciu MB WFCD JSON za każdym razem) ---
WFCD_CACHE_TTL_HOURS = 24

# --- HTTP ---
USER_AGENT = "wf-demand-tracker/1.0 (personal project, contact: hubert)"
