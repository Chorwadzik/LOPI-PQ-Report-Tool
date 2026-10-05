# THD(A) i widma z CSV

Etap 2 wdrożono 2026-10-05. Źródłem jest pierwszy blok eksportu WinPQ mobil
`exports/20260924_all.csv`, o interwale 60 s. Nie rozszerzano mapowania PQF.

## Zweryfikowane kanały

| Rodzaj | Nazwy po imporcie | Jednostka | Liczba kanałów |
| --- | --- | --- | --- |
| THD(A) | THD_(A)_I1, I2, I3, IN (pełny prefiks dla każdego) | A | 4 |
| Harmoniczne U | H2_UL1–H50_UL1, analogicznie UL2 i UL3 | % | 147 |
| Harmoniczne I | H2_I1–H50_I1, analogicznie I2, I3 i IN | A | 196 |

Każdy z 347 kanałów zawiera 11 281 ważnych próbek z 11 283 wierszy.
Dwa oflagowane interwały wykluczył importer CSV. Sprawdzono jednostkę i nazwę
każdego kanału, liczebność oraz brak ujemnych amplitud. Pełne zestawienie dla
tej sesji zapisano w `output/pdf/Kontrola_kanalow_widm.csv`; zawiera także
średnie harmonicznych zaokrąglone do dwóch miejsc.

Domyślny raport z tego CSV wybiera 388 kanałów: 41 dotychczasowych i 347 nowych.
Kanały harmonicznych nie tworzą osobnych wykresów czasowych, lecz dwa widma
grupowane według rzędu i przewodu. Pierwsza harmoniczna, UNE i U12/U23/U31 nie
są automatycznie dobierane do tych widm. Błędna jednostka rozpoznanego kanału
powoduje błąd, nie ciche przeliczenie.

## Statystyka i prezentacja

Użytkownik wybiera `mean`, `max` lub `p95`, domyślnie średnią arytmetyczną.
P95 wykorzystuje interpolację liniową w pozycji `(n - 1) × 0,95` w posortowanej
serii indeksowanej od zera. Obliczenia obejmują wszystkie ważne próbki osobno
dla każdej harmonicznej. Nie sumuje się średnich słupków w celu otrzymania THD.
THD(A) jest odczytywany z osobnych kanałów źródłowych.

Wybór zapisuje się w metadanych projektu jako `spectrum_statistic`; jest też
obsługiwany przez CLI w JSON metadanych. Starsze projekty bez tego pola przyjmują
`mean`. Nieznana wartość ustawienia jest odrzucana.

Kolory L1/L2/L3/N to czerwony/zielony/niebieski/fioletowy, również przy wyborze
pojedynczego kanału THD(A). Kolor nie oznacza percentyla ani maksimum.
Nie ma progów normatywnych ani skali procentu limitu. Używane są jednostki CSV.
Tabele pokazują h2–h50, wynik i `n` ważnych próbek dla każdego przewodu. Wyniki
mają dwa miejsca po przecinku; liczebności są całkowite. Brak wyniku to kreska,
brak słupka jest oznaczony krzyżykiem albo opisem braku danych całego panelu.

## Kontrola

40 testów projektu przeszło, w tym znane wyniki średniej/maksimum/P95, błędne
jednostki, ujemne i niefinitywne amplitudy, brak fazy/rzędu, zerowa amplituda,
jedna próbka, zachowanie źródła i stabilność kolorów przy częściowym wyborze.
Sprawdzono wybór nowych kanałów w interfejsie i walidację metadanych projektu.

Wygenerowano raport z rzeczywistego CSV (25 stron) oraz testowe raporty
z niepełnymi widmami i statystykami maksimum/P95. Kontrola wizualna obejmowała
wszystkie strony; osobny agent sprawdził kod i skład. Ograniczenia: pierwszy
blok CSV, brak automatycznego łączenia z PQF, brak zdarzeń i oceny normatywnej.
