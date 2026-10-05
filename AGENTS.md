# Zasady projektu LOPI PQ Report Tool

## Cel i ograniczenia
- Aplikacja Windows EXE działa lokalnie bez AI, tokenów, telemetrii i usług sieciowych. Wynik: PDF.
- Użytkownik edytuje autorów, tytuł, numer raportu, nazwę pliku, obiekt, adres, opis i wnioski.
- Pliki w `przykładowy raport` są materiałem źródłowym tylko do odczytu. Nie kopiować starych wyników ani danych klienta do nowych raportów.
- Zachować polskie znaki, czytelne wykresy, jednostki i tabele. Styl odnosić do dostarczonego Worda.

## Strażnicy jakości
- Agent danych sprawdza źródła, nazwy kanałów, jednostki, daty, interwały, braki i flagi. Nie zgadywać mapowania binarnego PQF. Odczyt binarny wymaga dokumentacji lub porównania z eksportem WinPQ.
- Agent raportu sprawdza strony PDF, podpisy, rozmiar tekstu, legendy, podziały tabel i zakresy osi.
- Agent aplikacji sprawdza obsługę błędów, zapis projektu, instalację i samodzielne uruchomienie EXE.
- Przed wydaniem niezależny agent recenzuje zmiany; koordynator poprawia istotne błędy i dokumentuje nieweryfikowane elementy.

## Rzetelność pomiarowa
- Nie utożsamiać ekstremów średnich interwałowych z ekstremami półokresowymi.
- Nie utożsamiać THDI w procentach z THD(A); zachować jednostki z eksportu.
- Brak danych nie oznacza zera ani zgodności z normą. Nie tworzyć automatycznej oceny normatywnej bez zweryfikowanych kryteriów, czasu agregacji i pokrycia okresu.
- Wnioski techniczne wpisuje użytkownik. Nie przepisywać ich z wzorca.
- Statystyki liczyć z pełnych danych. Ewentualną redukcję wykresów opisać i zachować ekstrema.
- Zmiany parsera i obliczeń wymagają testów na brakach, błędnych wartościach i znanym wyniku.

## Praca
- Nie publikować ani wysyłać pomiarów do usług zewnętrznych.
- Nie dodawać plików pomiarowych, buildów i danych klientów do Git.
- Każdy etap opisać uczciwie: działające, sprawdzone, ograniczenia, kolejny krok.
