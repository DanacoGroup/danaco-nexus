# Dziennik zmian

Format zgodny z [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/),
numeracja wersji zgodna z [SemVer](https://semver.org/lang/pl/).

## [Nieopublikowane]

### Dodano

- Założenie projektu Danaco Nexus.
- Asystent AI z interfejsem czatu: historia rozmów, przesyłanie plików (przycisk,
  przeciąganie, wklejanie), strumieniowanie odpowiedzi i działań narzędzi, podgląd
  i pobieranie wyników, anulowanie zadań, układ dla komputerów, tabletów i telefonów.
- Agent działający przez Claude Code CLI (`claude-opus-5`, zapasowo `claude-sonnet-5`)
  na subskrypcji konta Claude, z sesją CLI utrzymującą kontekst rozmowy; narzędzia
  udostępnia serwer MCP projektu. Zadania w kolejce PostgreSQL wykonuje proces roboczy.
- 22 narzędzia agenta: OCR z przeszukiwalnym PDF (Tesseract), poprawa skanów
  (OpenCV, unpaper), korekta zdjęć, retusz portretów, powiększanie Real-ESRGAN,
  ImageMagick, konwersje obrazów i dokumentów (LibreOffice, Inkscape), tworzenie
  dokumentów, korekta językowa (LanguageTool), podział, łączenie i edycja PDF,
  wykrywanie granic dokumentów, audio i wideo (FFmpeg), archiwa ZIP, baza wiedzy
  z wyszukiwaniem semantycznym (Qdrant).
- Logowanie administratora (Argon2, sesje w bazie, ochrona CSRF, limit prób).
- Wdrożenie bez Dockera: skrypt instalacji, własny klaster PostgreSQL 18, Qdrant
  i LanguageTool w katalogu projektu, usługi systemd, szablon witryny Caddy.
- Chmura osobista Nextcloud (FrankenPHP, baza w klastrze projektu, zadania w tle co 5 minut)
  z synchronizacją na komputer i telefon oraz narzędzia agenta `cloud_browse`,
  `cloud_import` i `cloud_save`; odnośnik do chmury w interfejsie.
- Skrypt rekordów DNS w strefie OVH i witryna Caddy dla `danaco-nexus.pl`
  i `cloud.danaco-nexus.pl`.
- Polecenie diagnostyczne `doctor` (programy, usługi, Claude Code CLI, serwer MCP).
