# Warframe Demand Tracker
 
Narzędzie do analizy popytu rynkowego w Warframe. Skanuje dane z **warframe.market**
i wzbogaca je o dane z **WFCD warframe-items**, generując arkusz Excel z rankingiem
przedmiotów wg płynności rynkowej, cen, liczby ofert i sposobu zdobycia.
 
Dostępne w dwóch trybach:
- **CLI** (`main.py`) — pełny skan uruchamiany z linii poleceń
- **Web UI** (`webapp.py`) — lokalny interfejs przeglądarkowy z podglądem postępu i wyborem itemów
---
 
## Spis treści
 
- [Wymagania](#wymagania)
- [Szybki start](#szybki-start)
- [Tryb CLI](#tryb-cli)
- [Tryb Web UI](#tryb-web-ui)
- [Konfiguracja (`config.py`)](#konfiguracja-configpy)
- [Market Demand Index — jak liczony](#market-demand-index--jak-liczony)
- [Źródła danych](#źródła-danych)
- [Struktura projektu](#struktura-projektu)
- [Budowanie pliku .exe](#budowanie-pliku-exe)
- [Automatyczne odświeżanie](#automatyczne-odświeżanie)
- [Znane ograniczenia](#znane-ograniczenia)
- [Rozwiązywanie problemów](#rozwiązywanie-problemów)
---
 
## Wymagania
 
- **Python 3.10+** (Windows — sprawdzone; Linux/Mac powinny działać, ale skrypty `.bat` są Windows-only)
- Połączenie z internetem (warframe.market API + WFCD GitHub)
Zależności instalowane automatycznie z `requirements.txt`:
 
| Pakiet | Zastosowanie |
|---|---|
| `requests` | komunikacja z API |
| `pandas` | przetwarzanie danych |
| `openpyxl` | generowanie plików `.xlsx` |
| `beautifulsoup4` | parsowanie (Overframe, eksperymentalne) |
| `flask` | interfejs webowy |
 
---
 
## Szybki start
 
Najprostsza ścieżka dla początkującego:
 
```
start_here.bat
```
 
Skrypt automatycznie:
1. sprawdza obecność Pythona,
2. tworzy wirtualne środowisko `.venv` (jeśli nie istnieje),
3. instaluje zależności z `requirements.txt`,
4. uruchamia **interfejs webowy** pod adresem `http://localhost:8000` i otwiera go w przeglądarce.
Serwer działa dopóki nie zamkniesz okna konsoli.
 
---
 
## Tryb CLI
 
Pełny skan bez interfejsu graficznego:
 
```bash
python main.py
```
 
Wynik trafia do `output/warframe_demand_tracker.xlsx`.
 
> **Ważne:** openpyxl zapisuje formuły Excela bez wyliczonych wartości. Po otwarciu
> pliku naciśnij **Ctrl+Shift+F9** (lub Dane → Przelicz), żeby kolumna
> *Market Demand Index* pokazała rzeczywiste wartości.
 
CLI używa ustawień z `config.py` (patrz niżej) — m.in. czy skanować całą listę
przedmiotów z warframe.market, czy tylko `WATCHLIST`.
 
---
 
## Tryb Web UI
 
```bash
python webapp.py
```
 
Otwórz `http://localhost:8000`. Interfejs pozwala:
 
- wybrać przedmioty z gotowych presetów (Zasoby, Prime Sets, Primed Mods, Arcana...),
- zbudować własną listę przedmiotów do skanu,
- śledzić postęp skanu w czasie rzeczywistym (pasek postępu, ETA),
- podejrzeć top wyniki bezpośrednio w przeglądarce,
- pobrać wygenerowany plik `.xlsx`.
> Interfejs wymaga folderu `templates/` z plikami `index.html` i `instructions.html`
> wewnątrz `wf_tracker/`. Jeśli go brakuje, `webapp.py` zwróci błąd renderowania strony.
 
---
 
## Konfiguracja (`config.py`)
 
Wszystkie ustawienia projektu edytuje się w jednym miejscu — reszta kodu nie wymaga zmian.
 
| Ustawienie | Opis |
|---|---|
| `WATCHLIST` | Lista slugów przedmiotów do śledzenia (używana, gdy `USE_ALL_MARKET_ITEMS = False`) |
| `USE_ALL_MARKET_ITEMS` | `True` = ignoruje `WATCHLIST`, skanuje cały rynek |
| `ALL_MARKET_ITEMS_LIMIT` | Opcjonalny limit liczby itemów przy pełnym skanie (`0` = brak limitu) |
| `TRADABLE_ONLY` | `True` = pomija przedmioty niehandlowalne |
| `MAX_ITEMS_OUTPUT` | Maksymalna liczba wierszy w wynikowym arkuszu (`0` = bez limitu) |
| `TOP_N_BY` | Metryka sortowania: `"market_demand_index"` lub `"estimated_grind_yield"` |
| `MARKET_DEMAND_WEIGHTS` | Domyślne wagi indeksu popytu (sprzedaż / cena / oferty kupna) |
| `OVERFRAME_ENABLED` | Eksperymentalny sygnał użycia w buildach z overframe.gg (domyślnie `False`) |
| `WFCD_CACHE_TTL_HOURS` | Czas ważności lokalnego cache danych WFCD (domyślnie 24h) |
 
Slug przedmiotu znajdziesz w adresie URL na warframe.market, np.
`https://warframe.market/items/orokin_cell` → `orokin_cell`.
 
---
 
## Market Demand Index — jak liczony
 
To **formuła Excela**, nie gotowa liczba z Pythona — dzięki temu można zmieniać wagi
bezpośrednio w arkuszu bez ponownego uruchamiania skryptu.
 
```
Market Demand Index = norm(Sales Count) × w1 + norm(Avg Sell Price) × w2 + norm(Buy Orders) × w3
```
 
- Normalizacja logarytmiczna, liczona **w obrębie danego skanu** (nie względem całej gry).
- Wagi (`w1`, `w2`, `w3`) znajdują się w żółtych, edytowalnych komórkach `Q2:Q4` arkusza.
- Po zmianie wag naciśnij `Ctrl+Shift+F9`, aby przeliczyć ranking.
- Domyślne wagi: Sales Count `0.50`, Avg Sell Price `0.30`, Buy Orders `0.20`.
Kolor komórek w arkuszu:
- **Niebieski tekst** — dane wejściowe (nadpisywane przy każdym skanie)
- **Czarny tekst** — formuła Excela
- **Żółte tło** — wartości do edycji ręcznej (wagi)
---
 
## Źródła danych
 
| Dane | Źródło | Status |
|---|---|---|
| Ceny, liczba ofert kupna/sprzedaży | warframe.market API v2 | Zgodne z dokumentacją API |
| Wolumen 48h / 90d | warframe.market `/v1/statistics` | Best-effort — brak danych nie przerywa skanu |
| Kategoria, komponenty craftingu, notatka o zdobyciu | WFCD `warframe-items` (GitHub, MIT) | Sprawdzone, stabilne |
| Relikty dla części Prime | WFCD `warframe-drop-data` (GitHub) | Sprawdzone, stabilne |
| Użycie w buildach ("Overframe Usage") | overframe.gg (scraping, brak oficjalnego API) | Eksperymentalne, wyłączone domyślnie |
 
---
 
## Struktura projektu
 
```
wf_tracker/
├── start_here.bat          # uruchomienie web UI dla początkujących
├── main.py                 # orchestrator trybu CLI
├── webapp.py                # serwer Flask (interfejs webowy)
├── config.py                # ustawienia projektu
├── demand.py                 # alternatywna, czysto-Pythonowa metoda liczenia indeksu
├── build_excel.py            # generowanie pliku .xlsx (openpyxl)
├── build_exe.bat             # budowanie pliku .exe (PyInstaller)
├── requirements.txt
├── sources/
│   ├── market.py             # warframe.market API
│   ├── items_db.py            # WFCD warframe-items
│   ├── relics.py               # WFCD warframe-drop-data
│   └── overframe.py            # eksperymentalny scraping overframe.gg
├── templates/                # szablony HTML dla web UI
├── scripts/
│   └── selftest_wfcd.py       # test warstwy WFCD bez odpytywania rynku
├── cache/                    # cache danych WFCD (TTL 24h)
└── output/
    ├── warframe_demand_tracker.xlsx
    └── warframe_demand_tracker_cache.json
```
 
---
 
## Budowanie pliku .exe
 
```
build_exe.bat
```
 
Wynikowy plik pojawi się w `dist\wf_tracker.exe`. Warto zbudować go dopiero po
ostatecznym skonfigurowaniu `config.py`, ponieważ ustawienia zostają zapisane
wewnątrz pliku wykonywalnego.
 
---
 
## Automatyczne odświeżanie
 
**Windows — Harmonogram zadań:**
1. Utwórz nowe zadanie → Akcja: *Uruchom program*
2. Program: `C:\ścieżka\do\python.exe`
3. Argumenty: `main.py`
4. Katalog startowy: `C:\ścieżka\do\wf_tracker`
5. Wyzwalacz: np. codziennie o 8:00
**Linux/Mac (cron):**
```
0 8 * * * cd /ścieżka/do/wf_tracker && /usr/bin/python3 main.py >> run.log 2>&1
```
 
> Plik `.xlsx` jest nadpisywany przy każdym uruchomieniu — jeśli trzymasz go
> otwarty w Excelu w momencie odpalenia skryptu, zapis się nie powiedzie.
 
---
 
## Znane ograniczenia
 
- **Rate limit warframe.market: 3 req/s.** Pełny skan całego rynku (`USE_ALL_MARKET_ITEMS = True`)
  może trwać znacząco dłużej niż skan wybranej `WATCHLIST`.
- **Overframe (`sources/overframe.py`) jest eksperymentalny.** Brak oficjalnego API — parsuje
  niedokumentowaną strukturę HTML, która może się zmienić bez ostrzeżenia.
- **Relikty pokrywają tylko część przedmiotów Prime.** Dla pozostałych (mody, arkana, riveny)
  `acquisition_note` opiera się na opisie z WFCD.
- **Starsze slugi mogą nie istnieć w API v2** (np. niektóre zasoby wycofane z gry) — takie
  pozycje zostają pominięte z ostrzeżeniem w logu.
---
 
## Rozwiązywanie problemów
 
| Objaw | Przyczyna / rozwiązanie |
|---|---|
| Kolumna Market Demand Index pusta lub `0` | Nie przeliczono formuł — naciśnij `Ctrl+Shift+F9` w Excelu |
| `Nie znaleziono katalogu aplikacji` przy `start_here.bat` | Skrypt nie znajduje się w folderze `wf_tracker` obok `main.py` |
| Błąd renderowania strony w web UI | Brak folderu `templates/` z plikami `index.html` / `instructions.html` |
| `Nie znaleziono 'X' na warframe.market` w logu | Nieaktualny slug — sprawdź aktualny adres URL przedmiotu na warframe.market |
| Zapis pliku `.xlsx` się nie powiódł | Plik jest otwarty w Excelu — zamknij go przed ponownym uruchomieniem skanu |
| Skan trwa bardzo długo | `USE_ALL_MARKET_ITEMS = True` skanuje cały rynek — ogranicz `WATCHLIST` lub ustaw `ALL_MARKET_ITEMS_LIMIT` |
 
---
 
## Licencja
 
Patrz plik `LICENSE`.
