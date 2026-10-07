# Styl raportu PDF

## Zakres analizy

Źródło tylko do odczytu: `przykładowy raport/Raport_Pomiarowy_Szablon_v1.docx`. Sprawdzono strukturę OOXML, style, tabele, podpisy, nagłówek i stopkę oraz obrazy osadzone w dokumencie. Nie kopiowano danych klienta, wyników, autorów ani wniosków do zasobów aplikacji. Zastosowano procedurę odczytu umiejętności documents.

Nie potwierdzono wyglądu każdej strony DOCX: środowisko do renderowania nie ma dostępnego pakietowego `soffice.exe`. Nie instalowano renderera i nie uruchamiano desktopowego LibreOffice. Informacje o układzie wynikają z XML, a informacje o obrazach z ich oględzin. Nie należy deklarować zgodności stron 1:1 ze wzorcem.

## Rozpoznany styl

| Element | Wzorzec |
|---|---|
| Strona | A4 pionowo, 210 × 297 mm |
| Marginesy | 25 mm z każdej strony; nagłówek i stopka 12,5 mm od brzegu |
| Pole treści | około 160 × 247 mm |
| Krój | motyw Calibri / Calibri Light; bezpośrednio także Segoe UI w tabelach i Cambria Math we wzorach |
| Tekst | przeważnie 11 pt, czarny; styl Body Text ma 12 pt, często nadpisywane bezpośrednio |
| Tytuł | wyśrodkowany, pogrubiony, 18 pt; styl definiuje Arial, fragmenty używają fontu motywu |
| Nagłówki | czarne, pogrubione, około 12 pt, numeracja sekcji i podsekcji |
| Podpisy | wyśrodkowane, zwykle 9 pt, oddzielna numeracja wykresów i tabel |
| Tabele | białe komórki i szare nagłówki `#E0E0E0`; miejscami `#BFBFBF` i `#F8F8F8`; tabele informacyjne z czarną siatką 0,5 pt |
| Tabela statystyk | cztery kolumny: kanał, Min, Średnia, Max |
| Wykresy | białe pole, delikatna szara siatka; kolorowe serie fazowe; szerokie wykresy czasowe |
| Nagłówek / stopka | data po prawej w nagłówku, numer strony wyśrodkowany w stopce |

Logo potwierdzone wzrokowo: `word/media/image1.png`, 735 × 314 px. Dokładna kopia wyłącznie tego obrazu: `assets/lopi-logo.png`. Logo zawiera znak granatowo-czerwony i napis LOPI. Pozostałe obrazy są wynikami starych badań i nie są zasobami aplikacji.

## Struktura wzorca

1. Dane wykonawcy, logo, tytuł i numer raportu, obiekt, adres.
2. Wstęp: cel, okres pomiarów, osoby, odniesienia i metody.
3. Wyniki: napięcia, prądy, moce, odkształcenia, harmoniczne, tgφ, zdarzenia.
4. Ocena normatywna ze starego badania.
5. Wnioski autora.

Struktura opisuje źródło i nie nakazuje odtwarzać nieudokumentowanej oceny normatywnej ani brakujących pomiarów.

## Proponowany skład ReportLab

- A4, margines 25 mm. Logo na pierwszej stronie, szerokość około 48 mm przy zachowaniu proporcji. Czarne nagłówki i szare tabele zachowują techniczny charakter wzorca.
- Font osadzony z obsługą polskich znaków. Można korzystać z fontu dostarczanego legalnie z aplikacją (np. DejaVu Sans z informacją licencyjną). To świadome przybliżenie Calibri. Nie kopiować fontów Windows do dystrybucji bez sprawdzenia uprawnień.
- Tytuł 18 pt / 22 pt interlinii, tekst 10,5–11 pt / 14 pt, nagłówki 12–13 pt, podpisy i tabela co najmniej 9 pt. Podpisy stosować konsekwentnie.
- Pierwsza strona: tytuł, numer, nazwa obiektu, adres, autorzy, data raportu i okres pomiarów. Długie wartości zawijać. Nie wpisywać przykładowego klienta ani autora domyślnie.
- Opis pomiarów i wnioski pochodzą z pól użytkownika. Puste pole może mieć neutralny komunikat „Nie podano”; nie wypełniać go interpretacją automatyczną.
- Sekcja źródeł: pliki, okresy, liczba rekordów, kanały i jednostki, rozpoznane interwały oraz zastrzeżenia o brakach/flagach. Dane te wynikają z importu.
- Następnie kolejne sekcje kanałów: nagłówek, duży wykres około 160 × 85 mm, podpis i tabela statystyczna. Grupować tylko kanały o zgodnych jednostkach i semantyce. Długie nazwy zawijać w tabelach i legendach.
- Tabele: `repeatRows=1`, dynamiczna wysokość wierszy, padding 5–6 pt, siatka szara 0,5 pt, nagłówek `#E0E0E0`. Nazwy wyrównać w lewo, liczby konsekwentnie w prawo. Szerokości dopasować do znaczenia kolumn.
- `KeepTogether` stosować do wykresu i podpisu, nie do całej dowolnie długiej sekcji. Zapewnić co najmniej nagłówek z następnym elementem. Umożliwić rozdzielenie długich tabel na strony.
- Numer strony generować automatycznie. Data raportu musi być polem projektu; nie używać ruchomego pola TIME zmieniającego historyczny dokument przy otwarciu.
- Wykresy generować z nowych danych, z osiami opisanymi jednostkami oraz legendą czytelną przy rzeczywistym rozmiarze PDF. Minimalna wielkość etykiet 9 pt. Oś czasu powinna pokazywać daty i godziny odpowiednio do okresu.
- Maksymalnie kilka serii na wykresie. Fazy: spójna paleta czerwony, zielony, niebieski; pomocniczo styl linii dla wydruku w szarości. Brakujące dane przerywają przebieg.
- Jeśli redukcja punktów jest potrzebna, zachować ekstrema i opisać redukcję. Statystyki zawsze z pełnych danych; braki nigdy nie są zerami.
- Raport nie ocenia automatycznie zgodności z normą i nie zawiera starych wykresów zgodności. Sekcja zdarzeń powstaje wyłącznie z prawidłowo odczytanych danych zdarzeniowych.

## Błędy i ryzyka źródła do wyeliminowania

- Numeracja jest nieciągła: wykresy przechodzą z 16 do 22 i z 23 do 25, tabele z 10 do 12, a następnie do 18. Nowe numery wyliczać w kolejności faktycznie wstawianych elementów.
- Tabela 9 jest podpisana ogólnie jako moc bierna, mimo sekcji mocy dystorsji. Tytuł generować z metadanych kanałów.
- Ponowny odczyt źródła 2026-10-05 potwierdził wypełnione tabele Min/Średnia/Max; występują również puste wiersze dekoracyjne. Wcześniejsza uwaga o licznych pustych komórkach wynikowych nie opisuje obecnej wersji Worda. W nowym PDF pokazywać wartości lub jednoznaczny brak danych.
- Obrazy wykresów zawierają drobne etykiety interfejsu WinPQ. Nie zmniejszać gotowego zrzutu ekranu: wykresy rysować od nowa z docelową wielkością tekstu.
- Nie przenosić wniosków o kompensacji mocy ze starego obiektu.
- Nie utożsamiać minimum i maksimum szeregu średnich interwałowych z ekstremami półokresowymi urządzenia.
- Nie zmieniać THD(A) na THDI [%]. Nazwa i jednostka z potwierdzonego eksportu są nadrzędne wobec podpisu we wzorcu.
- Nie przenosić liczb zdarzeń, granic normatywnych, dawnego czasu agregacji ani modelu analizatora jako domyślnych faktów nowych pomiarów.

## Kontrola gotowego PDF

Każda strona próbnego PDF wymaga renderu i oględzin: polskie znaki, podpisy, brak ucięcia tekstu, tabele między stronami, podpisy osi i legenda, długie dane użytkownika. Sprawdzić także pusty opis, długie wnioski, brak kanałów oraz import zawierający luki. Raport bez danych nie może sugerować kompletności badań. Ograniczenia niepotwierdzonego odczytu należy komunikować użytkownikowi w aplikacji.

## Wdrożony skład z 2026-10-05

Generator używa ReportLab BaseDocTemplate z polem treści 160 mm bez dodatkowych
wewnętrznych marginesów ramki. Okładka ma logo wyrównane do lewej, tytuł 23 pt
i tabelę danych zlecenia. Dalej znajdują się automatyczny spis treści i zakładki
PDF, Wstęp, Wyniki pomiarów, Wnioski autora i załącznik techniczny z pełnymi
ostrzeżeniami importu. We Wstępie pozostaje jawny zakres ograniczeń i odsyłacz.

Grupy są prezentowane w kolejności U średnie/max/min, I średnie/max/min,
P, Q, D, S (jeśli dostępna), THD, tgφ, częstotliwość i pozostałe kanały.
Sortowanie nie zmienia danych ani obliczeń. Wykresy mają około 118 mm wysokości,
a podwójny wykres tgφ około 133 mm. Tabele mają wyrównane do prawej liczby,
szare pogrubione nagłówki i delikatne naprzemienne tło. Kolumna jednostki ma
22 mm, aby nagłówek mieścił się w całości. Tekst autora dzieli się na akapity
i nie zostawia pojedynczych wierszy na granicy strony.

Wyniki Min/Średnia/Max są prezentowane z dokładnie dwoma miejscami po przecinku
po przeliczeniu jednostki, również z końcowymi zerami. Wartość zaokrąglona do
zera nie ma znaku minus. Liczby próbek pozostają całkowite; dane źródłowe,
eksport CSV i obliczenia zachowują pełną dokładność.

Sprawdzono 18-stronicowy raport z rzeczywistych 41 kanałów oraz 9-stronicowy
przypadek z długim tytułem, opisem, wnioskami i brakującymi wartościami.
Wszystkie 31 testów projektu przeszło. Spis treści odpowiada rzeczywistym
stronom. Zmiana dotyczy składu; nie dodaje widm ani oceny normatywnej.

## Aktualizacja z 2026-10-07 — wykresy total i szerokość

Na prośbę użytkownika marginesy boczne zmniejszono z 25 do 15 mm.
Wykresy, tabele i nagłówek wykorzystują 180 mm szerokości. Figury są
renderowane w nowej szerokości przy zachowanej wysokości i wielkości czcionek.
Marginesy górny i dolny pozostają po 25 mm.

Ptotal, Qtotal, Dtotal oraz zbiorczy tg_(fi) (również z końcowym podkreśleniem)
mają osobne strony z wykresami i tabelami, bezpośrednio po kanałach fazowych
danej wielkości. W obu grupach tgφ pozostaje pełny zakres i opisane
powiększenie P1–P99, liczone dla serii na danym wykresie. Statystyki,
wartości źródłowe, flagi i jednostki pozostają bez zmian.

Weryfikacja: 45 testów, test generowania PDF gotowym EXE oraz render
wszystkich 22 stron raportu próbnego. Wykresy total są na osobnych stronach,
a tabele i spis treści zachowują poprawny podział. Wyniki nadal wymagają
uzupełnienia metadanych i wniosków przez autora; nie powstała ocena normatywna.
Aktualny build: `dist/wide-charts/LOPI-PQ-Report.exe`, skopiowany także do
`dist/LOPI-PQ-Report.exe` i `dist/poprawka/LOPI-PQ-Report.exe`. Otwarty
`dist/pdf-fix/LOPI-PQ-Report.exe` pozostaje wcześniejszą wersją.
