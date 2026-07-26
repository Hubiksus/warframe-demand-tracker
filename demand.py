"""
Liczy znormalizowany Market Demand Index (0-100) na podstawie sygnałów z warframe.market.
Normalizacja: logarytmiczna w obrębie batcha dla sprzedaży, ceny i ofert kupna.
Wagi ustawiasz w config.py -> MARKET_DEMAND_WEIGHTS.

Wynik mówi "jak ten item wypada na tle innych z Twojej WATCHLIST", a nie
"jak wypada na tle wszystkich itemów w grze". Jeśli chcesz porównywać do całej gry,
trzeba by pociągnąć dane dla wszystkich itemów z get_all_items() - technicznie możliwe,
ale to kilkaset/kilka tysięcy itemów x kilka requestów = długi run (patrz README).
"""

from __future__ import annotations

from math import log1p

from config import MARKET_DEMAND_WEIGHTS


def _log_normalize(values: list[float]) -> list[float]:
    transformed = [log1p(max(v, 0)) for v in values]
    if not transformed:
        return []
    max_val = max(transformed)
    if max_val <= 0:
        return [0.0 for _ in transformed]
    return [round(v / max_val * 100, 1) for v in transformed]


def _linear_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    max_val = max(values)
    if max_val <= 0:
        return [0.0 for _ in values]
    return [round(min(max(v, 0), max_val) / max_val * 100, 1) for v in values]


def _verify_extreme_market_demand_index(row: dict, score: float) -> float:
    """Dodatkowa weryfikacja dla skrajnie wysokich Market Demand Index."""
    if score <= 80:
        return score

    buy_orders = row.get("buy_orders_count", 0)
    sell_orders = row.get("sell_orders_count", 0)
    vol_48h = row.get("volume_48h", 0)
    vol_90d = row.get("volume_90d_avg", 0)
    price = row.get("avg_sell_price_top5") or row.get("lowest_sell_price") or 0

    low_volume = vol_48h < 3 and vol_90d < 1
    low_orders = buy_orders < 10 and sell_orders < 5
    low_price = price <= 1

    if low_volume and low_orders:
        return round(min(score, 80) * 0.75, 1)
    if low_volume and buy_orders < 5:
        return round(min(score, 85) * 0.85, 1)
    if low_price and score > 90:
        return round(90.0, 1)
    return score


def compute_demand_scores(rows: list[dict]) -> list[dict]:
    """
    rows: lista dictów zawierających co najmniej:
      buy_orders_count, avg_sell_price_top5, volume_48h, volume_90d_avg
    Dopisuje do każdego dicta klucz 'market_demand_index'.
    """
    if not rows:
        return rows

    sales = _log_normalize([r.get("sales_count", 0) for r in rows])
    avg_price = _log_normalize([r.get("avg_sell_price", 0) for r in rows])
    buy_orders = _log_normalize([r.get("buy_orders_count", 0) for r in rows])

    w = MARKET_DEMAND_WEIGHTS
    for i, row in enumerate(rows):
        score = (
            sales[i] * w["sales_count"]
            + avg_price[i] * w["avg_sell_price"]
            + buy_orders[i] * w["buy_orders"]
        )
        score = round(score, 1)
        row["market_demand_index"] = _verify_extreme_market_demand_index(row, score)

    return rows
