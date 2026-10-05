# LOPI PQ Report Tool

Lokalna aplikacja Windows do generowania raportów PDF z pomiarów PQBox.
Nie używa AI, API, tokenów ani połączeń sieciowych. Wykresy, statystyki i PDF
powstają na komputerze. Word i WinPQ nie są wymagane dla obsługiwanego profilu PQF.

## Uruchomienie

Uruchom `dist/LOPI-PQ-Report.exe`. Nie wymaga instalowania Pythona.

1. W **Pliki i pomiary** wskaż folder pomiaru PQBox oraz folder zapisu PDF.
2. Wczytaj pomiary. Folder może zawierać jeden podfolder pomiarowy; przy wielu
   pomiarach należy wskazać konkretny podfolder.
3. Sprawdź daty i ostrzeżenia. Dla udostępnionej sesji przesunięcie zegara wynosi
   **+2 godziny**. To jawne ustawienie, nie automatyczne rozpoznawanie strefy.
4. W **Dane raportu i wnioski** wpisz tytuł, numer, wykonawcę, obiekt, adres,
   autorów, analizator, opis i własne wnioski.
5. Wybierz kanały, potwierdź sprawdzenie dat dla PQF i naciśnij **Generuj PDF**.
   Nazwę pliku ustala użytkownik. Nadpisanie istniejącego PDF wymaga potwierdzenia.

### THD(A) i widma z CSV

Wczytaj pełny eksport przez **Wczytaj pomocniczy CSV…**. W zakładce **Kanały i PDF**
przycisk **Podstawowe + widma** wybiera podstawowe wyniki, THD(A) i obsługiwane
harmoniczne. **Tylko THD(A) i widma** tworzy krótsze opracowanie tych wielkości.
Wybierz statystykę słupków: **Średnia** (domyślna), **Maksimum** albo **Percentyl 95**.
Ustawienie zapisuje się w projekcie; stare projekty przyjmują średnią.

- THD(A) jest odrębnym przebiegiem w amperach; nie jest przeliczany z THDI [%].
- Widmo U: `H2_UL1`–`H50_UL1` i analogicznie L2/L3, jednostka `%` z CSV.
- Widmo I: `H2_I1`–`H50_I1` i analogicznie I2/I3/IN, jednostka `A`.
- Każdy słupek odpowiada wybranej statystyce jednego kanału z całego okresu;
  kolory oznaczają fazy. P95: interpolacja liniowa w pozycji `(n−1) × 0,95`.
- Pod wykresami znajdują się tabele wszystkich rzędów 2–50 z wynikami do dwóch
  miejsc po przecinku i liczbą ważnych próbek. Braki nie stają się zerami.
- Jednostki są sprawdzane; ujemne amplitudy harmonicznych odrzucają generowanie.
  Nie są stosowane limity normatywne ani skala „% limitu”.

Te funkcje wymagają odpowiednich kanałów CSV. Bezpośredni profil PQF nadal
obejmuje 41 kanałów bez widm i THD(A). Zaimportowany CSV zastępuje źródło danych;
aplikacja nie scala go automatycznie z folderem PQF.

**Zapisz projekt** zachowuje opisy, ścieżki i wybór kanałów w JSON. Po otwarciu
projektu ponownie wczytaj źródło. **Eksport danych CSV** zapisuje wszystkie
odczytane kanały do pliku UTF-8 ze średnikiem; braki pozostają puste.

## Zakres pierwszej wersji

- Bezpośredni odczyt dostarczonego profilu PQBox150 V4.708, interwał 60 s,
  określony układ rekordów i fingerprint konfiguracji `info.pqf`.
- 41 zweryfikowanych kanałów: fazowe napięcia i prądy oraz kanały min/max,
  THDU i THDI w %, moce czynne, bierne, dystorsji, tgφ oraz częstotliwość.
- Flagi jakości z `cyc.pqf` i `cyc2h.pqf`; wspólne flagi konserwatywnie wykluczają
  wszystkie kanały dla danego znacznika czasu.
- PDF A4 z logo LOPI i stylem inspirowanym dostarczonym Wordem, opisami,
  wykresami, tabelami minimum/średnia/maksimum oraz wnioskami autora.
- Uporządkowany skład raportu: strona tytułowa, automatyczny spis treści,
  rozdziały Wstęp / Wyniki / Wnioski i załącznik techniczny. Dłuższe uwagi
  o imporcie są oddzielone od głównej prezentacji wyników.
- Wykres tgφ: pełny zakres oraz opisane powiększenie P1–P99. Tabele zawsze
  obejmują cały poprawny zbiór. Wykresy nie łączą luk i nie redukują próbek.
- Import pierwszego bloku interwałów CSV z WinPQ. Dalsze bloki o innych
  interwałach nie są łączone; pominięcie jest opisane w raporcie.

## Ograniczenia

To pierwsza wersja zweryfikowana na jednej sesji, **nie uniwersalny dekoder
wszystkich plików PQBox**. Inny model, firmware, konfiguracja, nieznane flagi
lub układ rekordów są odrzucane. Fingerprint obejmuje cały payload `info.pqf`,
więc może odrzucić także nową sesję z pozornie podobnymi ustawieniami. To celowe,
dopóki nowy wariant nie zostanie porównany z eksportem producenta. Wówczas użyj CSV.

Czas PQF odczytano z empirycznie zweryfikowanego kodowania z epoką 1990-01-01
i jawnym przesunięciem użytkownika. Program nie wykrywa zmiany czasu letniego,
ustawień zegara analizatora ani przekładni niezweryfikowanych konfiguracji.

Wersja nie odtwarza pełnego zakresu Worda: **nie tworzy tabel/matrycy zdarzeń PQ
ani automatycznej oceny PN-EN 50160**. Te moduły wymagają osobnej walidacji.
Widma z CSV pokazują jawnie wybraną statystykę, bez przypisywania znaczenia
kolorom starego raportu. THDI w % nie jest zamieniane na THD(A). Wnioski nie są
kopiowane z raportu wzorcowego; wpisuje je użytkownik.

Średnia jest średnią arytmetyczną poprawnych próbek. Min/max to ekstrema danego
kanału; program nie nadaje im automatycznie znaczenia półokresowego. Brak nie
jest zerem. Kolumny CSV o zduplikowanych nazwach są pomijane, aby nie zgadywać
różnicy np. między energią narastającą i interwałową.

## Eksport CSV w WinPQ mobil

Wczytaj pomiar w WinPQ, wybierz **Dane → Export do CSV** i potrzebne kanały.
Zachowaj nagłówek, włącz **Z flagowaniem**, wyłącz **Wypełnij luki**, wybierz
**Z interwałem**. W aplikacji LOPI użyj jawnego przycisku importu CSV.
Tabulatory, średniki i polskie przecinki dziesiętne są obsługiwane.
Bez kolumny flag aplikacja pokazuje ostrzeżenie o braku potwierdzenia jakości.

Uzyskany lokalnie eksport źródłowy: `exports/20260924_all.csv`. Nie jest
dodawany do Git ani dołączany do EXE.

## Rozwój i budowanie

Python 3.12, Tkinter, ReportLab, Matplotlib, PyInstaller.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-build.txt
.venv/Scripts/python.exe -m unittest discover -s tests -v
./build.ps1 -Python .venv/Scripts/python.exe
```

Test pełnego porównania z pomiarami jest pomijany, jeśli materiałów prywatnych
nie ma lokalnie. Testy syntetyczne sprawdzają uszkodzone rekordy, flagi, czasy,
braki, parser CSV i walidację aplikacji.

Tryb CLI: `--input` (folder PQF lub CSV), `--output` (nowy PDF), `--metadata`
(JSON z polami raportu), `--time-offset 2`, opcjonalnie `--status-file` (wynik JSON).
CLI odmawia nadpisania istniejącego PDF.

Zasady: `AGENTS.md`. Analiza PQF: `docs/pqf-analysis.md`.
Styl raportu: `docs/report-style.md`. Źródła pozostają tylko do odczytu.
