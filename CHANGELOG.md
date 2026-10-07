# Historia wersji

## v1.3 — 2026-10-07

- Jeden połączony kanał tgφ na fazę i jeden dla Σ w domyślnym raporcie Sonel.
- Wynik to suma czterech wyeksportowanych wariantów ze znakami; brak którejkolwiek
  składowej pozostaje brakiem. Metoda jest opisana na wykresach i w załączniku.
- Oryginalne warianty pozostają dostępne do kontroli poza domyślnym wyborem.
- Poprawny status CLI także przy znakach φ/Σ i kodowaniu konsoli Windows cp1250.

## v1.2 — 2026-10-07

- Automatyczne rozpoznawanie eksportu CSV z Sonel Analysis lub WinPQ.
- Strumieniowy import podstawowych kanałów Sonel: oryginalne nazwy, jednostki,
  agregacja, czas UTC, flagi jakości i kontrola kompletności eksportu.
- Osobne wykresy faz i sum Σ, oddzielne warianty tgφ oraz definicje mocy Sonel.
- Test PDF przez gotowy EXE dla syntetycznych danych obu producentów.
- Sonel wymaga CSV z programu producenta; nie dodano dekodera plików .pqm710.

## v1.1 — 2026-10-07

- Osobne wykresy i tabele total dla P, Q, D oraz tgφ.
- Marginesy boczne 15 mm; wykresy i tabele szerokości 180 mm.
- Dostępne potwierdzenie dat i przewijanie zakładki kanałów.
- Naprawione dołączanie zależności PDF; kontrola zależności i test PDF przez gotowy EXE.
- Jedna aktualna wersja EXE w `dist`; wcześniejsze wydania w `dist/Kontrola funkcji`.
