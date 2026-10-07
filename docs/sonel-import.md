# Sonel CSV — obsługa od v1.2

## Przygotowanie pliku

W Sonel Analysis wybierz Pomiary, zakres pomiaru i wymagane kanały. Zaznacz
całą tabelę, następnie Raporty → Raport CSV. Zachowaj nagłówki, jednostki,
kolumny flag i deklarację czasu. Wyłącz dzielenie CSV na mniejsze pliki.
W LOPI wybierz „Wczytaj CSV (Sonel / WinPQ)…”. Format zostanie rozpoznany
automatycznie. Uzupełnij dane raportu, wskaż folder wyjściowy i wybierz Generuj PDF.
Nie potrzeba licencji konwertera, Pythona ani uruchomionego Sonel Analysis
podczas importu gotowego CSV.

## Zakres

Zweryfikowano polski eksport tabeli Sonel Analysis 5.0.0 z PQM-710.
Import zachowuje nazwy, jednostki, min./maks./średnie napięć i prądów,
średnie częstotliwości, P, Q z jawnym wariantem, D, S/Sn, THD U/I w procentach
oraz osobne warianty tg(φ). Nie utożsamia Q1, QB, Sn i D. Fazy i sumy Σ
mają oddzielne wykresy. Pola binarne .pqm710 nie są dekodowane — wskaż CSV.

Czytany jest strumień wierszy, a w pamięci pozostają kanały podstawowego
raportu. Pozostałe kanały (w tym harmoniczne, energie i flicker) są pomijane
z informacją o liczbie pominięć. Z różnych agregacji importowana jest tylko
najkrótsza zadeklarowana; pozostałe nie są mieszane. W kontrolnym eksporcie
odczytano 57 kanałów o agregacji 10 s. Próbka kontrolna obejmuje około
3 godzin, nie całą rejestrację. Wersja nie tworzy widm Sonel ani THD(A)
przez przeliczanie THDI. Dotychczasowe widma WinPQ nadal są obsługiwane.

## Jakość i czas

### Połączony tgφ od v1.3

Domyślny zestaw pokazuje jeden kanał tgφ dla L1, L2, L3 oraz oddzielny dla Σ.
Każda próbka jest sumą wyeksportowanych tgφ L+, C−, L− i C+ z ich znakami.
Oryginalne warianty są nadal dostępne na liście kanałów i w eksporcie danych.
Σ jest obliczane z czterech wariantów Σ, nigdy z dodawania faz.

Podstawa: [instrukcja PQM-702/703/710/711 v1.52, strony drukowane 79 i 82](https://cdn.sonel.com/Instrukcje/PQM-702_702T_703_710_711%20insobs%20v1.52%20PL.pdf).
Wszystkie cztery warianty mają wspólny mianownik, przyrost energii czynnej
pobranej EP+, a warianty C zawierają znak minus. Wynik opisujemy jako sumę
wariantów, nie jako iloraz średnich mocy Q/P ani ocenę rozliczeń kwadrantowych.
Wykorzystujemy zaokrąglone wartości eksportu, nie odtwarzamy surowych energii.

Wymagane są cztery składowe tego samego przewodu i okresu, o jednostce
bezwymiarowej. Brak, nieprawidłowy znak, niezgodna jednostka lub przepełnienie
oznaczają brak wyniku; zera nie zastępują brakujących kanałów. Metoda i uwagi
są zapisane w metadanych oraz PDF. Na próbce kontrolnej otrzymano 4 × 1086
ważnych wartości; domyślny zestaw raportu obejmuje 45 kanałów.

### Pozostałe zasady

- Zachowywany jest czas i offset UTC z CSV. Przesunięcie PQBox nie jest stosowane.
- G/Gf oznacza brak synchronizacji GPS/UTC: dane zachowane, ograniczenie
  dokładności czasu opisane w raporcie.
- E/Ef, P/Pf, T/Tf, A/Af i nieznane flagi konserwatywnie wykluczają cały wiersz.
- Gwiazdka I *L1 itd. pozostaje w nazwie. Sonel oznacza nią ograniczanie
  małych prądów; wyeksportowane zera nie są zmieniane.
- Braki, liczby niefinitywne i błędne wartości nie stają się zerami.
- Sprawdzane są liczby kolumn, unikalność i kolejność czasu, nazwy/jednostki,
  strefa UTC oraz zgodność granic wierszy z deklaracją eksportu. Tolerancja
  granic 2 ms uwzględnia potwierdzoną różnicę 1 ms w eksporcie Sonel.
- Nie powstaje automatyczna ocena normatywna ani wnioski techniczne.

## Walidacja i ograniczenia

Testy używają wyłącznie danych syntetycznych: znanych wartości, braków,
flag normalnych i szybkich, zduplikowanych nagłówków/czasów, uciętych plików,
jednostek i różnych agregacji. Dane klientów pozostają poza Git.
Nie jest to uniwersalny importer wszystkich wersji i języków Sonel.
Inny układ tabeli wymaga osobnego eksportu kontrolnego i walidacji.

Znaczenie flag, gwiazdki i eksportu sprawdzono w lokalnej instrukcji
Sonel Analysis (rozdział pomiarów i eksportu). Opcjonalny PQDif Converter
jest osobnym licencjonowanym produktem i nie jest zależnością LOPI v1.2.

## Odbiór v1.2

- 81 testów syntetycznych/regresyjnych zakończonych poprawnie (77 w pełnym
  zestawie oraz 4 dodatkowe testy integracji CSV).
- Niezależny przegląd kodu i porównanie wszystkich 61 902 zachowanych wartości
  kontrolnego eksportu z CSV: zgodne.
- Gotowy EXE wygenerował poprawne PDF dla syntetycznych WinPQ i Sonel oraz
  rzeczywistego eksportu Sonel (1086 próbek, 57 kanałów).
- Wszystkie 31 stron PDF fragmentu kontrolnego oceniono wizualnie. Rendery
  raportu z EXE są identyczne z zatwierdzonymi renderami wersji źródłowej.
- Nie zweryfikowano pełnej kilkudniowej rejestracji, innych modeli, wersji
  eksportera ani języków. Nie deklaruje się obsługi binarnego .pqm710.

## Odbiór v1.3

92 testy przeszły (91 w zestawie oraz dodatkowy test CLI z kodowaniem cp1250).
Niezależnie porównano wszystkie 4344 nowe wartości tgφ
na próbce CSV oraz potwierdzono zachowanie 57 oryginalnych kanałów.
Raport domyślny ma 45 kanałów i 25 stron; wszystkie strony przeszły kontrolę
wizualną, w tym opis metody, fazy/Σ, powiększenia P1–P99 i załącznik.
