# Analiza lokalnych plików PQF

Stan: 5 października 2026. Analiza tylko do odczytu. Pliki źródłowe nie były zmieniane.

## Wnioski

Można odczytać identyfikację urządzenia i strukturę kontenera. Po otrzymaniu pełnego eksportu WinPQ wdrożono ograniczony parser 41 kanałów w `lopi_report/pqf.py`. Wszystkie 11 283 próbki tych kanałów, jednostki, daty oraz obie flagi jakości porównano z eksportem. Nie jest to parser uniwersalny: obsługuje wyłącznie profil dostarczonej konfiguracji PQBox150 V4.708, interwał 60 s; przesunięcie zegara musi jawnie podać użytkownik. Profil dodatkowo wymaga zgodnego SHA256 całego payloadu info.pqf (bajty od 48 do końca). Inne konfiguracje są odrzucane, ponieważ nie zweryfikowano ich przekładni i skalowania.

Zweryfikowana droga eksportu to GUI WinPQ mobil: Dane / Eksport CSV. Nie znaleziono udokumentowanego CLI PQF → CSV. Brak wyniku wyszukiwania nie dowodzi, że interfejs taki nie istnieje. Dostępny lokalnie `PQDIFConverter.exe` obsługuje CSV → PQDIF; jego README opisuje też PQDIF → CSV, ale oznacza ten kierunek jako niedziałający. Nie jest to konwerter PQF.

## Kontener przykładowego pomiaru

- Binarny nagłówek plików pomiarowych ma 48 bajtów, zaczyna się tekstem `PQBOX150 V4.708`, zawiera identyfikator rodzaju pliku oraz tekstowy znacznik `20260924120146`.
- `comments.pqf` jest tekstem UTF-8 z BOM; `info.pqf` jest binarny.
- `cyc.pqf`: 122 443 164 bajty = 48 + 11 283 × 10 852. Liczba interwałów zgadza się z odczytem GUI (11 283, interwał 60 s, 24.09.2026 12:02–02.10.2026 08:05).
- Pierwszy interwał daje się przejść jako bloki: 16-bitowy identyfikator i 16-bitowa długość payloadu, oba big-endian. Pierwsze pary ID/długość: 150/24, 100/12, 101/32, 902/12, 903/32, 102/140, 103/248. Suma bloków wynosi dokładnie 10 852 bajty. Początkowy prefiks powtarza się we wszystkich 11 283 interwałach.
- W payloadzie występują liczby zgodne z float32 little-endian. To obserwacja strukturalna, nie zatwierdzenie nazw kanałów, skalowania lub flag.
- `cyc10t.pqf`, `cyc150t.pqf`, `recS3.pqf` mają tylko 48-bajtowy nagłówek. Nie traktować ich jako serii zerowych.
- Pozostałe klasy czasu i rekordery są oddzielnymi plikami; nie wolno mieszać ich agregacji.

## Lokalna baza mapowania producenta

`C:/Program Files/WinPQ mobil (64Bit)/plugin_ext/PQDIF Export/MappingDB.db` jest bazą SQLite. Odczytano ją z `mode=ro`. Tabela `pqbox` zawiera `ID, Struct, PQBOX_ID, DataType, Offset`; `main` ma jednostki, a `english` etykiety. Przykłady:

| ID bazy | Struktura | Pole | Typ | Offset | Jednostka |
|---|---|---|---|---:|---|
| 4285 | StructF | Freq | float | 8 | Hz |
| 31 | StructU | U1 | float | 8 | V |
| 544 | StructU | U2 | float | 12 | V |
| 1057 | StructU | U3 | float | 16 | V |
| 32 | StructU | THD1 | float | 36 | % |

Na początkowym etapie baza nie wystarczała do powiązania nazw struktur z blokami TLV, kodowania czasu, przekładni i flag. Późniejsze porównanie CSV potwierdziło zakres 41 kanałów i dwie występujące flagi, zgodnie z końcową sekcją wdrożenia. Wyciąg roboczy do walidacji znajduje się w `tmp/pqf_analysis/channel_mapping.json`. Inne konfiguracje i specjalne znaczniki skończonych wartości brakujących nie zostały udokumentowane; NaN/Inf są wykluczane.

ID bazy nie są ID szablonu eksportu: profil utworzony w GUI dla `f` ma `selection=125`, podczas gdy baza oznacza ID 125 jako interharmoniczną U1 rzędu 45. Zatem nie można budować profilu `.selection` przez bezpośrednie kopiowanie ID z bazy.

## Ustawienia i źródła

[Instrukcja producenta WinPQ mobil](https://www.a-eberle.de/wp-content/uploads/2021/03/BA_WinPQmobil_EN.pdf), strony 73–75, opisuje eksport danych interwałowych, zapisywanie i wczytywanie wyboru kanałów, kolejność kolumn oraz osobne znaczniki czasu ekstremów. Opcja **Fill gaps** wypełnia przerwy zerami: należy ją wyłączyć. **With Flagging** eksportuje flagi i powinna być włączona. Nie usuwać nagłówka z informacją o interwale. Lokalna kopia instrukcji jest wyłącznie plikiem roboczym w `tmp/pqf_analysis/`.

## Kryteria dalszego rozszerzania importu

1. Porównać wszystkie próbki każdego dopuszczonego kanału z CSV tej samej sesji, uwzględniając precyzję eksportu.
2. Potwierdzić czas i agregację oraz przekładnie, jednostki i flagi; nie ukrywać kanałów niezweryfikowanych pod poprawnie wyglądającą etykietą.
3. Testować nagłówek nieznanej wersji, ucięte bloki, braki, NaN/Inf, duplikaty i przerwy czasu. Odrzucać nieobsługiwane warianty z jasnym komunikatem.
4. Nie kopiować bazy producenta do dystrybucji aplikacji bez sprawdzenia warunków licencji. Własny jawny, zweryfikowany zakres parsera opisać osobno.

## Porównanie z rzeczywistym eksportem WinPQ

Uzyskano `exports/20260924_all.csv`, UTF-8 BOM, separator tabulator. Plik zawiera wiele sekcji o różnych interwałach i szerokościach; nie wolno sklejać go jako jednej tabeli. Pierwszy nagłówek jest w wierszu 11, po nim 11 283 wiersze interwałów 60 s. CSV potwierdza znaczniki od 24.09.2026 12:03 do 02.10.2026 08:05, czyli znaczniki końców interwałów. Kolejne tabele zaczynają się nagłówkami na wierszach 11299 i 79008 (numeracja od 1).

Porównano każdą próbkę podstawowych kanałów; poniższe offsety float32LE liczone od początku interwału dawały maksymalny błąd poniżej 0,000501 względem CSV zaokrąglonego do 3 miejsc. To potwierdzenie dla tego konkretnego pomiaru, bez gwarancji przenośności na inny firmware, przekładnie lub konfigurację.

| Kanał CSV | Offset |
|---|---:|
| UL1 / UL2 / UL3 [V] | 144 / 148 / 152 |
| IL1 / IL2 / IL3 [A] | 2252 / 2256 / 2260 |
| THDL1 [%] | 172 |
| THD_I1 [%] | 2272 |
| PL1 / Ptotal [W] | 4180 / 4192 |
| QL1 / Qtotal [Var] | 4212 / 4224 |
| DL1 / Dtotal [Var] | 4616 / 4628 |
| tg_(fi)_L1 / tg_(fi)_ | 5312 / 5324 |
| f [Hz] | 92 |

**Ustalenie dotyczące flag:** CSV oznacza `X` w interwałach indeks 2535 i 2637 (26.09.2026 06:18 i 08:00). Niezerowe pole stanu TLV150 występuje tylko dla 2535, TLV152 ma pola stanu zerowe wszędzie, a podstawowe słowa jakości w znacznikach czasu obu interwałów są takie jak w pozostałych. Druga flaga została odnaleziona w osobnym `cyc2h.pqf`, TLV600, o znaczniku czasu odpowiadającym indeksowi 2637. W obu przypadkach pole stanu zawiera `00800000`, pozostałe bajty stanu są zerowe. Pełny eksport WinPQ włącza kanały Plt do pierwszej tabeli, więc flaga tego wiersza obejmuje także klasę 2h. Odczyt wyłącznie flag TLV150 nie odwzorowałby pełnego eksportu. To potwierdzenie dla dwóch zaobserwowanych flag; pozostałe możliwe kombinacje bitów nie zostały zweryfikowane.

## Wdrożenie i testy

`import_pqf(folder, time_offset_hours=2)` zwraca wspólny model `Dataset`. Brak jawnego przesunięcia zegara powoduje błąd. Wartość +2 jest potwierdzona dla tej sesji; parser nie rozpoznaje strefy automatycznie. Zakłada epokę 1990-01-01; dla innej konfiguracji zegara należy sprawdzić czasy w WinPQ. Odrzucane są inne firmware, układ bloków, interwał, nieznane flagi, nieobsługiwane słowa jakości czasu, niezgodne identyfikatory sesji i niepełne pliki.

SHA256 payloadu konfiguracji zatwierdzonego profilu: `382af6285d974bcc1e17fb271a503c231f0130e0e008b9c6f3e9a0443e7023d8`. Fingerprint nie obejmuje nagłówka z datą sesji, ale może obejmować inne zmienne pola info.pqf o nieznanym znaczeniu. Celowo może więc odrzucić również nową sesję o pozornie identycznych ustawieniach. Wtedy należy użyć CSV; profil można rozszerzyć dopiero po nowym pełnym porównaniu. Nie zapisano prywatnego payloadu w repozytorium; testy syntetyczne podmieniają jedynie oczekiwany hash swojego sztucznego fixture.

Wszystkie 41 kanałów odpowiada wyborowi `default_channels` CSV: U/I z min/max, P/Q/D faz i sumy, THDU/THDI faz, tg(fi), częstotliwość. Dwie oflagowane próbki są wykluczane wspólnie we wszystkich kanałach. Jest to konserwatywna reguła odwzorowująca pełny eksport, opisana w ostrzeżeniu raportu. NaN i nieskończoności stają się brakami, nie zerami. Min/max są wartościami eksportowanymi przez WinPQ; nie deklaruje się ich jako ekstremów półokresowych.

Test porównania z pełnym CSV zakończył się wynikiem PASS: 11 283 identyczne znaczniki czasu, 41 zgodnych jednostek i serii (maksymalna różnica poniżej 0,000501), 2 identyczne wykluczone próbki. `tests/test_pqf.py` zawiera 11 testów syntetycznych i 1 pełne porównanie lokalnego eksportu (łącznie 12 PASS), obejmując znany wynik, flagę 2h, brak jawnego offsetu, nieznane flagi i firmware, zmianę jednego bajtu konfiguracji, zmieniony layout, ucięcie, NaN/Inf, duplikaty i konflikty czasów, przerwy oraz wiele pomiarów w folderze. Test pełnego porównania jest pomijany, gdy prywatne źródła nie są dostępne. Nowe konfiguracje pomiarowe, inne przekładnie i inne sezony czasowe pozostają do porównania z WinPQ.
