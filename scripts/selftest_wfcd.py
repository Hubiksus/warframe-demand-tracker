"""
Test modułu sources/items_db.py (WFCD warframe-items).
Ten moduł BYŁ przetestowany na żywo - raw.githubusercontent.com jest dostępny.

Uruchom z głównego katalogu projektu: python scripts/selftest_wfcd.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sources import items_db

TEST_ITEMS = ["Orokin Cell", "Neurodes", "Ash Prime Systems"]

for name in TEST_ITEMS:
    print(f"\n=== {name} ===")
    print("Category:", items_db.get_category(name))
    uses = items_db.get_crafting_uses(name)
    print(f"Crafting uses ({len(uses)}):", uses[:5], "..." if len(uses) > 5 else "")
    print("Acquisition note:", items_db.get_acquisition_note(name)[:200])
