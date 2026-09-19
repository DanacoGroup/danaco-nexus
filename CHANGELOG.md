# Dziennik zmian

Format zgodny z [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
numeracja wersji zgodna z [SemVer](https://semver.org/lang/pl/).

## [Nieopublikowane]

### Dodano

- Założenie projektu Danaco Nexus.
- Asystent AI z interfejsem czatu: historia rozmów, przesyłanie plików (przycisk,
  przeciąganie, wklejanie), strumieniowanie odpowiedzi i działań narzędzi, podgląd
  i pobieranie wyników, anulowanie zadań, układ dla komputerów, tabletów i telefonów.
- Pętla agenta Claude (`claude-opus-5`) z myśleniem adaptacyjnym, pamięcią podręczną
  promptu i server-side fallbacks; zadania w kolejce PostgreSQL wykonywane przez
  proces roboczy.
- 22 narzędzia agenta: OCR z przeszukiwalnym PDF (Tesseract), poprawa skanów
  (OpenCV, unpaper), korekta zdjęć, retusz portretów, powiększanie Real-ESRGAN,
  ImageMagick, konwersje obrazów i dokumentów (LibreOffice, Inkscape), tworzenie
  dokumentów, korekta językowa (LanguageTool), podział, łączenie i edycja PDF,
  wykrywanie granic dokumentów, audio i wideo (FFmpeg), archiwa ZIP, baza wiedzy
  z wyszukiwaniem semantycznym (Qdrant).
- Logowanie administratora (Argon2, sesje w bazie, ochrona CSRF, limit prób).
- Docker Compose, skrypt budowy obrazów, szablon witryny Caddy i procedura
  przeniesienia magazynu obrazów containerd na partycję danych.
