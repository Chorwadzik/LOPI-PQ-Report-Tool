# LOPI PQ Report Tool

Lokalna aplikacja Windows do generowania raportów PDF z pomiarów PQBox i eksportów CSV Sonel.
Nie używa AI, API, tokenów ani połączeń sieciowych. Wykresy, statystyki i PDF
powstają na komputerze. Word i WinPQ nie są wymagane dla obsługiwanego profilu PQF.

## Uruchomienie

Uruchom `dist/LOPI-PQ-Report-v1.3.exe`. Nie wymaga instalowania Pythona.

Numer bieżącego wydania jest w `VERSION`, a opis zmian w `CHANGELOG.md`.
W `dist` pozostaje jeden aktualny EXE. Budowanie najpierw tworzy i sprawdza
nowe wydanie w katalogu roboczym, a następnie przenosi poprzedni EXE do
`dist/Kontrola funkcji/<poprzednia nazwa>/<data archiwizacji>/`.
Przed kolejnym wydaniem zwiększamy numer stosownie do zmian: poprawki
np. v1.1.1, rozszerzenia v1.2, duże zmiany v2.0.

1. W **Pliki i pomiary** wskaż folder pomiaru PQBox oraz folder zapisu PDF.
2. Wczytaj pomiary. Folder może zawierać jeden podfolder pomiarowy; przy wielu
   pomiarach należy wskazać konkretny podfolder.
3. Sprawdź daty i ostrzeżenia. Dla udostępnionej sesji przesunięcie zegara wynosi
   **+2 godziny**. To jawne ustawienie, nie automatyczne rozpoznawanie strefy.
4. W **Dane raportu i wnioski** wpisz tytuł, numer, wykonawcę, obiekt, adres,
   autorów, analizator, opis i własne wnioski.
5. W zakładce **Kanały i PDF** porównaj wyświetlony na górze okres z WinPQ
   i zaznacz **Sprawdzono daty i zakres pomiaru w WinPQ** (wymagane dla PQF).
   Wybierz kanały i naciśnij **Generuj PDF**. Potwierdzenie jest zerowane
   po zmianie źródła, przesunięcia czasu lub ponownym wczytaniu danych.
   Nazwę pliku ustala użytkownik. Nadpisanie istniejącego PDF wymaga potwierdzenia.

### Sonel CSV

Wybierz **Wczytaj CSV (Sonel / WinPQ)…** i wskaż eksport tabeli pomiarów.
Program sam rozpozna format i wybierze podstawowe kanały. Potem uzupełnij
dane raportu, wskaż folder wynikowy i naciśnij **Generuj PDF**.
W Sonel Analysis użyj **Pomiary → zaznacz całą tabelę → Raporty → Raport CSV**,
z nagłówkami i flagami, bez dzielenia pliku. Natywne `.pqm710` wymagają tego eksportu.

Import Sonel obejmuje podstawowe wielkości przy najkrótszej agregacji,
zachowuje czas UTC z pliku, jednostki, warianty mocy i osobne sumy Σ.
Harmoniczne, energie, flicker i inne agregacje są pomijane z ostrzeżeniem.
Od v1.3 domyślny raport pokazuje jeden tgφ na fazę oraz osobny tgφ dla Σ:
sumę wariantów L+, C−, L− i C+ z zachowaniem znaków. Brak składowej daje lukę.
Pierwotne warianty pozostają dostępne na liście kanałów.
Flaga G/Gf pozostawia dane z uwagą o synchronizacji czasu; pozostałe flagi
wykluczają wiersz. Szczegóły i ograniczenia: [Sonel CSV](docs/sonel-import.md).

### THD(A) i widma z CSV WinPQ

Wczytaj pełny eksport przez **Wczytaj CSV (Sonel / WinPQ)…**. W zakładce **Kanały i PDF**
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
- Ptotal, Qtotal, Dtotal oraz zbiorczy tgφ mają osobne wykresy i tabele,
  bezpośrednio po odpowiednich kanałach fazowych. Marginesy boczne wynoszą
  15 mm, a wykresy i tabele mają szerokość 180 mm.
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

### Poprawka dostępności potwierdzenia dat — 2026-10-07

Potwierdzenie i okres pomiaru są na górze zakładki **Kanały i PDF**.
Zakładka ma paski przewijania, a uwagi mają osobny pasek. Przy próbie
generowania niepotwierdzonego PQF widok wraca do potwierdzenia.
Sprawdzono 44 testy, w tym małe okna i skalę Tk 2.0; niezależna recenzja
potwierdziła dostępność listy i uwag. Nowy EXE uruchomiono samodzielnie
i zamknięto poprawnie (kod 0).

Gotowy plik tej poprawki: `dist/poprawka/LOPI-PQ-Report.exe`.
Dotychczasowy EXE był otwarty i zablokowany przez Windows, dlatego pozostał
bez podmiany. Przed przejściem do poprawionej wersji zapisz bieżący projekt.
Nie potwierdzano dat konkretnego pomiaru za użytkownika ani nie wykonywano
ponownej kontroli wizualnej PDF: zmiana dotyczy interfejsu. Kolejny krok:
otworzyć projekt w poprawionej wersji, wczytać pomiary i porównać daty z WinPQ.

### Uzupełnienie poprawki — zależności PDF

Poprzednia kontrola uruchomienia EXE nie wykryła brakującego ReportLab:
testy pomocniczych obliczeń nie uruchamiały całego generatora. Uzupełniono
środowisko z `requirements-build.txt`. `build.ps1` teraz przerywa budowanie,
jeśli brakuje zależności, i wymaga wygenerowania PDF przez gotowy EXE
na syntetycznym CSV z obcego katalogu roboczego (`tools/smoke_test_exe.py`).
Opcja `-DistPath` pozwala zbudować nową wersję, gdy stary EXE jest otwarty.

Sprawdzono 44 testy oraz generowanie PDF przez EXE na danych syntetycznych
i wskazanym przez użytkownika folderze PQF. Gotowy raport roboczy sprawdzono
wizualnie. Zaktualizowano EXE w `dist`, `dist/poprawka` i `dist/pdf-fix`;
wersje mają identyczne SHA256. Dane pomiarowe i wynikowe pozostają poza Git.
Metadane autora i wnioski nie były uzupełniane automatycznie. Próbne
generowanie potwierdza działanie techniczne, nie ocenę normatywną pomiaru.
