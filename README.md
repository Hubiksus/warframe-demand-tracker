# Warframe Demand Tracker

Automatyczny, cyklicznie aktualizowany arkusz Excel z popytem, cenami, ilością ofert
i notatką "jak zdobyć" dla wybranych itemów z Warframe.

## Co realnie działa i skąd biorą się dane

| Kolumna w Excelu | Źródło | Status |
|---|---|---|
| Ceny, liczba ofert kupna/sprzedaży | **warframe.market API v2** (`api.warframe.market/v2`) | Poprawione po realnym teście: v1 zostało wyłączone (`/v1/items` = 404), przepisane na `/v2/items` + `/v2/orders/item/{slug}`. **Items i Orders potwierdzone w dokumentacji**, ale nie odpalone na żywo w środowisku, w którym pisałem kod - pierwszy prawdziwy test to Twoje `python main.py`. |
| Wolumen 48h/90d | `/v1/statistics` (best-effort fallback) | **Niepewne** - v1 może być wyłączone też tutaj. Jeśli zwróci 404, kod tego nie traktuje jako błąd krytyczny - po prostu wolumen wyjdzie 0, a Market Demand Index liczy się z pozostałych sygnałów (sales_count, buy orders, avg sell price). |
| Kategoria, opis/lokalizacja dropu, komponenty craftingu ("Used In") | **WFCD/warframe-items** (GitHub, MIT) | **Przetestowane na żywo** podczas budowy tego projektu - działa. |
| Relikty dla części Prime | **WFCD/warframe-drop-data** (GitHub) | **Przetestowane na żywo** - działa, z poprawką na relikty Requiem (brak pola `relicName`). |
| "Overframe Usage" (użycie w buildach) | **overframe.gg** (scraping HTML, brak oficjalnego API) | **Eksperymentalne, wyłączone domyślnie** (`OVERFRAME_ENABLED = False` w `config.py`). Zobacz `sources/overframe.py` - struktura strony jest niedokumentowana i mogła się zmienić. |

**Dlaczego nie ma bezpośredniego scrapingu wiki.warframe.com?** Bo to Fandom wiki z prozą,
trudną do niezawodnego parsowania. Zamiast tego projekt używa WFCD/warframe-items i
WFCD/warframe-drop-data - community-maintained paczek danych zasilanych bezpośrednio
danymi z gry (Warframe Public Export), które *same* agregują to, co normalnie trzeba by
było wyciągać z wiki. Jest to stabilniejsze i ma jasną licencję (MIT).

## Instalacja

```bash
cd wf_tracker
pip install -r requirements.txt
```

## Pierwsze uruchomienie

1. Otwórz `config.py`, edytuj `WATCHLIST` lub przełącz na pełny skan rynku:
   - `USE_ALL_MARKET_ITEMS = True` powoduje ignorowanie `WATCHLIST` i ocenę wszystkich itemów z warframe.market.
   - Jeśli chcesz użyć `WATCHLIST`, pamiętaj, że starsze slugi (np. `orokin_cell`, `neurodes`, `tellurium`, `nitain_extract`) mogą już nie istnieć w aktualnej liście v2 i zostaną pominięte.
   - `TRADABLE_ONLY = True` filtruje wynik do itemów tradowalnych.
   - `MAX_ITEMS_OUTPUT = 200` ogranicza końcowy arkusz do 200 najlepszych pozycji.
   - `TOP_N_BY = "estimated_grind_yield"` pozwala wybierać top-N po metryce Grind Yield (plat/min) zamiast Market Demand Index.
2. `python scripts/selftest_wfcd.py` - szybki test warstwy WFCD (nie dotyka warframe.market/overframe)
3. `python main.py` - pełny run. Pierwsze uruchomienie ściągnie ~54MB danych WFCD
   do `cache/` (potem cache trzyma się `WFCD_CACHE_TTL_HOURS` godzin, domyślnie 24h)
4. Otwórz `output/warframe_demand_tracker.xlsx` w Excelu/LibreOffice i **przelicz formuły**
   (Ctrl+Shift+F9 lub Plik -> Przelicz) - openpyxl zapisuje formuły bez wartości,
   Market Demand Index pokaże się dopiero po przeliczeniu w prawdziwym Excelu

## Budowanie EXE na Windows

Jeśli chcesz zbudować plik `.exe`:

```bash
cd wf_tracker
.venv\Scripts\python.exe build_exe.bat
```

Po zakończeniu znajdziesz wygenerowany plik w katalogu `dist\wf_tracker.exe`.

W repo jest `output/sample_output_DEMO_DATA.xlsx` - wygenerowany z **wymyślonymi**
danymi rynkowymi (bo `api.warframe.market` jest zablokowane w środowisku, w którym
budowałem ten projekt), żeby pokazać format i sprawdzić, że formuły/kolory/warunkowe
formatowanie faktycznie działają. Kolumny "Used In (Crafting)" i "Acquisition Note"
w tym demo są prawdziwe (WFCD zostało realnie odpytane) - tylko ceny/wolumeny są fejkowe.

## Jak liczony jest Market Demand Index

To **formuła Excela**, nie gotowa liczba z Pythona - patrz kolumny J/K/F i wagi w
komórkach Q2:Q4 (żółte, edytowalne). Logarytmiczna normalizacja w obrębie Twojej WATCHLIST:

```
Market Demand Index = norm(Sales Count)*w1 + norm(Avg Sell Price)*w2 + norm(Buy Orders)*w3
```

Zmień wagi bezpośrednio w Excelu - indeks przeliczy się automatycznie po Ctrl+Shift+F9.
Domyślne wagi (`MARKET_DEMAND_WEIGHTS` w `config.py`): Sales Count 0.50, Avg Sell Price 0.30,
Buy Orders 0.20.

To normalizacja **względem itemów w Twojej watchliście**, nie względem całej gry.
Jeśli chcesz porównywać do wszystkich itemów w grze - technicznie możliwe (pociągnij
`market.get_all_items()` zamiast `WATCHLIST`), ale to setki/tysiące requestów x rate
limit 3/s = długi run (rzędu godzin). Nie zaimplementowane - to świadomy kompromis.

## GitHub Actions: cache dependencies and build artifacts

This repository includes a GitHub Actions workflow that caches Python dependencies
and uploads build artifacts produced by CI. The workflow file is at
`.github/workflows/ci.yml` and runs on pushes and PRs to `main`.

What is cached:
- pip cache (`~/.cache/pip`) keyed by `requirements.txt` hash — this speeds up
   repeated `pip install` runs across CI jobs.

What the workflow does:
- installs dependencies using `pip install -r requirements.txt` (uses the cache)
- on Windows runner it runs the included `build_exe.bat` to produce `dist\wf_tracker.exe`
- uploads `dist/` as a build artifact (per-run)

To enable CI on GitHub:
1. Commit and push this repository to GitHub (see earlier instructions).
2. Go to the repository on GitHub -> Actions and enable the workflow if prompted.
3. After a push the workflow will run and you can download the `dist` artifact
    from the workflow run's summary (if the Windows job produced it).

Notes:
- CI cannot produce a signed installer — the produced `.exe` is unsigned.
- If you want faster builds on CI, consider pinning dependency versions or using
   a pre-built wheelhouse and caching it with `actions/cache`.

## Automatyczne, cykliczne odświeżanie

**Windows Task Scheduler:**
1. Utwórz zadanie -> Akcja: Uruchom program
2. Program: `C:\ścieżka\do\python.exe`
3. Argumenty: `main.py`
4. Katalog startowy: `C:\ścieżka\do\wf_tracker`
5. Wyzwalacz: np. codziennie o 8:00

**Linux/Mac (cron):**
```
0 8 * * * cd /ścieżka/do/wf_tracker && /usr/bin/python3 main.py >> run.log 2>&1
```

Plik `.xlsx` jest nadpisywany przy każdym uruchomieniu - jeśli trzymasz go otwartego
w Excelu w momencie odpalenia skryptu, zapis się nie powiedzie (Windows blokuje plik).

## Ograniczenia i rzeczy do zweryfikowania samodzielnie

1. **`sources/market.py` nie był testowany na żywo.** Kontrakt API (`docs.warframe.market`)
   jest stosunkowo stabilny, ale endpoint `/statistics` czasem bywał przenoszony między
   wersjami API - jeśli dostaniesz błędy 404, sprawdź aktualną dokumentację.
2. **`sources/overframe.py` jest eksperymentalny i wyłączony domyślnie.** Nie ma
   oficjalnego API - parsuje niedokumentowany JSON osadzony w HTML. Zanim włączysz
   `OVERFRAME_ENABLED`, sprawdź `overframe.gg/robots.txt` i ToS
   (wearemoba.com/terms-of-service/), i zweryfikuj strukturę `__NEXT_DATA__` ręcznie
   (Ctrl+U na stronie itemu w przeglądarce).
3. **Relikty pokrywają tylko część Prime.** Zwykłe mody, arkany, riveny nie mają
   reliktów w tym samym sensie - dla nich `acquisition_note` spadnie do pola
   `description` z WFCD albo linku do wiki.
4. **Rate limiting warframe.market: 3 req/s.** Przy dużej WATCHLIST (>50 itemów) run
   może trwać kilka minut - to celowe, żeby nie oberwać banem/Cloudflare.

## Struktura projektu

```
wf_tracker/
├── config.py              # WATCHLIST, wagi, flagi - tu edytujesz
├── main.py                # orchestrator, uruchamiasz to
├── demand.py               # (nieużywane obecnie - logika przeniesiona do formuł Excela,
│                            #  zostawione jako alternatywna, czysto-Pythonowa metoda liczenia)
├── build_excel.py          # generowanie .xlsx (openpyxl, formuły, formatowanie)
├── sources/
│   ├── market.py           # warframe.market API v1
│   ├── items_db.py          # WFCD warframe-items (kategoria, crafting uses, opis)
│   ├── relics.py            # WFCD warframe-drop-data (relikty dla części Prime)
│   └── overframe.py         # EKSPERYMENTALNE - scraping overframe.gg
├── scripts/
│   └── selftest_wfcd.py    # test warstwy WFCD bez dotykania warframe.market/overframe
├── cache/                   # cache WFCD JSON (tworzone automatycznie, TTL 24h)
└── output/
    └── warframe_demand_tracker.xlsx
```
