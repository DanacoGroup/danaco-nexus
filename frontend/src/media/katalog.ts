// Spis materiałów ruchomych. Wynik frontend/scripts/zasoby.py — nie edytować ręcznie.
// Źródła: promocja/film, promocja/kampania, motion/stany, motion/start.

export type Zrodla = { mp4?: string; webm?: string };
export type Film = { id: string; tytul: string; opis: string; kadr: string; zrodla: Zrodla; plakat: string; napisy: Record<string, string> };
export type Kampania = Film & { temat: string };
export type Nagranie = { id: string; zrodla: Zrodla };
export type Stan = Nagranie & { rodzina: string };

export const FILMY = [
  {
    "id": "nexus-15s-16x9",
    "tytul": "Spot 15 s",
    "opis": "Krótka forma do mediów społecznościowych.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/film/katalog/nexus-15s-16x9.mp4",
      "webm": "/film/katalog/nexus-15s-16x9.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-15s-16x9.pl.vtt",
      "en": "/film/katalog/nexus-15s-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-15s-1x1",
    "tytul": "Spot 15 s",
    "opis": "Krótka forma do mediów społecznościowych.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/film/katalog/nexus-15s-1x1.mp4",
      "webm": "/film/katalog/nexus-15s-1x1.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-15s-1x1.pl.vtt",
      "en": "/film/katalog/nexus-15s-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-15s-9x16",
    "tytul": "Spot 15 s",
    "opis": "Krótka forma do mediów społecznościowych.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/film/katalog/nexus-15s-9x16.mp4",
      "webm": "/film/katalog/nexus-15s-9x16.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-15s-9x16.pl.vtt",
      "en": "/film/katalog/nexus-15s-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-30s-16x9",
    "tytul": "Spot 30 s",
    "opis": "Pełna obietnica produktu w pół minuty.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/film/katalog/nexus-30s-16x9.mp4",
      "webm": "/film/katalog/nexus-30s-16x9.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-30s-16x9.pl.vtt",
      "en": "/film/katalog/nexus-30s-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-30s-9x16",
    "tytul": "Spot 30 s",
    "opis": "Pełna obietnica produktu w pół minuty.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/film/katalog/nexus-30s-9x16.mp4",
      "webm": "/film/katalog/nexus-30s-9x16.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-30s-9x16.pl.vtt",
      "en": "/film/katalog/nexus-30s-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-60s-16x9-1440p",
    "tytul": "Film główny (16x9-1440p)",
    "opis": "Minuta o tym, czym jest Danaco Nexus.",
    "kadr": "",
    "zrodla": {
      "mp4": "/film/katalog/nexus-60s-16x9-1440p.mp4",
      "webm": "/film/katalog/nexus-60s-16x9-1440p.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-60s-16x9-1440p.pl.vtt",
      "en": "/film/katalog/nexus-60s-16x9-1440p.en.vtt"
    }
  },
  {
    "id": "nexus-60s-16x9-lektor",
    "tytul": "Film główny (16x9-lektor)",
    "opis": "Minuta o tym, czym jest Danaco Nexus.",
    "kadr": "",
    "zrodla": {
      "mp4": "/film/katalog/nexus-60s-16x9-lektor.mp4",
      "webm": "/film/katalog/nexus-60s-16x9-lektor.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-60s-16x9-lektor.pl.vtt",
      "en": "/film/katalog/nexus-60s-16x9-lektor.en.vtt"
    }
  },
  {
    "id": "nexus-60s-16x9",
    "tytul": "Film główny",
    "opis": "Minuta o tym, czym jest Danaco Nexus.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/film/katalog/nexus-60s-16x9.mp4",
      "webm": "/film/katalog/nexus-60s-16x9.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {
      "pl": "/film/katalog/nexus-60s-16x9.pl.vtt",
      "en": "/film/katalog/nexus-60s-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-6s-16x9",
    "tytul": "Zajawka",
    "opis": "Sześć sekund: znak, obietnica, adres.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/film/katalog/nexus-6s-16x9.mp4",
      "webm": "/film/katalog/nexus-6s-16x9.webm"
    },
    "plakat": "/film/okladki/okladka-1920x1080.png",
    "napisy": {}
  }
] as const;

export const KAMPANIA = [
  {
    "id": "nexus-analityka-16x9",
    "temat": "nexus-analityka",
    "tytul": "Analityka biznesowa",
    "opis": "Liczby z faktur i arkuszy zamienione w wykres i wniosek.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-analityka-16x9.mp4",
      "webm": "/kampania/nexus-analityka-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-analityka-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-analityka-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-analityka-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-analityka-1x1",
    "temat": "nexus-analityka",
    "tytul": "Analityka biznesowa",
    "opis": "Liczby z faktur i arkuszy zamienione w wykres i wniosek.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-analityka-1x1.mp4",
      "webm": "/kampania/nexus-analityka-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-analityka-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-analityka-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-analityka-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-analityka-9x16",
    "temat": "nexus-analityka",
    "tytul": "Analityka biznesowa",
    "opis": "Liczby z faktur i arkuszy zamienione w wykres i wniosek.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-analityka-9x16.mp4",
      "webm": "/kampania/nexus-analityka-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-analityka-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-analityka-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-analityka-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-automatyzacja-16x9",
    "temat": "nexus-automatyzacja",
    "tytul": "Automatyzacja",
    "opis": "Powtarzalna robota ustawiona raz i wykonywana sama.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-automatyzacja-16x9.mp4",
      "webm": "/kampania/nexus-automatyzacja-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-automatyzacja-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-automatyzacja-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-automatyzacja-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-automatyzacja-1x1",
    "temat": "nexus-automatyzacja",
    "tytul": "Automatyzacja",
    "opis": "Powtarzalna robota ustawiona raz i wykonywana sama.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-automatyzacja-1x1.mp4",
      "webm": "/kampania/nexus-automatyzacja-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-automatyzacja-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-automatyzacja-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-automatyzacja-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-automatyzacja-9x16",
    "temat": "nexus-automatyzacja",
    "tytul": "Automatyzacja",
    "opis": "Powtarzalna robota ustawiona raz i wykonywana sama.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-automatyzacja-9x16.mp4",
      "webm": "/kampania/nexus-automatyzacja-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-automatyzacja-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-automatyzacja-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-automatyzacja-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-firmy-16x9",
    "temat": "nexus-firmy",
    "tytul": "Dla firm",
    "opis": "Jedna przestrzeń dla zespołu: dokumenty, poczta, kalendarz.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-firmy-16x9.mp4",
      "webm": "/kampania/nexus-firmy-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-firmy-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-firmy-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-firmy-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-firmy-1x1",
    "temat": "nexus-firmy",
    "tytul": "Dla firm",
    "opis": "Jedna przestrzeń dla zespołu: dokumenty, poczta, kalendarz.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-firmy-1x1.mp4",
      "webm": "/kampania/nexus-firmy-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-firmy-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-firmy-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-firmy-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-firmy-9x16",
    "temat": "nexus-firmy",
    "tytul": "Dla firm",
    "opis": "Jedna przestrzeń dla zespołu: dokumenty, poczta, kalendarz.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-firmy-9x16.mp4",
      "webm": "/kampania/nexus-firmy-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-firmy-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-firmy-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-firmy-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-funkcje-16x9",
    "temat": "nexus-funkcje",
    "tytul": "Funkcje",
    "opis": "Przegląd tego, co Nexus robi na co dzień.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-funkcje-16x9.mp4",
      "webm": "/kampania/nexus-funkcje-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-funkcje-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-funkcje-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-funkcje-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-marka-16x9",
    "temat": "nexus-marka",
    "tytul": "Marka",
    "opis": "Znak, łuk i Aurora — język wizualny Nexusa.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-marka-16x9.mp4",
      "webm": "/kampania/nexus-marka-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-marka-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-marka-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-marka-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-produktywnosc-16x9",
    "temat": "nexus-produktywnosc",
    "tytul": "Produktywność",
    "opis": "Dzień pracy skrócony o rzeczy, których nie trzeba robić ręcznie.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-produktywnosc-16x9.mp4",
      "webm": "/kampania/nexus-produktywnosc-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-produktywnosc-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-produktywnosc-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-produktywnosc-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-produktywnosc-1x1",
    "temat": "nexus-produktywnosc",
    "tytul": "Produktywność",
    "opis": "Dzień pracy skrócony o rzeczy, których nie trzeba robić ręcznie.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-produktywnosc-1x1.mp4",
      "webm": "/kampania/nexus-produktywnosc-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-produktywnosc-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-produktywnosc-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-produktywnosc-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-produktywnosc-9x16",
    "temat": "nexus-produktywnosc",
    "tytul": "Produktywność",
    "opis": "Dzień pracy skrócony o rzeczy, których nie trzeba robić ręcznie.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-produktywnosc-9x16.mp4",
      "webm": "/kampania/nexus-produktywnosc-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-produktywnosc-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-produktywnosc-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-produktywnosc-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-wiedza-16x9",
    "temat": "nexus-wiedza",
    "tytul": "Baza wiedzy",
    "opis": "Własne dokumenty jako pamięć agenta — z przypisami do źródła.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-wiedza-16x9.mp4",
      "webm": "/kampania/nexus-wiedza-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-wiedza-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wiedza-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-wiedza-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-wiedza-1x1",
    "temat": "nexus-wiedza",
    "tytul": "Baza wiedzy",
    "opis": "Własne dokumenty jako pamięć agenta — z przypisami do źródła.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-wiedza-1x1.mp4",
      "webm": "/kampania/nexus-wiedza-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-wiedza-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wiedza-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-wiedza-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-wiedza-9x16",
    "temat": "nexus-wiedza",
    "tytul": "Baza wiedzy",
    "opis": "Własne dokumenty jako pamięć agenta — z przypisami do źródła.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-wiedza-9x16.mp4",
      "webm": "/kampania/nexus-wiedza-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-wiedza-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wiedza-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-wiedza-9x16.en.vtt"
    }
  },
  {
    "id": "nexus-wyszukiwanie-16x9",
    "temat": "nexus-wyszukiwanie",
    "tytul": "Wyszukiwanie",
    "opis": "Pytanie opisowe zamiast przypominania sobie nazwy pliku.",
    "kadr": "16:9",
    "zrodla": {
      "mp4": "/kampania/nexus-wyszukiwanie-16x9.mp4",
      "webm": "/kampania/nexus-wyszukiwanie-16x9.webm"
    },
    "plakat": "/kampania/okladki/nexus-wyszukiwanie-16x9.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wyszukiwanie-16x9.pl.vtt",
      "en": "/kampania/napisy/nexus-wyszukiwanie-16x9.en.vtt"
    }
  },
  {
    "id": "nexus-wyszukiwanie-1x1",
    "temat": "nexus-wyszukiwanie",
    "tytul": "Wyszukiwanie",
    "opis": "Pytanie opisowe zamiast przypominania sobie nazwy pliku.",
    "kadr": "1:1",
    "zrodla": {
      "mp4": "/kampania/nexus-wyszukiwanie-1x1.mp4",
      "webm": "/kampania/nexus-wyszukiwanie-1x1.webm"
    },
    "plakat": "/kampania/okladki/nexus-wyszukiwanie-1x1.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wyszukiwanie-1x1.pl.vtt",
      "en": "/kampania/napisy/nexus-wyszukiwanie-1x1.en.vtt"
    }
  },
  {
    "id": "nexus-wyszukiwanie-9x16",
    "temat": "nexus-wyszukiwanie",
    "tytul": "Wyszukiwanie",
    "opis": "Pytanie opisowe zamiast przypominania sobie nazwy pliku.",
    "kadr": "9:16",
    "zrodla": {
      "mp4": "/kampania/nexus-wyszukiwanie-9x16.mp4",
      "webm": "/kampania/nexus-wyszukiwanie-9x16.webm"
    },
    "plakat": "/kampania/okladki/nexus-wyszukiwanie-9x16.png",
    "napisy": {
      "pl": "/kampania/napisy/nexus-wyszukiwanie-9x16.pl.vtt",
      "en": "/kampania/napisy/nexus-wyszukiwanie-9x16.en.vtt"
    }
  }
] as const;

export const STANY = [
  {
    "id": "automatyzacja",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/automatyzacja.mp4"
    }
  },
  {
    "id": "blad",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/blad.mp4"
    }
  },
  {
    "id": "brak-wynikow",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/brak-wynikow.mp4"
    }
  },
  {
    "id": "czytanie",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/czytanie.mp4"
    }
  },
  {
    "id": "ilustracja",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/ilustracja.mp4"
    }
  },
  {
    "id": "ocr",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/ocr.mp4"
    }
  },
  {
    "id": "odnawianie",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/odnawianie.mp4"
    }
  },
  {
    "id": "ostrzezenie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/ostrzezenie.mp4"
    }
  },
  {
    "id": "pierwsze-uruchomienie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/pierwsze-uruchomienie.mp4"
    }
  },
  {
    "id": "podglad-pliku",
    "rodzina": "przejścia widoków",
    "zrodla": {
      "mp4": "/ruch/stany/podglad-pliku.mp4"
    }
  },
  {
    "id": "polaczenie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/polaczenie.mp4"
    }
  },
  {
    "id": "powiadomienie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/powiadomienie.mp4"
    }
  },
  {
    "id": "powiekszanie",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/powiekszanie.mp4"
    }
  },
  {
    "id": "przesylanie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/przesylanie.mp4"
    }
  },
  {
    "id": "przypiecie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/przypiecie.mp4"
    }
  },
  {
    "id": "pusta-rozmowa",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/pusta-rozmowa.mp4"
    }
  },
  {
    "id": "showreel",
    "rodzina": "zestawienie",
    "zrodla": {
      "mp4": "/ruch/stany/showreel.mp4",
      "webm": "/ruch/stany/showreel.webm"
    }
  },
  {
    "id": "skopiowano",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/skopiowano.mp4"
    }
  },
  {
    "id": "sukces",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/sukces.mp4"
    }
  },
  {
    "id": "synchronizacja",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/synchronizacja.mp4"
    }
  },
  {
    "id": "szuflada",
    "rodzina": "przejścia widoków",
    "zrodla": {
      "mp4": "/ruch/stany/szuflada.mp4"
    }
  },
  {
    "id": "tlo",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/tlo.mp4"
    }
  },
  {
    "id": "transkrypcja",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/transkrypcja.mp4"
    }
  },
  {
    "id": "upuszczanie",
    "rodzina": "stany",
    "zrodla": {
      "mp4": "/ruch/stany/upuszczanie.mp4"
    }
  },
  {
    "id": "widoki",
    "rodzina": "przejścia widoków",
    "zrodla": {
      "mp4": "/ruch/stany/widoki.mp4"
    }
  },
  {
    "id": "wiedza",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/wiedza.mp4"
    }
  },
  {
    "id": "wycieczka",
    "rodzina": "praca agenta",
    "zrodla": {
      "mp4": "/ruch/stany/wycieczka.mp4"
    }
  }
] as const;

export const START = [
  {
    "id": "intro-3d",
    "zrodla": {
      "mp4": "/ruch/start/intro-3d.mp4",
      "webm": "/ruch/start/intro-3d.webm"
    }
  },
  {
    "id": "intro-znaku",
    "zrodla": {
      "mp4": "/ruch/start/intro-znaku.mp4",
      "webm": "/ruch/start/intro-znaku.webm"
    }
  },
  {
    "id": "logowanie-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/logowanie-ciemny.mp4",
      "webm": "/ruch/start/logowanie-ciemny.webm"
    }
  },
  {
    "id": "logowanie-jasny",
    "zrodla": {
      "mp4": "/ruch/start/logowanie-jasny.mp4",
      "webm": "/ruch/start/logowanie-jasny.webm"
    }
  },
  {
    "id": "logowanie-ograniczone-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/logowanie-ograniczone-ciemny.mp4",
      "webm": "/ruch/start/logowanie-ograniczone-ciemny.webm"
    }
  },
  {
    "id": "moment-blad",
    "zrodla": {
      "mp4": "/ruch/start/moment-blad.mp4",
      "webm": "/ruch/start/moment-blad.webm"
    }
  },
  {
    "id": "moment-brak-polaczenia",
    "zrodla": {
      "mp4": "/ruch/start/moment-brak-polaczenia.mp4",
      "webm": "/ruch/start/moment-brak-polaczenia.webm"
    }
  },
  {
    "id": "moment-instalacja",
    "zrodla": {
      "mp4": "/ruch/start/moment-instalacja.mp4",
      "webm": "/ruch/start/moment-instalacja.webm"
    }
  },
  {
    "id": "moment-mysli",
    "zrodla": {
      "mp4": "/ruch/start/moment-mysli.mp4",
      "webm": "/ruch/start/moment-mysli.webm"
    }
  },
  {
    "id": "moment-sukces",
    "zrodla": {
      "mp4": "/ruch/start/moment-sukces.mp4",
      "webm": "/ruch/start/moment-sukces.webm"
    }
  },
  {
    "id": "moment-wylogowanie",
    "zrodla": {
      "mp4": "/ruch/start/moment-wylogowanie.mp4",
      "webm": "/ruch/start/moment-wylogowanie.webm"
    }
  },
  {
    "id": "uruchomienie-komputer-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-komputer-ciemny.mp4",
      "webm": "/ruch/start/uruchomienie-komputer-ciemny.webm"
    }
  },
  {
    "id": "uruchomienie-komputer-jasny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-komputer-jasny.mp4",
      "webm": "/ruch/start/uruchomienie-komputer-jasny.webm"
    }
  },
  {
    "id": "uruchomienie-krotkie-komputer-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-krotkie-komputer-ciemny.mp4",
      "webm": "/ruch/start/uruchomienie-krotkie-komputer-ciemny.webm"
    }
  },
  {
    "id": "uruchomienie-krotkie-telefon-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-krotkie-telefon-ciemny.mp4",
      "webm": "/ruch/start/uruchomienie-krotkie-telefon-ciemny.webm"
    }
  },
  {
    "id": "uruchomienie-ograniczone-telefon-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-ograniczone-telefon-ciemny.mp4",
      "webm": "/ruch/start/uruchomienie-ograniczone-telefon-ciemny.webm"
    }
  },
  {
    "id": "uruchomienie-telefon-ciemny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-telefon-ciemny.mp4",
      "webm": "/ruch/start/uruchomienie-telefon-ciemny.webm"
    }
  },
  {
    "id": "uruchomienie-telefon-jasny",
    "zrodla": {
      "mp4": "/ruch/start/uruchomienie-telefon-jasny.mp4",
      "webm": "/ruch/start/uruchomienie-telefon-jasny.webm"
    }
  }
] as const;

