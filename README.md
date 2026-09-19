# Danaco Nexus

**Personal AI Workspace for Documents, Images and Automation**

Prywatny asystent AI działający na serwerze Danaco. Interfejs czatu w stylu
Claude/ChatGPT: użytkownik przesyła wiadomość i pliki, a Claude analizuje
zadanie, planuje wykonanie, dobiera narzędzia serwera i zwraca gotowe wyniki.

## Zakres

- czat z Claude z historią rozmów, przesyłaniem plików i wynikami do pobrania,
- agent narzędziowy: OCR i PDF z warstwą tekstową, poprawa jakości skanów
  i zdjęć, Real-ESRGAN, podział i łączenie PDF, konwersje LibreOffice,
  FFmpeg, LanguageTool, archiwa ZIP,
- pamięć: rozmowy, zadania, pliki i wyniki w PostgreSQL,
- baza wiedzy: wyszukiwanie dokumentów po treści (Qdrant),
- uruchamianie przez Docker Compose, publikacja przez Caddy (HTTPS),
- logowanie administratora.

## Stan

Projekt w budowie. Instrukcja instalacji i uruchomienia zostanie uzupełniona
wraz z pierwszą wersją działającą.
