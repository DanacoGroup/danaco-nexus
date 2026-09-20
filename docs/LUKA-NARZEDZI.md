# Programy na serwerze bez narzędzia agenta

Stan na 20 września 2026, po domknięciu luki. Rejestr `backend/nexus/tools/` liczy
**82 narzędzia** (rano było 59); stoi za nimi ponad trzydzieści programów i bibliotek. W `/danaco/programy` leży **49 katalogów**
programów — reszta nie ma żadnego narzędzia, więc agent nie może ich użyć, choćby
użytkownik wprost o to poprosił.

Ten dokument jest wykazem tej luki, a nie obietnicą. Każda pozycja ma wpisaną funkcję,
którą dałaby użytkownikowi, i szacunek pracy.

## Podpięte dziś

ImageMagick · LibreOffice · Inkscape · FFmpeg i ffprobe · Real-ESRGAN · Tesseract ·
unpaper · rembg · Apache Tika · PyMuPDF · OpenCV · Pillow · pikepdf · reportlab ·
LanguageTool · Whisper · Piper · Qdrant · Node.js · Playwright.

Dołożone 20 września: **DDColor** (koloryzacja), **DeepFilterNet 3** (odszumianie mowy),
**Depth Anything V2** i **LaMa** (głębia, rozmycie tła, ożywienie zdjęcia, usuwanie
obiektów), **Demucs** (rozdzielenie ścieżek), **CodeFormer** (rekonstrukcja twarzy),
**Typst** i **Tectonic** (skład do druku), **pandoc**, **Docling**, **Iconify**,
**Lottie**, **gifski**, **oxipng**, **svgo**, **semgrep**, **ruff**, **shellcheck**,
**typos**, **pa11y**, **WhisperX** (mówcy w transkrypcji).

Sprawdzone na prawdziwych plikach, nie tylko w testach: koloryzacja małego zdjęcia —
5 s (wczytanie modelu 4,4 s, praca 0,6 s); ożywienie zdjęcia — film 1440×1080, 90 klatek,
3 s materiału powstaje w 11 s (głębia 4,8 s, warstwy 3,1 s, render 3,3 s).

## Co zostało świadomie pominięte

| Program | Dlaczego nie |
|---|---|
| **InsightFace** (`danaco-twarze`, `danaco-twarze-indeks`) | modele wyłącznie do użytku niekomercyjnego, a produkt jest płatny; dodatkowo wizerunek twarzy to dane biometryczne — szczególna kategoria wg RODO, wymagająca osobnej decyzji o zgodzie i okresie przechowywania, a nie wpisu w rejestrze narzędzi |
| **GIMP** (Script-Fu) | pokrywa się z `imagemagick`, a bezpieczne wystawienie Script-Fu znaczy wykonywanie kodu układanego przez model |
| **Blender** | render Cycles zajmuje serwer na kwadranse; wymaga kolejki zadań długich i limitów, których produkt jeszcze nie ma |
| **surowy FFmpeg** | konwersje, przycinanie i kompresję ma `media_process`; FFmpeg jest pod spodem |
| **`k6`, `hyperfine`, `git-lfs`, `gh`** | narzędzia wytwórcze zespołu, nie funkcje dla użytkownika produktu |

## Kolejność dalszej pracy

1. **Blender** — dopiero gdy będzie kolejka zadań długich i limit czasu renderu na konto.
2. **zoekt** — szybkie wyszukiwanie w dużym repozytorium dla modułu Kod, gdy projekty urosną.
3. **Szablony Typst** — `typeset_document` ma cztery; warto dołożyć kolejne układy pod
   konkretne zastosowania (umowa, faktura, katalog produktów).
