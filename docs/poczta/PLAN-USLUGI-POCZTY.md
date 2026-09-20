# Danaco Nexus — własna usługa poczty: plan wdrożenia

| | |
|---|---|
| **Produkt** | Danaco Nexus |
| **Producent** | Danaco Holding Group Sp. z o.o. |
| **Wersja** | projekt do zatwierdzenia |
| **Status** | Projektowy — nic nie zostało wdrożone, kupione ani zmienione na serwerze |
| **Data** | 2026-09-20 |

**Informacje szczegółowe dokumentu:**

| | |
|---|---|
| **Tytuł** | Własna usługa poczty dla kont z subskrypcją — domena, umiejscowienie, stos, wpięcie, dostarczalność |
| **Klasa dokumentu** | Plan wdrożenia z rozstrzygnięciami projektowymi |
| **Odbiorcy** | właściciel produktu (decyzja zakupowa) · agent wykonujący wdrożenie · radca prawny (rozdz. 6.5) |
| **Przeznaczenie** | Na podstawie rozdz. 1 właściciel kupuje domenę; na podstawie rozdz. 2–7 osobny agent wykonuje wdrożenie bez dalszych pytań projektowych. |
| **Zakres** | Skrzynka zakładana z poziomu Nexusa dla konta z opłaconą subskrypcją: domena, serwer, stos, kod, DNS, dostarczalność, nadużycia, RODO, etapy |
| **Poza zakresem** | Poczta transakcyjna portalu (odzyskiwanie hasła) — zostaje tam, gdzie jest; skrzynka właściciela na `danaco-group.pl` — nietknięta; migracja całego Nexusa na osobny serwer — osobna decyzja, rozdz. 2.4 |
| **Źródła stanu faktycznego** | `backend/nexus/mail.py` · `backend/nexus/api/modules/poczta.py` · `backend/nexus/platnosci/**` · `backend/nexus/api/files.py` · `deploy/systemd/**` · `deploy/dns/ustaw-dns.py` · pomiary serwera z 2026-09-20 |
| **Zasada nadrzędna** | Operator poczty odpowiada za cudzą korespondencję. Każde rozstrzygnięcie w tym dokumencie wybiera rozwiązanie nudne i sprawdzone nad nowe i eleganckie. |

## Spis treści

1. [Domena](#1-domena)
2. [Gdzie postawić serwer](#2-gdzie-postawić-serwer)
3. [Stos techniczny](#3-stos-techniczny)
4. [Wpięcie w Nexusa](#4-wpięcie-w-nexusa)
5. [Dostarczalność](#5-dostarczalność)
6. [Nadużycia i prawo](#6-nadużycia-i-prawo)
7. [Plan wdrożenia od A do Z](#7-plan-wdrożenia-od-a-do-z)
8. [Ryzyka i kiedy tego nie robić](#8-ryzyka-i-kiedy-tego-nie-robić)
9. [Stan faktyczny ustalony pomiarem](#9-stan-faktyczny-ustalony-pomiarem)

---

## 1. Domena

### 1.1. Czego szukamy

Adres z tej domeny będzie dyktowany przez telefon, wpisywany z wizytówki i czytany przez
filtry antyspamowe cudzych serwerów. Kryteria, w kolejności wagi:

1. **Jednoznaczność zapisu ze słuchu po polsku.** Wyłącznie litery alfabetu polskiego bez
   znaków diakrytycznych. Żadnego `x`, `q`, `v` (Polak dyktuje je jako „iks”, „kju”, „fau”
   i odbiorca wpisuje literalnie). Żadnych cyfr. Żadnych podwójnych liter. Nic, co kusi do
   dopisania ogonka.
2. **Brak ryzyka kolizji ze znakiem towarowym.** Krótkie, ładne słowo słownikowe to zwykle
   cudzy znak w którejś klasie.
3. **Skojarzenie z pocztą** — odbiorca widzący nieznaną domenę ma od razu wiedzieć, że to
   dostawca skrzynek, a nie jednorazowa domena kampanii.
4. **Rozszerzenie neutralne reputacyjnie** (rozdz. 1.2).
5. **Długość.** Ważna, ale najmniej — lepsza domena o dwie sylaby dłuższa niż taka, którą
   trzeba literować.

Domena nie może być poddomeną `danaco-nexus.pl` ani `danaco-group.pl`: reputacja domenowa
(Spamhaus DBL, wewnętrzne listy dostawców, polityka DMARC) działa na poziomie domeny
rejestrowalnej, więc poddomena dziedziczy problem.

### 1.2. Rozszerzenie — rozstrzygnięcie

| Rozszerzenie | Ocena | Uzasadnienie |
|---|---|---|
| **`.pl`** | **wybrane** | Odbiorcy są polscy. Rejestr NASK, domena płatna i weryfikowalna, reputacyjnie neutralna. Polskie bramki pocztowe (WP, Onet, Interia, o2) traktują `.pl` jak swoje. Żaden znany filtr nie punktuje `.pl` ujemnie. |
| `.com` | rejestracja obronna | Też neutralne i rozpoznawalne. Dyktowane po polsku bywa zapisywane jako „kom”. Bierzemy je tylko po to, żeby nikt nie postawił podróbki pod tą samą nazwą. |
| `.email` | **odrzucone** | Delegowane i kupowalne, ale nowe gTLD z tej rodziny (`.email`, `.click`, `.top`, `.online`) mają wysoki udział nadużyć w statystykach nadużyć TLD. Część bramek korporacyjnych podnosi za nie punktację, a niektóre po prostu odrzucają. Kupujemy sobie problem, którego nie musimy mieć. |
| `.mail` | **niemożliwe** | Ciąg `.mail` **nie jest delegowany w korzeniu DNS** — sprawdzone zapytaniem o rekordy NS: odpowiedź pusta (`.email`, `.pl`, `.com` odpowiadają normalnie). Znajduje się wśród ciągów wysokiego ryzyka odłożonych przez ICANN razem z `.corp` i `.home`. Nie da się go kupić u żadnego rejestratora. |
| `.eu`, `.net` | dopuszczalne, gorsze | Neutralne, ale bez zysku wobec `.pl` przy polskich odbiorcach. |
| domena IDN (z ogonkami) | **odrzucone** | Obsługa SMTPUTF8 u odbiorców jest nierówna, a adres z ogonkiem jest niedyktowalny. Nigdy. |

### 1.3. Kandydaci

Kolumna „delegacja” to wynik zapytania o rekordy NS z 2026-09-20. **Brak delegacji nie
oznacza, że domena jest wolna** — domenę można mieć zarejestrowaną bez serwerów nazw, a
domena z delegacją jest na pewno zajęta. Ostateczną odpowiedź daje wyłącznie sprawdzenie
w rejestrze (rozdz. 1.5).

| # | Domena | Znaki | Delegacja 2026-09-20 | Zalety | Wady |
|---|---|---|---|---|---|
| **1** | **`danacopoczta.pl`** | 12 | **brak** (wolna też w `.com`) | Wyłącznie litery polskie, zero `x`/`q`/`v`, zero cyfr, zero podwojeń — ze słuchu zapisuje się na jeden sposób. Zerowe ryzyko znaku towarowego: „Danaco” to własna firma. Odbiorca widzi domenę identyfikowalnej polskiej spółki, co pomaga przy ręcznym odblokowaniu. Prawie na pewno wolna. | Najdłuższa z sensownych. Wpis na blocklistę jest widoczny pod marką Danaco (choć technicznie nie dotyka ani `danaco-nexus.pl`, ani `danaco-group.pl`). |
| 2 | `koperta.pl` | 7 | brak | Najlepsza nazwa na liście, gdyby była wolna: 7 znaków, idealna fonetyka, skojarzenie z pocztą natychmiastowe, pełna neutralność wobec marki produktu. | Popularne słowo słownikowe bez delegacji prawie zawsze znaczy „zarejestrowana i zaparkowana” albo „świeżo zwolniona i obstawiona przez łowców”. Realne ryzyko kolizji ze znakiem towarowym w klasach papierniczych i usługowych. Trzeba sprawdzić w pierwszej kolejności — jeśli wolna, bierzemy ją. |
| 3 | `prostapoczta.pl` | 12 | brak | Czysta fonetyka, zero ryzyka znaku (nazwa opisowa jest trudna do zarejestrowania jako znak), pełna neutralność wobec marki, oczywiste skojarzenie. | Brzmi jak obietnica marketingowa, nie jak usługa Danaco. Buduje drugą markę, którą trzeba by utrzymywać. |
| 4 | `danaco-poczta.pl` | 13 | brak | To samo co #1, plus czytelniejszy podział na człony. | Myślnik trzeba podyktować („kreska”, „minus”, „myślnik” — trzy słowa na jeden znak) i bywa gubiony przy przepisywaniu. To realny koszt przy dyktowaniu przez telefon. |
| 5 | `listor.pl` | 6 | brak | Najkrótsza. Rdzeń „list” daje skojarzenie z pocztą. Łatwa do podyktowania. | Nazwa wymyślona — odbiorca nie odgadnie znaczenia. `listor.com` jest zajęty, więc kolizja z istniejącym podmiotem jest możliwa; wymaga sprawdzenia znaku. |
| 6 | `danacomail.pl` | 13 | brak (wolna też w `.com`) | Zerowe ryzyko znaku, wolna. | **Poważna wada dyktowania:** „mail” Polak wymawia „mejl” i odbiorca wpisuje `danacomejl`. To jest dokładnie ten błąd, którego kryterium 1 zakazuje. Odradzam mimo dostępności. |
| 7 | `pocztowa.pl` | 8 | **zajęta** (serwery `aftermarket.pl` — wystawiona na sprzedaż) | Dobra fonetyka i skojarzenie. | Do odkupienia na rynku wtórnym, czyli cena negocjowana i nieprzewidywalna. Domena z rynku wtórnego ma historię, której nie znamy — mogła już wysyłać spam. Wymagałaby sprawdzenia archiwalnej reputacji przed zakupem. |
| 8 | `adresat.pl` | 7 | **zajęta** (`aftermarket.pl` — na sprzedaż) | Jak wyżej. | Jak wyżej, plus semantyka „adresat” jest myląca dla domeny nadawcy. |
| — | `nadawca.pl`, `skrzynka.pl`, `znaczek.pl`, `listonosz.pl`, `mailo.pl`, `dobrapoczta.pl`, `listowo.pl`, `kopertka.pl`, `poczta.pl` | — | **wszystkie zajęte i delegowane** | — | Odpadają. `mailo.pl` dodatkowo koliduje z francuskim dostawcą poczty Mailo — znak towarowy. |

### 1.4. Rekomendacja

**`danacopoczta.pl`**, z obronną rejestracją `danacopoczta.com`.

Uzasadnienie wyboru wbrew długości: ze wszystkich kryteriów najdroższy w skutkach jest błąd
zapisu adresu ze słuchu (wiadomość nie dochodzi i nikt nie wie dlaczego) oraz kolizja ze
znakiem towarowym (utrata domeny po wdrożeniu, czyli utrata wszystkich adresów użytkowników).
`danacopoczta.pl` zeruje oba ryzyka. Dwanaście znaków to koszt jednorazowy przy dyktowaniu;
tamte dwa błędy są nieodwracalne.

**Jeden wyjątek:** jeżeli sprawdzenie wykaże, że `koperta.pl` jest naprawdę wolna i wolna od
znaku towarowego — brać `koperta.pl`. Jest lepsza pod każdym względem poza pewnością.

### 1.5. Co właściciel ma sprawdzić przed zakupem

Dostępności **nie zgaduję** — powyższe zapytania o NS to tylko przesłanka. Przed zakupem:

1. **Dostępność w rejestrze.** Wyszukiwarka DNS NASK (`dns.pl`) albo panel dowolnego
   rejestratora. Sprawdzić w tej kolejności: `koperta.pl` → `danacopoczta.pl` →
   `prostapoczta.pl` → `listor.pl`.
2. **Historia domeny**, jeśli nie jest to świeża rejestracja: czy domena kiedyś wysyłała
   pocztę i czy jest na listach reputacyjnych domen (Spamhaus DBL, SURBL). Domena
   z rynku wtórnego bez sprawdzonej historii — nie kupować.
3. **Znak towarowy.** Rejestr UPRP (Polska) i EUIPO (Unia), klasa 38 (usługi
   telekomunikacyjne, poczta elektroniczna) i 42. Dla `danacopoczta.pl` to formalność;
   dla każdego słowa słownikowego to warunek konieczny.
4. **Okres rejestracji: co najmniej 2 lata z góry.** Wiek domeny i długość rejestracji są
   sygnałami dla filtrów, a jednoroczna rejestracja domeny pocztowej wygląda jak domena
   jednorazowa.
5. **DNS w OVH.** Rejestrator dowolny, ale strefę prowadzić w OVH — projekt ma już
   działającą automatyzację strefy przez API OVH (`deploy/dns/ustaw-dns.py`), którą
   wdrożenie ma po prostu rozszerzyć, zamiast pisać drugą.
6. **Dane WHOIS spółki jawne**, nie anonimizowane. Dla domeny pocztowej jawny, prawdziwy
   podmiot jest atutem reputacyjnym; ukrywanie danych jest sygnałem negatywnym.
7. **Blokada transferu (registrar lock)** włączona od pierwszego dnia.

---

## 2. Gdzie postawić serwer

### 2.1. Stan faktyczny obecnej maszyny (pomiar 2026-09-20)

| Cecha | Wartość | Znaczenie dla poczty |
|---|---|---|
| Maszyna | OVH, serwer dedykowany, `ns3066572.ip-193-70-46.eu` | Dedykowany, nie VPS — port 25 nie jest blokowany z zasady. |
| IPv4 / IPv6 | `193.70.46.37` / `2001:41d0:303:c25::` | Jeden adres publiczny dla wszystkiego. |
| rDNS (PTR) | `ns3066572.ip-193-70-46.eu` — domyślny OVH | Do zmiany w panelu OVH; dla poczty **musi** wskazywać `mail.<domena>`. |
| Port 25 wychodzący | **otwarty** — sprawdzone połączeniem do `alt1.aspmx.l.google.com:25` i `mx.zoho.com:25`, oba odpowiedziały banerem `220` | Kluczowe. Wysyłka z tej maszyny jest technicznie możliwa już dziś. |
| RAM | 62 GiB, 29 GiB w użyciu, 32 GiB dostępne | Zapas ogromny. |
| CPU | AMD Ryzen 9 9900X, 24 wątki, load 3,1–4,3 | Obciążenie poniżej 20%. |
| Dysk `/danaco` | 937 GB, 586 GB zajęte, **352 GB wolne** | Zapas wystarczający. |
| Dysk `/` | 9,6 GB, **1,9 GB wolne (80%)** | Wąsko. Wszystkie dane poczty musiałyby trafić do `/danaco`, a domyślne ścieżki Postfiksa i Dovecota (`/var/spool/`, `/var/mail/`) trzeba by przenieść. |
| Co jeszcze na niej stoi | `danaco-lex.pl`, `e-kancelaria.app`, `danaco-core.pl`, repozytorium instytucji, kilkanaście usług MCP i API, Nextcloud, dwa klastry PostgreSQL, Caddy jako brama HTTPS całego serwera | **To jest cała produkcja Danaco na jednej maszynie.** |
| Istniejący serwer poczty `danaco-group.pl` | `57.128.253.74`, rDNS `mail.danaco-group.pl` — **inna maszyna** | Zgodnie z wymaganiem zostaje nietknięty. Potwierdzone: na obecnej maszynie nie działa żaden demon pocztowy (brak nasłuchu na 25/143/465/587/993, brak jednostek systemd). |
| Zapora | brak reguł `nft`/`iptables` | Dodanie usługi nasłuchującej publicznie wymagałoby najpierw zbudowania zapory. |

### 2.2. Porównanie wariantów

| Kryterium | (a) Poczta na obecnej maszynie | (b) Osobny mały VPS tylko na pocztę | (c) Osobny serwer na całego Nexusa |
|---|---|---|---|
| **Reputacja IP** | Współdzielona z niczym (dziś nikt stąd nie wysyła), ale **na stałe związana z maszyną trzymającą całą produkcję**. Można kupić dodatkowy adres IP failover w OVH i związać z nim pocztę — wtedy reputacja jest odrębna. | Własny adres, własna reputacja, zero sprzężenia z czymkolwiek. Ryzyko: adres przydzielony przez dostawcę może być już obciążony historią poprzednika — trzeba sprawdzić przed przyjęciem. | Nexus i poczta dzielą nowy adres — czyli ten sam problem co (a), tylko na młodszej maszynie. Bez drugiego IP nic nie rozwiązuje. |
| **PTR / port 25** | PTR ustawialny w panelu OVH dla serwera dedykowanego. Port 25 wychodzący potwierdzony jako otwarty. Przychodzący — do sprawdzenia, ale OVH nie filtruje ruchu do serwerów dedykowanych. | **Do sprawdzenia u każdego dostawcy z osobna.** OVH na VPS blokuje wychodzący SMTP nowym kontom do czasu odblokowania na wniosek; Hetzner blokuje port 25 nowym kontom i odblokowuje po weryfikacji; część dostawców nie odblokowuje nigdy. Warunek zakupu: pisemne potwierdzenie odblokowanego portu 25 w obie strony i ustawialnego rDNS dla IPv4 **i** IPv6. | Jak (b) — warunki zależą od wybranego dostawcy. |
| **Izolacja awarii** | **Najgorsza.** Zalew wiadomości, atak słownikowy na SASL albo przejęta skrzynka konkurują o CPU i dysk z workerem Nexusa i dwoma klastrami PostgreSQL. Co gorsza: przy poważnym nadużyciu OVH blokuje ruch **na poziomie adresu serwera** — i razem z pocztą znika `danaco-lex.pl`, `e-kancelaria.app` i Nexus. | **Najlepsza.** Zablokowany adres, zawieszona usługa, kompromitacja stosu pocztowego — wszystko kończy się na maszynie, na której nie ma nic innego. | Lepsza niż dziś dla Nexusa, ale poczta i Nexus nadal padają razem. |
| **Bezpieczeństwo** | Otwarcie portów 25/465/587/993 czyni z maszyny trzymającej całą produkcję publiczny, uwierzytelniany cel. Postfix i Dovecot to duża, historycznie dziurawa powierzchnia ataku. Kompromitacja stosu pocztowego = kompromitacja hosta wszystkich usług Danaco. | Powierzchnia ataku odizolowana. Maszyna nie trzyma żadnych innych sekretów. Kanał do Nexusa przez WireGuard, bez wystawiania PostgreSQL. | Powierzchnia ataku dzielona z aplikacją i bazą klientów — czyli z danymi płatności i plikami użytkowników. |
| **Koszt** | Zerowy koszt sprzętu. Ewentualny dodatkowy adres IP failover — koszt niewielki, **do sprawdzenia w cenniku OVH**. | Koszt jednego małego VPS-a. Potrzebna klasa: 2 vCPU, 4 GB RAM, 80–160 GB NVMe, ruch nielimitowany. **Konkretnych cen nie podaję — wymaga sprawdzenia aktualnych cenników.** | Koszt pełnowartościowego serwera plus migracja. Najdroższy wariant. |
| **Pracochłonność utrzymania** | Najmniejsza przyrostowo: jedna maszyna do łatania, jedna kopia zapasowa, jeden monitoring. | Druga maszyna: aktualizacje, kopie, monitoring, drugi komplet sekretów, drugi tunel. Realnie ~2–4 godziny miesięcznie ponad wariant (a). | Największa: pełna migracja klastra PostgreSQL, Qdranta, Nextclouda, profilu Claude CLI, Caddy i DNS, z przestojem. Tygodnie pracy. |
| **Wpływ na obecne usługi** | Zasobowo żaden (poczta dla setek skrzynek to pomijalne obciążenie przy 24 wątkach i 32 GB wolnego RAM-u). **Ryzykowo — duży**, patrz wiersze o izolacji i bezpieczeństwie. | Żaden. | Odciąża obecną maszynę, ale kosztem długiego przestoju przy migracji. |

### 2.3. Rekomendacja

**Wariant (b): osobny mały VPS wyłącznie na pocztę.**

Rozstrzygające jest jedno zdanie: *na obecnej maszynie stoi cała produkcja Danaco*. Poczta to
jedyna usługa w tym ekosystemie, której awaria bierze się z działania osób trzecich — obcego
nadawcy, przejętego hasła, cudzej listy spamowej. Umieszczenie takiej usługi na maszynie, na
której działa `danaco-lex.pl`, `e-kancelaria.app`, repozytorium instytucji i Nexus, oznacza,
że jeden użytkownik z ukradzionym hasłem może doprowadzić do zablokowania adresu IP całej
produkcji. Zapas RAM-u, CPU i dysku jest ogromny i **nie ma znaczenia** — argument przeciw
wariantowi (a) nie jest wydajnościowy, tylko dotyczy promienia rażenia.

Wariant (a) z dodatkowym adresem IP failover usuwa problem reputacji adresu, ale nie usuwa
dwóch pozostałych: publicznej powierzchni ataku na hoście całej produkcji oraz tego, że
poważne nadużycie OVH gasi na poziomie serwera, nie adresu.

**Wariant (c) odrzucam jako odpowiedź na to pytanie**, choć osobny serwer dla Nexusa jest
sam w sobie słusznym pomysłem: produkt subskrypcyjny z danymi klientów nie powinien dzielić
maszyny z usługami kancelaryjnymi. To jednak osobna decyzja, o innym uzasadnieniu i innym
koszcie. Wiązanie jej z pocztą opóźniłoby pocztę o tygodnie, a poczcie i tak trzeba osobnego
adresu. **Rozdzielić: poczta na VPS teraz, migracja Nexusa jako osobna pozycja planu rozwoju.**

### 2.4. Warunki, które musi spełnić dostawca VPS-a

Warunki twarde — brak któregokolwiek dyskwalifikuje dostawcę, niezależnie od ceny:

1. Port 25 **wychodzący i przychodzący** odblokowany — potwierdzony pisemnie przed opłaceniem
   albo zweryfikowany w okresie zwrotu.
2. Ustawialny rekord PTR dla IPv4 **i** dla IPv6.
3. Przydzielony adres IPv4 nieobecny na listach: Spamhaus SBL/CSS/PBL, Barracuda, Invaluement,
   SpamCop. Sprawdzić **przed** konfiguracją; jeżeli adres jest wpisany — żądać innego albo
   odstąpić. *(Wpisów UCEPROTECT poziomu 2 i 3 nie brać pod uwagę — obejmują całe sieci i nikt
   poważny ich nie używa.)*
4. Adres nie z puli oznaczonej jako dynamiczna/rezydencjalna (Spamhaus PBL).
5. Dostawca nie zabrania prowadzenia serwera poczty w regulaminie.

Warunki miękkie: lokalizacja w UE (RODO, rozdz. 6.5), migawki dysku, konsola awaryjna.

---

## 3. Stos techniczny

### 3.1. Rozważone rozwiązania

| Rozwiązanie | Werdykt | Uzasadnienie |
|---|---|---|
| **Mailcow** | odrzucone | Działa wyłącznie w Dockerze i twórcy odmawiają wsparcia poza nim. Projekt świadomie nie używa Dockera (magazyn obrazów leży na partycji systemowej, w której zostało 1,9 GB). Sprzeczność nie do obejścia. |
| **Mail-in-a-Box** | odrzucone | Przejmuje całą maszynę i uruchamia własny serwer DNS (`nsd`). Strefę prowadzimy w OVH, mamy do tego automatyzację. Ponadto jego interfejs zarządzania nie nadaje się do programowego zakładania skrzynek z zewnątrz. |
| **Stalwart Mail Server** | **rezerwowe** | Bardzo atrakcyjny kształtem: jeden binarny plik w Ruście, jedna jednostka systemd, jeden plik konfiguracji, wbudowane SMTP/IMAP/JMAP, własny filtr antyspamowy, podpisywanie DKIM, limity i **prawdziwe API administracyjne** — dokładnie to, czego Nexus potrzebuje do zakładania skrzynek. Odrzucony tylko z powodu wieku: pierwsze wydania z 2023 r., konfiguracja zmienia się między wydaniami pobocznymi, a społeczność jest mała. Gdy coś przestanie dostarczać o trzeciej w nocy, nie ma dwudziestu lat cudzych odpowiedzi do przeczytania. Dodatkowo jeden proces obsługuje nadawanie, doręczanie i magazyn naraz — jeden błąd gasi wszystko. |
| **Maddy** | odrzucone | Ta sama idea co Stalwart, ale mniejszy projekt, wyraźnie słabszy filtr antyspamowy (brak odpowiednika modułów bayes i fuzzy z Rspamd) i uboższe zarządzanie. |
| **Postfix + Dovecot + Rspamd + PostgreSQL** | **wybrane** | Rozdz. 3.2. |

Osobno: **OpenDKIM nie jest potrzebny.** Rspamd podpisuje DKIM sam (moduł `dkim_signing`),
sprawdza DKIM, SPF, DMARC i ARC oraz publikuje raporty DMARC. Dokładanie OpenDKIM to
czwarty demon robiący to, co już robi trzeci.

### 3.2. Rozstrzygnięcie: Postfix + Dovecot + Rspamd, użytkownicy w PostgreSQL

| Składnik | Rola | Jednostka systemd |
|---|---|---|
| **Postfix** | MTA: przyjmowanie z zewnątrz (25), nadawanie uwierzytelnione (465 implicit TLS, 587 STARTTLS), doręczanie przez LMTP do Dovecota | `postfix.service` |
| **Dovecot** | IMAP (993), magazyn Maildir, uwierzytelnianie (SASL dla Postfiksa przez gniazdo), limity miejsca (`quota`), usługa `quota-status` dla Postfiksa, `lmtpd` | `dovecot.service` |
| **Rspamd** | Filtr wejściowy, podpisywanie DKIM wychodzących, weryfikacja SPF/DKIM/DMARC, **progi antyspamowe wysyłki** (moduł `ratelimit`), greylisting, bayes, raporty DMARC | `rspamd.service` |
| **Valkey** | Pamięć Rspamd (bayes, fuzzy, liczniki limitów) | `valkey.service` |
| **PostgreSQL** | Tabele skrzynek, aliasów, haseł i limitów — źródło prawdy dla Postfiksa i Dovecota | `postgresql.service` |
| **Caddy** | Certyfikat TLS dla `mail.<domena>` (ACME) i serwowanie polityki MTA-STS | `caddy.service` |

Powody wyboru, w kolejności wagi:

1. **Zakładanie skrzynki sprowadza się do wstawienia wiersza do tabeli.** Wymaganie „skrzynkę
   zakłada aplikacja, bez konfiguracji po stronie użytkownika, i kasuje ją po wygaśnięciu
   subskrypcji” realizuje się przez `INSERT`/`UPDATE`/`DELETE` w SQL. Żadnego autorskiego
   klienta HTTP do cudzego panelu, żadnego parsowania odpowiedzi, żadnego trybu, w którym
   panel jest niedostępny i skrzynka nie powstaje. Nexus już prowadzi PostgreSQL i model
   SQLAlchemy — to jest ta sama technologia, którą zespół zna.
2. **Progi antyspamowe jednakowe dla wszystkich** odwzorowują się wprost na statyczne wiadra
   modułu `ratelimit` w Rspamd — jeden plik konfiguracji, bez logiki planów w kodzie.
3. **Limit miejsca na skrzynkę** to udokumentowana funkcja Dovecota (`quota`,
   `quota_rule`) wraz z usługą `quota-status`, którą Postfix odpytuje **w trakcie sesji
   SMTP**, odrzucając przepełnioną skrzynkę kodem 5xx zamiast przyjmować wiadomość i
   generować odbicie. To jest warunek konieczny rozdz. 4.5.
4. **Diagnostyka dostarczalności jest najtrudniejszą częścią tego projektu**, a to jest stos,
   dla którego każda odpowiedź już istnieje — w dokumentacji, na listach dyskusyjnych i
   w archiwach postmasterów.
5. Cztery zwykłe jednostki systemd, bez Dockera, wszystkie ścieżki przestawialne do katalogu
   projektu — zgodne z przyjętym sposobem prowadzenia usług w Danaco.

### 3.3. Wady wybranego rozwiązania — wprost

1. **Największa powierzchnia konfiguracji ze wszystkich rozważanych.** Cztery demony,
   kilkanaście plików, składnia Postfiksa jest archaiczna i nieprzebaczająca.
2. **Otwarty przekaźnik to realny błąd jednej linii.** Zła wartość `mynetworks` albo
   `permit_mynetworks` w niewłaściwym miejscu `smtpd_recipient_restrictions` czyni z serwera
   otwarty relay i kończy projekt w jeden dzień. Wdrożenie **musi** zakończyć się testem
   otwartego przekaźnika z zewnątrz, zanim powstanie pierwsza prawdziwa skrzynka.
3. **Backscatter.** Przyjęcie wiadomości, a dopiero potem odkrycie, że adresata nie ma albo
   skrzynka jest pełna, generuje odbicia do sfałszowanych nadawców i kończy się wpisem na
   listę. Wszystkie odrzucenia muszą padać w trakcie sesji SMTP.
4. **Zmiana składni konfiguracji Dovecota w gałęzi 2.4** względem 2.3 jest niezgodna wstecz.
   Instalować od razu wersję z repozytoriów dystrybucji i zapisać w dokumentacji wdrożenia,
   która to gałąź — inaczej pierwsza większa aktualizacja systemu zgasi IMAP.
5. **Cztery rzeczy do łatania** zamiast jednej.
6. **Rspamd wymaga Valkey/Redis** — piąty proces.

Warunek zmiany decyzji na Stalwart: jeżeli po pół roku utrzymanie czterech demonów okaże
się kosztowniejsze niż zakładano albo pojawi się produktowa potrzeba JMAP (szybka
synchronizacja na telefonie), przepisanie warstwy provisioningu na API Stalwart jest małą
zmianą — kontrakt między Nexusem a serwerem poczty (rozdz. 4.3) jest celowo wąski.

---

## 4. Wpięcie w Nexusa

### 4.1. Zasada

Moduł Poczta **nie dowiaduje się, że skrzynka jest nasza**. Skrzynka Nexusa to zwykłe konto
IMAP/SMTP zapisane tą samą drogą co konto dodane ręcznie — różni się jedynie tym, że
poświadczenia generuje serwer, a nie człowiek. Dzięki temu cała istniejąca ścieżka
(`nexus/mail.py`, `nexus/api/modules/poczta.py`, narzędzia `mail_*`, kolejka
`biuro_oczekujace`) działa bez jednej zmiany w logice poczty.

### 4.2. Nowe miejsca w kodzie

| Ścieżka | Zawartość |
|---|---|
| `backend/nexus/skrzynki/model.py` | Tabela `poczta_skrzynki` (rozdz. 4.4) |
| `backend/nexus/skrzynki/uslugi.py` | `utworz`, `wstrzymaj`, `wznow`, `usun`, `stan`, `uzycie` — logika po stronie Nexusa |
| `backend/nexus/skrzynki/klient_serwera.py` | Kanał do serwera poczty (rozdz. 4.3); protokół z jedną implementacją HTTP, jak `KlientStripe` w `platnosci/klient.py` |
| `backend/nexus/skrzynki/uzgodnienie.py` | Uzgodnienie stanu skrzynek ze stanem subskrypcji — biegnie z timera |
| `backend/nexus/api/modules/poczta.py` | Nowe trasy: `GET/POST/DELETE /api/poczta/skrzynka`, `POST /api/poczta/skrzynka/haslo-aplikacji`, `POST /api/poczta/skrzynka/eksport` |
| `backend/nexus/platnosci/zdarzenia.py` | Wywołanie usług skrzynek w `_subskrypcja_zmieniona` i `_subskrypcja_usunieta` |
| `backend/nexus/portal/konta.py` | `usun_konto` kasuje skrzynkę natychmiast |
| `backend/nexus/api/files.py` | `zajete_miejsce` dolicza miejsce skrzynki (rozdz. 4.5) |
| `frontend/src/modules/poczta/` | Ekran „Skrzynka Nexusa”: wybór nazwy, stan, hasło aplikacji, eksport |
| `deploy/systemd/danaco-nexus-skrzynki.timer` + `.service` | Uzgodnienie raz na dobę |
| `backend/tests/test_skrzynki.py` | Testy z atrapą klienta serwera poczty |

### 4.3. Kanał między Nexusem a serwerem poczty

Rozważone: pozwolić Dovecotowi pytać bazę Nexusa wprost (`passdb sql`). **Odrzucone** —
oznaczałoby wystawienie klastra PostgreSQL Nexusa (dziś wyłącznie gniazdo uniksowe,
uwierzytelnianie `peer`) do sieci i uzależnienie logowania do poczty od dostępności bazy
aplikacji. Poczta ma działać, gdy Nexus jest wyłączony na aktualizację.

**Rozstrzygnięcie:** serwer poczty ma **własną** bazę skrzynek. Nexus zmienia ją przez wąskie,
uwierzytelnione API administracyjne wystawione **wyłącznie w tunelu WireGuard** między obiema
maszynami (nasłuch na adresie tunelu, nie na publicznym). Uwierzytelnienie: token w nagłówku
plus ograniczenie źródłowego adresu tunelu.

Operacje — pięć, celowo:

| Operacja | Działanie na serwerze poczty |
|---|---|
| `POST /skrzynki` | Zakłada skrzynkę, zwraca wygenerowane hasło (jedyny raz w postaci jawnej) |
| `POST /skrzynki/<adres>/wstrzymaj` | Blokuje nadawanie, IMAP tylko do odczytu, poczta przychodząca odrzucana kodem 5xx |
| `POST /skrzynki/<adres>/wznow` | Cofa powyższe |
| `DELETE /skrzynki/<adres>` | Kasuje wiersz i katalog Maildir; adres trafia na listę nigdy-do-ponownego-użycia |
| `GET /skrzynki/<adres>` | Stan i liczba zajętych bajtów |

Każda jest idempotentna — uzgodnienie (rozdz. 4.6) wywołuje je wielokrotnie.

### 4.4. Zakładanie skrzynki i konfiguracja bez hasła

Przebieg:

1. Użytkownik w module Poczta wybiera „Załóż skrzynkę w Nexusie”, podaje nazwę przed `@`.
2. Serwer sprawdza uprawnienie (rozdz. 4.6) i nazwę:
   - wzorzec `^[a-z0-9](?:[a-z0-9.-]{1,28}[a-z0-9])$`, bez dwóch kropek pod rząd, wyłącznie ASCII;
   - lista nazw zastrzeżonych: wszystkie z RFC 2142 (`postmaster`, `abuse`, `hostmaster`,
     `webmaster`, `security`, `noc`, `info`, `sales`, `support`) oraz `admin`, `root`,
     `noreply`, `no-reply`, `mailer-daemon`, `dmarc`, `tlsrpt`, `nexus`, `danaco`
     — oraz każda nazwa już kiedyś wydana;
   - **adresy nie są nigdy ponownie wydawane.** Tabela zachowuje nagrobki. Wydanie
     zwolnionego adresu nowej osobie oznacza doręczanie jej cudzej korespondencji, w tym
     wiadomości resetujących hasła — to jednocześnie incydent bezpieczeństwa i naruszenie
     ochrony danych.
3. Nexus generuje hasło `secrets.token_urlsafe(32)`, zakłada skrzynkę przez API, po czym
   **zapisuje konto istniejącą funkcją `nexus.mail.save_accounts()`** do
   `dane/app/poczta/<owner>.json` (prawa 600, podmiana atomowa — już zaimplementowane).
   Wpis dostaje dodatkowe pole `zrodlo: "nexus"`.
4. Moduł Poczta widzi kolejne konto i działa. Zero konfiguracji po stronie użytkownika,
   zero hasła na ekranie.

Konsekwencja, którą trzeba zaprojektować od razu, nie później: skoro hasło zna wyłącznie
serwer, **użytkownik nie może wpiąć skrzynki w Thunderbirda ani w pocztę w telefonie**.
Dlatego od pierwszego wydania: `POST /api/poczta/skrzynka/haslo-aplikacji` generuje
**osobne** poświadczenie (druga pozycja w tabeli haseł skrzynki, własna etykieta, możliwe
odwołanie), pokazywane raz. Dorabianie wielu poświadczeń do jednej skrzynki po fakcie jest
przebudową schematu i uwierzytelniania — zrobić to od początku.

Pole `zrodlo: "nexus"` steruje interfejsem: konto Nexusa ma przycisk „Usuń skrzynkę”
(z ostrzeżeniem o utracie treści), nie ma pól hasła i serwerów, i nie da się go „odłączyć”
istniejącą trasą `DELETE /api/poczta/konta/<id>` bez skasowania skrzynki — inaczej powstałaby
skrzynka-sierota: istniejąca na serwerze, przyjmująca pocztę, niewidoczna dla nikogo.

### 4.5. Miejsce skrzynki w przestrzeni konta

Dziś `backend/nexus/api/files.py` sprawdza przy każdym wysłaniu pliku:

```
limit = settings.konto_limit_mb * 1024 * 1024
zajete = await zajete_miejsce(database, owner)
```

Zmiana: `zajete_miejsce` dolicza `poczta_skrzynki.uzyte_bajty` właściciela. Wartość
**nie jest** pobierana z serwera poczty przy każdym wysłaniu pliku (to wprowadziłoby
sieciowe wywołanie na ścieżce krytycznej) — odświeża ją uzgodnienie dobowe oraz każde
otwarcie ekranu skrzynki, zapisując czas pomiaru.

**Rozstrzygnięcie o egzekwowaniu:** limit Dovecota na skrzynkę ustawiamy na **pełne
2048 MB** (`NEXUS_KONTO_LIMIT_MB`), a nie na „limit minus zajęte pliki”. Blokowane są
**wysyłki plików**, nie poczta przychodząca.

Uzasadnienie: obie strony nie mogą być twarde naraz, bo suma przekroczyłaby limit konta.
Wybór pada na blokowanie plików, bo to działanie zainicjowane przez użytkownika, natychmiast
widoczne i z czytelnym komunikatem. Odrzucona poczta przychodząca jest niewidoczna dla
użytkownika, widoczna dla osoby trzeciej i wygląda jak awaria usługi. Skutek uboczny: konto
może chwilowo przekroczyć 2 GB, jeśli użytkownik ma pełną skrzynkę i pełne pliki. To jest
świadomie przyjęte — nadwyżka jest ograniczona (maksymalnie do drugiego tyle) i znika, gdy
użytkownik cokolwiek skasuje.

Interfejs pokazuje rozbicie: „Pliki 1,2 GB · Poczta 0,3 GB · Razem 1,5 z 2 GB”. Przy 90%
zajętości — ostrzeżenie w module Poczta i w module Pliki.

### 4.6. Cykl życia skrzynki a subskrypcja

**Kto ma prawo do skrzynki.** Wymaganie mówi „konto z aktywną subskrypcją”. Plan `osobisty`
jest w katalogu oznaczony `bezplatny=True` i przydziela się sam. **Rozstrzygam: skrzynka
przysługuje wyłącznie planom płatnym** (`pro`, `zespol`) w stanie z `STATUSY_UPRAWNIAJACE`
(`probna`, `aktywna`, `zalegla`). Powód nie jest handlowy, tylko antyspamowy: darmowa
skrzynka pocztowa zakładana samoobsługowo to dokładnie ten produkt, który spamerzy zakładają
masowo, a koszt jednego takiego incydentu ponoszą wszyscy użytkownicy naraz (rozdz. 6.3).
Bariera płatności jest najskuteczniejszym i najtańszym filtrem, jaki mamy. **Wymaga
potwierdzenia właściciela**, bo zmienia zakres planu bezpłatnego.

Stany skrzynki i przejścia:

| Stan | Nadawanie | IMAP | Poczta przychodząca | Wyzwalacz |
|---|---|---|---|---|
| `czynna` | tak | pełny | przyjmowana | Uprawniająca subskrypcja |
| `wstrzymana` | **nie** | tylko odczyt | **odrzucana kodem 5xx** | Utrata uprawnienia albo wykrycie nadużycia |
| `do_usuniecia` | nie | tylko odczyt | odrzucana | 30. dzień w stanie `wstrzymana` |
| — (skasowana) | — | — | — | Skasowanie treści i wiersza; adres na liście nagrobków |

- **Okres karencji: 30 dni** w stanie `wstrzymana`, w trakcie których treść jest do odczytu
  i do eksportu, a potem znika. Krótszy okres nie daje szans odzyskać korespondencji; dłuższy
  to przechowywanie cudzych danych bez podstawy. Wartość musi trafić do regulaminu.
- Poczta przychodząca do skrzynki wstrzymanej jest **odrzucana**, nie przyjmowana i
  kasowana. Nadawca ma wiedzieć, że wiadomość nie doszła.
- Zawiadomienia: w chwili wstrzymania, po 7, 21 i 29 dniach — pocztą na adres kontaktowy
  konta (nie na adres skrzynki, która właśnie przestała przyjmować pocztę) i w interfejsie.
- **Eksport przed skasowaniem:** `POST /api/poczta/skrzynka/eksport` tworzy archiwum Maildir
  w plikach konta. Bez tego skasowanie nie jest do obrony ani wobec użytkownika, ani wobec
  art. 20 RODO.

**Skąd bierze się decyzja o stanie.** Zdarzenia Stripe w `platnosci/zdarzenia.py` są szybką
ścieżką: `customer.subscription.updated` i `.deleted` wywołują odpowiednio `wznow`/`wstrzymaj`.
Gwarancją jest natomiast **dobowe uzgodnienie** (`danaco-nexus-skrzynki.timer`): dla każdej
skrzynki liczy uprawnienie z tabeli `platnosci_subskrypcje`, porównuje ze stanem na serwerze
poczty i wyrównuje. Webhooki się gubią; timer nie. Ten sam bieg pobiera zajętość skrzynek
i przelicza terminy karencji.

**Klucz powiązania.** `platnosci_subskrypcje.uzytkownik` trzyma identyfikator konta
(`UserSession.owner_id`), nie login — tak samo jak `files.owner_id`, `conversations.owner_id`
i plik `dane/app/poczta/<konto>.json`. `poczta_skrzynki` ma mieć tę samą kolumnę
`owner_id: uuid`, żeby uprawnienie, przestrzeń i skrzynka rozstrzygały się po jednym kluczu.
Adres e-mail konta portalu może się zmienić; identyfikator nie.

Dodatkowo `nexus.portal.konta.usun_konto` kasuje skrzynkę **natychmiast**, bez karencji —
użytkownik kasujący konto wyraża wolę wprost.

---

## 5. Dostarczalność

### 5.1. Rekordy DNS

Wartości do wpisania w strefie. `<D>` = kupiona domena, `<IP4>`/`<IP6>` = adresy VPS-a
pocztowego. Rekordy zakłada rozszerzony `deploy/dns/ustaw-dns.py` (API OVH), nie ręka.

| Nazwa | Typ | Wartość | Uwagi |
|---|---|---|---|
| `mail.<D>` | A | `<IP4>` | Nazwa HELO serwera. Musi się zgadzać z PTR. |
| `mail.<D>` | AAAA | `<IP6>` | **Publikować dopiero po ustawieniu i sprawdzeniu PTR dla IPv6.** Gmail odrzuca pocztę z IPv6 bez zgodnego PTR. Do tego czasu Postfix z `inet_protocols = ipv4`. |
| `<D>` | MX | `10 mail.<D>.` | Jeden MX. Zapasowy MX bez własnej filtracji to zaproszenie do omijania filtrów. |
| `<D>` | TXT | `v=spf1 mx -all` | `mx` pokrywa dokładnie hosta z rekordu MX. `-all` twardo — nikt inny nie wysyła w naszym imieniu. |
| `mail.<D>` | TXT | `v=spf1 a -all` | SPF dla samej nazwy HELO — potrzebny przy sprawdzeniach HELO i dla odbić z pustym nadawcą. Pomijany nagminnie. |
| `s202611._domainkey.<D>` | TXT | `v=DKIM1; k=rsa; h=sha256; p=<klucz publiczny>` | RSA-2048. Selektor z datą, żeby rotacja była oczywista; rotować raz w roku. Ed25519 dopiero, gdy RSA działa (podwójny podpis, nie zamiana). |
| `_dmarc.<D>` | TXT | `v=DMARC1; p=none; rua=mailto:dmarc@<D>; ruf=mailto:dmarc@<D>; fo=1; adkim=s; aspf=s` | Start. Zaostrzanie — rozdz. 5.2. |
| `_smtp._tls.<D>` | TXT | `v=TLSRPTv1; rua=mailto:tlsrpt@<D>` | Raporty o niepowodzeniach TLS. Tani sygnał, darmowa diagnostyka. |
| `_mta-sts.<D>` | TXT | `v=STSv1; id=20261101000000` | `id` zmieniać przy każdej zmianie polityki. |
| `mta-sts.<D>` | A / AAAA | `<IP4>` / `<IP6>` | Caddy na VPS-ie serwuje `https://mta-sts.<D>/.well-known/mta-sts.txt` z `version: STSv1`, `mode: testing`, `mx: mail.<D>`, `max_age: 604800`. Po 30 dniach bez zgłoszeń — `mode: enforce`, `max_age: 2592000`. |
| `<D>` | TXT | `google-site-verification=…` | Po rejestracji w Google Postmaster Tools. |
| PTR dla `<IP4>` | — | `mail.<D>` | Ustawiany w panelu dostawcy. |
| PTR dla `<IP6>` | — | `mail.<D>` | Jak wyżej; bez tego nie publikować AAAA. |

**DNSSEC:** włączyć na strefie (OVH obsługuje dla `.pl`). **DANE/TLSA: nie w pierwszym
wydaniu.** Rekord TLSA musi być zmieniany razem z odnowieniem certyfikatu; rozjazd oznacza
ciche, całkowite odrzucanie poczty przez nadawców weryfikujących DANE, a diagnoza takiej
awarii jest nieprzyjemna. Wrócić do tematu, gdy odnawianie certyfikatu będzie miało
sprawdzony zaczep aktualizujący TLSA.

Skrzynki `postmaster@<D>`, `abuse@<D>`, `dmarc@<D>`, `tlsrpt@<D>` muszą istnieć i być
czytane przez człowieka od pierwszego dnia. `abuse@` i `postmaster@` to obowiązek z RFC 2142
i pierwsze miejsce, gdzie zagląda operator listy blokującej.

### 5.2. Rozgrzewanie domeny i adresu

| Okres | Wolumen | Co się dzieje | Warunek przejścia dalej |
|---|---|---|---|
| **Dzień 0 → 30** | zero | Domena kupiona, rekordy opublikowane, `p=none`. Pod `https://<D>` stoi jedna prawdziwa strona wyjaśniająca, czym jest ta domena. **Nie wysyłamy niczego.** | Upływ 30 dni. Wiek domeny jest osobnym sygnałem dla filtrów, a jedynym jego kosztem jest kalendarz — dlatego zakup domeny musi być pierwszym krokiem, przed budową serwera. |
| **Tydzień 1–2** | 5–10 dziennie | Wyłącznie skrzynki testowe. Wysyłka na Gmail, Outlook.com, WP, Onet, Interia, o2, Yahoo. Każda wiadomość czytana z nagłówkami: czy `spf=pass`, `dkim=pass`, `dmarc=pass`, czy trafiła do Odebranych. Ręczne „to nie spam”, gdzie trzeba. | Wszystkie siedem celów: uwierzytelnienie zdane, Odebrane, nie Oferty/Spam. |
| **Tydzień 3–4** | 50–100 dziennie | 5–10 użytkowników pilotażowych z prawdziwą korespondencją. Codzienny przegląd raportów DMARC i dzienników odrzuceń. | Zero odrzuceń o charakterze reputacyjnym; raporty DMARC czyste. |
| **Tydzień 5** | — | DMARC `p=quarantine; pct=100`. | 7 dni bez wzrostu odrzuceń. |
| **Tydzień 6–8** | pułap rosnący | Otwarcie dla subskrybentów. Pułap całodomenowy: start 200 wiadomości na dobę, mnożenie przez 1,5 co trzy dni aż do pułapu docelowego. Realizowany jako jedno wiadro `ratelimit` w Rspamd — podnoszenie to zmiana jednej linii. | Brak wpisów na listy, brak skoku odbić. |
| **Tydzień 8–9** | pełny | DMARC `p=reject`. MTA-STS `enforce`. Pułap całodomenowy zdjęty; zostają progi per konto (rozdz. 6.1). | — |

**Realny czas dojścia do dobrej dostarczalności: 6–10 tygodni** od zakupu domeny, przy
założeniu zera incydentów. Uczciwe zastrzeżenie w dwie strony: (1) większość tego czasu to
czekanie — na wiek domeny i na etapy DMARC — a nie praca; (2) usługa wysyła wyłącznie
korespondencję jeden-do-jednego pisaną przez człowieka i zatwierdzaną kliknięciem, a dla
takiej poczty poprzeczka jest znacznie niżej niż dla wysyłki masowej. Jeden incydent
nadużycia cofa harmonogram o 2–6 tygodni.

### 5.3. Pętle zwrotne i monitorowanie

| Dostawca | Narzędzie | Uwagi |
|---|---|---|
| Microsoft (Outlook.com, Hotmail) | **SNDS** + **JMRP** | Bezpłatne, rejestracja na adres IP, wymaga działającego `abuse@`. Daje dane o skargach i reputacji adresu. Najbardziej użyteczna pętla zwrotna, jaką dostaniemy. Zarejestrować w dniu uruchomienia serwera. |
| Google (Gmail) | **Postmaster Tools** | Wymaga potwierdzenia domeny rekordem TXT. **Uczciwie: przy naszych wolumenach panel będzie w większości pusty** — Google pokazuje dane dopiero powyżej progu kilkuset wiadomości dziennie do Gmaila. Rejestrować mimo to, bo próg zostanie kiedyś przekroczony. |
| Yahoo / AOL | **CFL** | Rejestracja na domenę. |
| WP, Onet, Interia, o2 | **brak** | Polscy dostawcy nie prowadzą publicznych pętli zwrotnych ani nie publikują polityk. Jedyna droga przy problemach to kontakt z ich postmasterem. **To jest realna dziura w monitoringu** i trzeba ją nadrobić ręcznie: stałe konta testowe u każdego z nich, sprawdzane raz w tygodniu, czy wiadomość trafia do Odebranych. |
| Listy blokujące | własny timer systemd | Raz na godzinę: adres w `zen.spamhaus.org`, `b.barracudacentral.org`, `bl.spamcop.net`; domena w `dbl.spamhaus.org`. Wpis → alarm natychmiastowy. **Nie reagować na UCEPROTECT poziom 2 i 3 ani na backscatterer.org** — wpisują całe sieci i nikt poważny ich nie używa; reagowanie na nie to praca bez skutku. |
| Raporty DMARC | parser + tabela | Raporty `rua` przychodzą na `dmarc@<D>` jako skompresowany XML. Bez parsera nikt ich nie przeczyta. Prosty odbiorca zapisujący wyniki do tabeli i alarmujący przy `dkim=fail` lub `spf=fail` z naszego własnego adresu. |
| Uwierzytelnienie | testy jednorazowe | `mail-tester.com` (cel: 10/10), `internet.nl/test-mail`, `check-auth@verifier.port25.com`, MXToolbox. Wykonać przed pierwszą prawdziwą skrzynką i po każdej zmianie w strefie. |

### 5.4. Odbicia

- **Wszystkie odrzucenia w trakcie sesji SMTP.** Nieistniejący adresat, przepełniona
  skrzynka, przekroczony próg — kod 5xx albo 4xx w sesji, nigdy „przyjmij i odbij”.
  `reject_unauth_destination` w `smtpd_recipient_restrictions`, usługa `quota-status`
  Dovecota jako polityka Postfiksa.
- **Odbicia wiadomości wysłanych przez użytkownika** trafiają do jego własnej skrzynki, tak
  jak w każdym normalnym koncie pocztowym, i **dodatkowo** są zliczane po stronie serwera.
  Udział twardych odbić powyżej 15% w godzinie to sygnał przejętego konta (rozdz. 6.2).
- Pełny potok obsługi odbić z listą adresów wyłączonych z wysyłki to narzędzie nadawcy
  masowego. Nie budujemy go — byłby rozwiązaniem problemu, którego ta usługa nie ma.

---

## 6. Nadużycia i prawo

### 6.1. Progi antyspamowe

Jednakowe dla wszystkich kont, niezależne od planu. Realizacja: moduł `ratelimit` w Rspamd,
wiadra na uwierzytelnionego użytkownika.

| Próg | Wartość | Skąd ta liczba |
|---|---|---|
| Wiadomości na godzinę | **30**, dopuszczalny skok do 60 | Człowiek piszący intensywnie wysyła kilkanaście listów na godzinę. Trzydzieści to dwukrotność. |
| Wiadomości na dobę | **200** | Bardzo aktywny korespondent wysyła 50–80 dziennie. Dwieście to blisko trzykrotność. Dodatkowo każda wysyłka przez agenta wymaga kliknięcia użytkownika (`biuro_oczekujace`), więc zbliżenie się do tego progu wymaga świadomego wysiłku. |
| Różnych adresatów na godzinę | **100** | — |
| Różnych adresatów na dobę | **400** | — |
| Adresatów w jednej wiadomości | **100** | Postfix `smtpd_recipient_limit`. |
| Rozmiar wiadomości | **50 MB** | Limit załączników w Nexusie to dziś 25 MB (`NEXUS_POCZTA_ATTACHMENTS_LIMIT_MB`); pułap SMTP musi być wyżej, bo kodowanie zwiększa rozmiar. |
| Równoległych sesji SMTP na konto | **5** | — |
| **Pierwsze 72 godziny życia skrzynki** | **30 wiadomości i 30 różnych adresatów na dobę** | Jedyny próg zależny nie od planu, lecz od **wieku skrzynki**. Konto założone po to, żeby rozesłać spam, wyczerpuje się, zanim zdąży zaszkodzić reputacji. Dla prawdziwego użytkownika pierwsze trzy dni to zakładanie skrzynki i pisanie do kilku osób. |

Reakcja na przekroczenie: **odłożenie (kod 4xx)**, nie odrzucenie, plus alarm do operatora.
Wiadomość zostaje w kolejce klienta i dojdzie później. Nigdy ciche porzucenie.

Osobno, przeciw łamaniu haseł: 5 nieudanych uwierzytelnień z jednego adresu w 10 minut →
blokada adresu na godzinę (jail na dziennikach Postfiksa i Dovecota).

### 6.2. Wykrywanie przejętych kont

Sygnały, liczone w dobowym uzgodnieniu i na bieżąco w Rspamd:

1. Uwierzytelnienia z więcej niż trzech różnych sieci `/24` albo z dwóch różnych krajów
   w ciągu godziny.
2. Wolumen przekraczający pięciokrotność mediany tego konta z ostatnich 14 dni.
3. Ta sama treść wysłana do więcej niż 20 adresatów.
4. Udział twardych odbić powyżej 15% w godzinie.
5. Wysyłka w godzinach, w których to konto nigdy nie wysyłało (sygnał słaby — tylko jako
   dodatek do innego).

**Reakcja automatyczna:** `wstrzymaj` samego nadawania (IMAP zostaje czytelny, poczta
przychodząca przyjmowana), alarm, wpis do dziennika incydentów. Wstrzymanie jest
automatyczne i natychmiastowe, ale **zdejmuje je człowiek** po weryfikacji. Odwrotny
porządek — czekanie na człowieka przed wstrzymaniem — kosztuje reputację całej domeny.

Po potwierdzeniu przejęcia: odwołanie wszystkich poświadczeń skrzynki, wymuszenie zmiany
hasła konta Nexusa, przegląd dziennika sesji IMAP pod kątem tego, co intruz przeczytał —
ostatnie jest przesłanką do zgłoszenia naruszenia (rozdz. 6.5).

### 6.3. Procedura przy wpisie na listę blokującą

1. **Zatrzymać wysyłkę w ciągu minut od alarmu** — pułap Rspamd na zero dla całej domeny.
   Dalsza wysyłka z zablokowanego adresu pogłębia wpis.
2. **Znaleźć źródło**: wolumen z ostatnich 24 godzin w rozbiciu na konta z dziennika
   Postfiksa. Jedno konto odstające od reszty to odpowiedź.
3. **Wstrzymać to konto**, odwołać poświadczenia, ustalić adresy intruza.
4. **Dopiero teraz** wystąpić o wykreślenie. Kolejność jest istotna: wniosek złożony przed
   usunięciem przyczyny kończy się ponownym wpisem, a drugie wykreślenie jest znacznie
   trudniejsze od pierwszego. Spamhaus pyta wprost, co zostało zmienione.
5. Zapisać incydent — datę, przyczynę, działania. Przy kolejnym kontakcie to jedyna waluta.

Orientacyjne czasy wykreślenia: Spamhaus CSS — samoczynnie w ciągu godzin po ustaniu ruchu;
Spamhaus SBL — przegląd ręczny, 1–3 dni robocze; Barracuda — godziny po zgłoszeniu
formularzem; własna lista Microsoftu — zwykle 1–2 dni przez formularz wsparcia.
**Przez cały ten czas poczta użytkowników nie dochodzi.** To jest realny koszt tej usługi
i trzeba go opisać w regulaminie.

### 6.4. Co wolno, a czego nie wolno robić z treścią

- Treść korespondencji **nie jest** indeksowana w Qdrancie ani przekazywana do modelu bez
  działania użytkownika. Agent czyta wiadomość wyłącznie wtedy, gdy użytkownik o to poprosi
  (istniejące narzędzia `mail_read`, `mail_search`) — tak jak dziś przy skrzynce obcej.
- Filtr antyspamowy przetwarza treść przychodzącą — to jest konieczne do świadczenia usługi
  i tak trzeba to opisać w polityce prywatności.
- Nauczanie filtru bayesowskiego na treści użytkowników: **włączone, ale osobne dla każdej
  skrzynki**, nie wspólne. Wspólny model uczony na cudzej korespondencji jest trudny do
  obrony.

### 6.5. Obowiązki operatora poczty i RODO

Uruchomienie skrzynek wprowadza nową kategorię danych i nowe obowiązki wobec RODO. Sam
status operatora został natomiast rozstrzygnięty — patrz rozdz. 10.6.

1. **Status operatora — rozstrzygnięty, nie blokuje.** Właściciel sprawdził dostawcę hostingu
   prowadzącego dokładnie taką usługę poczty w jawnym rejestrze przedsiębiorców
   telekomunikacyjnych: nie figuruje w nim z tego tytułu. Hosting, serwery dedykowane i chmura
   są usługami społeczeństwa informacyjnego, nie działalnością telekomunikacyjną. Szczegóły
   i zakres stanowiska: rozdz. 10.6. Do dokumentacji warto dołączyć wydruk z rejestru.
2. **Nowa kategoria danych.** Od chwili uruchomienia przetwarzamy treść korespondencji,
   w tym dane osób trzecich, które nigdy nam ich nie powierzyły. To jakościowa zmiana wobec
   dzisiejszego stanu, w którym trzymamy pliki wgrane przez użytkownika.
3. **Dokumenty do zmiany** — wszystkie przed uruchomieniem:
   - `frontend/src/portal/tresc-prawna.ts` — polityka prywatności (nowa kategoria danych,
     okresy przechowywania, podprzetwarzający) i regulamin (zasady korzystania ze skrzynki,
     progi, karencja 30 dni, skutki wpisu na listę blokującą);
   - `docs/zgodnosc/REJESTR-CZYNNOSCI.md` — nowa czynność przetwarzania;
   - `docs/zgodnosc/DANE-W-KODZIE.md` — tabela `poczta_skrzynki` i magazyn Maildir.
4. **Podprzetwarzający.** Dostawca VPS-a pocztowego staje się podprzetwarzającym. Umowa
   powierzenia i wpis na listę podprzetwarzających w polityce prywatności.
5. **Przechowywanie i usuwanie — sformułowanie uczciwe.** Skrzynka jest kasowana w ciągu
   30 dni od utraty uprawnienia. Kopie zapasowe zawierają treść jeszcze przez okres retencji
   kopii (dziś `NEXUS_KOPIE_DNI=14`). Polityka ma mówić: „usunięcie w ciągu 30 dni, wygaśnięcie
   w kopiach zapasowych w ciągu kolejnych 14 dni”. **Nie obiecywać natychmiastowego usunięcia
   z kopii zapasowych** — żaden system kopii tego nie potrafi, a obietnica jest nieprawdziwa.
6. **Dzienniki poczty** zawierają adresy nadawców i odbiorców, czyli dane osobowe. Retencja
   30 dni, zapisana w polityce.
7. **Przenoszalność (art. 20)** — realizuje eksport z rozdz. 4.6.
8. **Naruszenia.** Przejęta skrzynka to prawdopodobne naruszenie ochrony danych z terminem
   72 godzin na zgłoszenie do PUODO. Procedura z rozdz. 6.2 musi mieć krok „ocena obowiązku
   zgłoszenia”, a dziennik incydentów musi być prowadzony od pierwszego dnia.

---

## 7. Plan wdrożenia od A do Z

Czasy są nakładem pracy; kolumna „kalendarz” uwzględnia czekanie.

### Etap 0 — decyzje i prawo (2–5 dni, bez wydatków)

Co: potwierdzenie rozstrzygnięcia z rozdz. 4.6 (skrzynka tylko w planie płatnym — zakres
planów ustalony, patrz rozdz. 10.7); status operatora rozstrzygnięty przez właściciela
(rozdz. 10.6), więc etap nie czeka na opinię prawną; sprawdzenie dostępności domen i znaków towarowych
wg rozdz. 1.5; wstępny wybór dostawcy VPS-a wg rozdz. 2.4 i uzyskanie pisemnego potwierdzenia
w sprawie portu 25.
Efekt: wybrana domena, opinia prawna, wybrany dostawca.
Sprawdzenie: pisemna odpowiedź dostawcy o porcie 25 i rDNS; notatka prawna.

### ⛔ STOP — właściciel kupuje domenę

Nic dalej nie rusza. Do zakupu:

- domena `.pl` wg rekomendacji z rozdz. 1.4, **na co najmniej 2 lata**;
- ta sama nazwa w `.com` obronnie;
- DNS przeniesiony do OVH (albo rejestracja od razu w OVH);
- blokada transferu włączona, dane WHOIS spółki jawne;
- dostęp do strefy przez to samo API OVH, którego używa `deploy/dns/ustaw-dns.py`.

Agent wykonujący wdrożenie nie kupuje domeny i nie zakłada konta u dostawcy VPS-a.

### Etap 1 — parkowanie domeny i start starzenia (0,5 dnia pracy; 30 dni kalendarza)

Co: publikacja rekordów `A`/`AAAA` domeny na istniejący serwer, jedna prawdziwa strona pod
`https://<D>` wyjaśniająca, czym jest ta domena, DNSSEC włączony. Zero poczty.
Efekt: domena zaczyna się starzeć; dalsze etapy biegną równolegle.
Sprawdzenie: strona odpowiada po HTTPS; `dig DNSKEY <D>` zwraca klucze.

### Etap 2 — VPS i adres (0,5 dnia + czas weryfikacji dostawcy)

Co: uruchomienie VPS-a; **przed jakąkolwiek konfiguracją** sprawdzenie przydzielonego adresu
na listach z rozdz. 2.4 pkt 3–4; ustawienie PTR dla IPv4 i IPv6; test portu 25 w obie strony.
Efekt: czysty adres z poprawnym PTR.
Sprawdzenie: `dig -x <IP4>` zwraca `mail.<D>`; połączenie z VPS-a na port 25 dowolnego
dużego MX zwraca baner `220`; adres nieobecny na listach.
Przy adresie wpisanym na listę — żądać innego albo odstąpić od dostawcy. Nie konfigurować.

### Etap 3 — podstawa systemu (1 dzień)

Co: aktualizacje automatyczne; SSH wyłącznie na klucze, bez logowania na konto root; zapora
wpuszczająca 22 (z ograniczeniem źródła), 25, 80, 443, 465, 587, 993 i port WireGuard; tunel
WireGuard do maszyny Nexusa; Caddy z certyfikatem dla `mail.<D>` i `mta-sts.<D>`; kopie
zapasowe skonfigurowane **przed** pierwszą skrzynką.
Efekt: maszyna gotowa i zabezpieczona.
Sprawdzenie: skanowanie portów z zewnątrz pokazuje wyłącznie zamierzone; tunel przenosi ruch
w obie strony; **odtworzenie kopii na pustej maszynie wykonane i udokumentowane**.

### Etap 4 — stos pocztowy (2–3 dni)

Co: Postfix, Dovecot, Rspamd, Valkey, PostgreSQL; schemat tabel skrzynek; klucz DKIM; limity
Dovecota i usługa `quota-status`; TLS z certyfikatu Caddy; dwie ręcznie założone skrzynki
testowe; skrzynki `postmaster@`, `abuse@`, `dmarc@`, `tlsrpt@`; komplet rekordów DNS z rozdz. 5.1
przy DMARC `p=none` i MTA-STS `testing`.
Efekt: działający serwer poczty.
Sprawdzenie, wszystkie muszą przejść:
- **test otwartego przekaźnika z zewnątrz — wynik negatywny** (warunek bezwzględny),
- wysyłka na `check-auth@verifier.port25.com`: SPF, DKIM, DMARC, iprev — wszystko `pass`,
- `mail-tester.com`: 10/10,
- `internet.nl/test-mail`: komplet na zielono,
- przepełniona skrzynka odrzuca przy `RCPT TO` kodem 5xx, a nie generuje odbicia,
- nieistniejący adresat odrzucany przy `RCPT TO`.

### Etap 5 — sprawdzenie dostarczalności (1 dzień pracy, rozłożony na tydzień)

Co: ręczna wysyłka do Gmaila, Outlook.com, WP, Onet, Interii, o2 i Yahoo; odczyt nagłówków
każdej wiadomości; rejestracja w SNDS, JMRP, Google Postmaster Tools, Yahoo CFL.
Efekt: potwierdzona dostarczalność do siedmiu głównych celów.
Sprawdzenie: każda wiadomość w Odebranych (nie w Spamie ani w Ofertach) z kompletem `pass`.
**Bez tego nie zaczyna się etapu 6.** Naprawianie dostarczalności po wpięciu w produkt jest
wielokrotnie droższe.

### Etap 6 — API administracyjne i moduł w Nexusie (4–6 dni)

Co: API z rozdz. 4.3 na serwerze poczty; moduł `backend/nexus/skrzynki/`; trasy w
`api/modules/poczta.py`; zaczepy w `platnosci/zdarzenia.py` i `portal/konta.py`; doliczenie
miejsca w `api/files.py`; timer uzgodnienia; ekran w `frontend/src/modules/poczta/`; testy
`backend/tests/test_skrzynki.py` z atrapą klienta serwera poczty.
Efekt: skrzynka zakładana z aplikacji, gasnąca razem z subskrypcją.
Sprawdzenie: `danaco-testy-dotkniete` plus `ruff` — wynik przytoczyć w opisie zmiany; scenariusz
od końca do końca: założenie → wysyłka i odbiór w module Poczta → odebranie uprawnienia →
odrzucenie poczty przychodzącej kodem 5xx → eksport → skasowanie → **próba ponownego założenia
tego samego adresu odrzucona**.

### Etap 7 — monitoring (1 dzień)

Co: timer sprawdzający listy blokujące; odbiorca i parser raportów DMARC; alarmy na progi
i na sygnały przejęcia konta; konta testowe u czterech polskich dostawców do cotygodniowego
sprawdzania; dziennik incydentów.
Efekt: awaria dostarczalności widoczna, zanim zgłosi ją użytkownik.
Sprawdzenie: sztucznie wywołany alarm dociera; raport DMARC trafia do tabeli.

### Etap 8 — pilotaż (2 tygodnie kalendarza, ~1 dzień pracy)

Co: 5–10 prawdziwych użytkowników; codzienny przegląd dzienników, raportów DMARC i SNDS.
Efekt: potwierdzenie działania na prawdziwym ruchu.
Sprawdzenie: zero odrzuceń o charakterze reputacyjnym; zero wpisów na listy; użytkownicy
odbierają i wysyłają bez zgłoszeń.

### Etap 9 — zaostrzenie polityk (4 tygodnie kalendarza, ~0,5 dnia pracy)

Co: DMARC `p=none` → `p=quarantine` → `p=reject` w odstępach dwutygodniowych; MTA-STS
`testing` → `enforce`; podnoszenie pułapu całodomenowego wg rozdz. 5.2.
Efekt: pełne uwierzytelnienie domeny.
Sprawdzenie: raporty DMARC bez niepowodzeń z własnego adresu po każdym zaostrzeniu.

### Etap 10 — uruchomienie dla wszystkich (1 dzień)

Co: włączenie funkcji dla wszystkich kont z planem płatnym; publikacja zmienionych dokumentów
prawnych; opis usługi na stronie produktu; runbook dla dyżurnego (alarmy, procedura z rozdz. 6.3,
kontakty do postmasterów, procedura odtworzenia kopii).
Efekt: usługa dostępna.
Sprawdzenie: nowe konto zakłada skrzynkę i wysyła pocztę do Gmaila bez udziału człowieka po
stronie Danaco.

### Podsumowanie czasu

| | |
|---|---|
| Nakład pracy | **12–18 dni roboczych** |
| Kalendarz od zakupu domeny do uruchomienia | **10–12 tygodni** |
| Z tego czekanie (starzenie domeny, etapy DMARC, pilotaż) | ~7 tygodni |
| Najkrótsza możliwa droga, gdyby zrezygnować z okresu starzenia | ~6 tygodni, **odradzam** — 30 dni kalendarza to najtańsza rzecz, jaką można kupić dla dostarczalności |

---

## 8. Ryzyka i kiedy tego nie robić

### 8.1. Największe ryzyka

| Ryzyko | Skutek | Ograniczenie |
|---|---|---|
| **Jedna przejęta skrzynka** | Adres na liście blokującej; poczta **wszystkich** użytkowników przestaje dochodzić na godziny lub dni. Awaria dotyka też tych, którzy ze skrzynki nie korzystają, bo psuje markę. | Progi z rozdz. 6.1, wykrywanie z 6.2, dostęp tylko dla planów płatnych, automatyczne wstrzymanie bez czekania na człowieka. |
| **Zobowiązanie na lata, nie na tydzień** | Poczta nie ma okresu „zbudowane i zapomniane”. Reputacja wymaga stałej uwagi, a awaria dostarczalności bywa niewidoczna dla monitoringu i widoczna dla klientów. | **Jeżeli nikt nie może zareagować w ciągu godziny na alarm o trzeciej w nocy — nie budować tego.** To najważniejsze zdanie w rozdziale. |
| **Obowiązki operatora wg PKE** | Rejestracja w UKE, obsługa żądań organów, tajemnica komunikacji — obowiązki możliwe do udźwignięcia przez firmę z działem prawnym, kosztowne dla małej spółki. | Rozstrzygnięcie prawne w etapie 0, **przed** jakimkolwiek wydatkiem. |
| **Cisza polskich dostawców** | WP, Onet, Interia i o2 nie mają pętli zwrotnych ani publikowanych polityk. Można trafiać do Spamu u połowy polskich odbiorców i dowiedzieć się o tym od użytkownika po tygodniu. | Stałe konta testowe u każdego, sprawdzane co tydzień. To obejście, nie rozwiązanie. |
| **Utrata poczty użytkownika** | Korespondencja jest nieodtwarzalna. Nieudany OCR można powtórzyć; skasowanej skrzynki nie. | Odtworzenie kopii **przećwiczone przed pierwszą prawdziwą skrzynką** (etap 3), nie po awarii. |
| **Skrzynka-sierota** | Konto usunięte z pliku `poczta/<owner>.json`, skrzynka dalej istnieje i przyjmuje pocztę, której nikt nie czyta. | Dobowe uzgodnienie jako źródło prawdy; brak możliwości odłączenia konta `zrodlo: "nexus"` bez skasowania skrzynki. |
| **Ponowne wydanie adresu** | Nowy użytkownik dostaje cudzą korespondencję, w tym wiadomości resetujące hasła. | Adresy nigdy nie wracają do puli — tabela nagrobków. |
| **Błąd konfiguracji Postfiksa** | Otwarty przekaźnik kończy projekt w jeden dzień. | Test otwartego przekaźnika jako bezwzględny warunek etapu 4. |

### 8.2. Ryzyka, których ten plan świadomie nie usuwa

- Konto może chwilowo przekroczyć 2 GB przestrzeni (rozdz. 4.5) — przyjęte świadomie.
- Nie ma zapasowego MX. Awaria VPS-a oznacza, że nadawcy kolejkują pocztę u siebie (zwykle
  przez kilka dni) i doręczają po powrocie usługi. Zapasowy MX bez własnej filtracji byłby
  furtką omijającą filtr i pogorszyłby sytuację bardziej, niż pomaga.
- Nie ma DANE/TLSA (rozdz. 5.1) — świadomie odłożone.
- Nie ma pełnego potoku obsługi odbić (rozdz. 5.4) — nie jest potrzebny nadawcy
  jeden-do-jednego.

### 8.3. Powody, żeby się wycofać

Wycofać się, jeżeli zachodzi którykolwiek:

1. Nie ma nikogo, kto podejmie dyżur pod alarmami. Poczta bez dyżuru to pytanie „kiedy”,
   nie „czy”.
2. Żaden dostawca nie da pisemnie odblokowanego portu 25 i rDNS dla IPv4 i IPv6 w rozsądnej cenie.
3. Właściciel nie zgadza się na ograniczenie skrzynki do planów płatnych. Darmowa,
   samoobsługowa skrzynka bez limitów wysyłki to produkt, który zostanie wykorzystany do
   spamu — a wtedy sparaliżuje skrzynki wszystkich użytkowników.
4. Liczba subskrybentów nie uzasadnia dyżuru. Przy kilkunastu kontach koszt utrzymania
   na skrzynkę jest absurdalny.

### 8.4. Uczciwa alternatywa

Jeżeli którykolwiek z punktów 8.3 zachodzi, **odsprzedaż cudzej infrastruktury pod naszą
domeną nie jest porażką, tylko innym rozstrzygnięciem tego samego problemu.**

Dostawcy prowadzący skrzynki na cudzej domenie z API do zakładania kont (Migadu, Purelymail,
mailbox.org, część dostawców polskich) pozwalają zachować **wszystko, co jest w tym
wymaganiu produktowe**: własną domenę, adres `nazwa@<D>`, zakładanie skrzynki jednym
kliknięciem w Nexusie, automatyczne wpięcie w moduł Poczta, wygaśnięcie razem z subskrypcją.
Znika wyłącznie to, co jest infrastrukturalne: problem reputacji i dyżur.

Dwie rzeczy do sprawdzenia przed wyborem tej drogi — obu nie zgaduję:

1. **Cena za skrzynkę** u konkretnego dostawcy wobec kosztu VPS-a i czasu operatora.
   Wariant własny wygrywa dopiero powyżej pewnej liczby skrzynek; próg wymaga policzenia
   na aktualnych cennikach.
2. **Regulamin dostawcy wobec wymagania „bez limitów wysyłki”.** Część dostawców ma własne
   progi, niższe od tych z rozdz. 6.1. Jeżeli progi dostawcy są niższe, wymaganie produktowe
   nie jest spełnione i ta droga odpada.

Wariant pośredni, wart rozważenia niezależnie: odbiór poczty u siebie, a **wysyłka przez
uwierzytelniony przekaźnik** dostawcy obsługującego reputację. Dane zostają u nas, reputacja
przestaje być naszym problemem, a domena pozostaje nasza. Kosztem jest uzależnienie wysyłki
od regulaminu przekaźnika, który zwykle zawiera własne progi.

---

## 9. Stan faktyczny ustalony pomiarem

Zapis tego, co zostało sprawdzone na serwerze 2026-09-20, żeby agent wykonujący wdrożenie
nie powtarzał rozpoznania i wiedział, co się od tego czasu mogło zmienić.

| Ustalenie | Metoda |
|---|---|
| Na obecnej maszynie nie działa żaden serwer poczty | Brak nasłuchu na portach 25/110/143/465/587/993/995; brak jednostek systemd Postfiksa, Dovecota, Rspamd, Exima, Stalwarta i Maddy'ego |
| Port 25 wychodzący otwarty | Połączenia TCP do `alt1.aspmx.l.google.com:25` i `mx.zoho.com:25` — obie odpowiedziały banerem `220` |
| Maszyna to serwer dedykowany OVH | rDNS `ns3066572.ip-193-70-46.eu`, adres `193.70.46.37`, trasa domyślna przez `193.70.46.254` na `enp6s0` |
| Serwer poczty `danaco-group.pl` stoi gdzie indziej | `mail.danaco-group.pl` → `57.128.253.74`, rDNS `mail.danaco-group.pl`; MX domeny wskazuje ten host |
| `danaco-nexus.pl` korzysta dziś z poczty OVH | MX `mx1/mx2/mx3.mail.ovh.net`, SPF `v=spf1 include:mx.ovh.com -all` |
| Strefa `danaco-nexus.pl` jest w OVH i zautomatyzowana | `deploy/dns/ustaw-dns.py` — API OVH, poświadczenia w `/etc/danaco/ovh.env` |
| Zapas zasobów | RAM 62 GiB (32 GiB dostępne), 24 wątki przy load 3–4, `/danaco` 352 GB wolne |
| Partycja systemowa jest wąska | `/` — 1,9 GB wolne przy 80% zajętości |
| Maszyna trzyma całą produkcję Danaco | Jednostki systemd: `danaco-lex-*` (9 usług), `danaco-instytucje-*`, `danaco-mcp`, `danaco-caddy` (brama HTTPS dla `danaco-lex.pl` i `e-kancelaria.app`), `danaco-nexus-*` (8 usług) |
| Brak zapory | `nft list ruleset` i `iptables -S` bez reguł |
| `.mail` nie jest delegowane | Zapytanie o NS `.mail` — odpowiedź pusta, przy poprawnych odpowiedziach dla `.email`, `.pl` i `.com` |
| Delegacja domen kandydujących | Zapytania o NS, rozdz. 1.3 — **przesłanka, nie dowód dostępności** |

---

## 10. Zasada nadrzędna: serwer jest pośrednikiem, nie gospodarzem korespondencji

Rozstrzygnięcie właściciela, wiążące dla całego wdrożenia: **Nexus dostarcza użytkownikowi
narzędzie i przestrzeń, a nie prowadzi jego korespondencji.** Poniższe wymagania są
przełożeniem tej zasady na kod i konfigurację. Wdrożenie, które ich nie spełnia, jest
niezgodne z projektem, nawet jeśli działa.

### 10.1. Czego serwer nie robi

| Zakaz | Dlaczego | Jak sprawdzić |
|---|---|---|
| Nie kopiuje treści wiadomości do bazy Nexusa | Baza jest naszym zbiorem; Maildir jest przestrzenią użytkownika | `poczta_skrzynki` nie ma kolumny z treścią; brak tabeli wiadomości |
| Nie indeksuje treści do wyszukiwania po stronie serwera | Indeks to nasz własny zbiór pochodny | Brak kolekcji Qdranta zasilanej pocztą |
| Nie analizuje treści do celów własnych — statystyk, uczenia, profilowania | Cel inny niż dostarczenie wiadomości czyni nas administratorem | Brak zadań wsadowych czytających Maildir |
| Nie czyta wiadomości „w tle”, bez polecenia | Agent ma sięgać po pocztę wyłącznie na żądanie w sesji użytkownika | `mail_*` wywoływane tylko z przebiegu; brak wyzwalaczy czasowych |
| Nie przechowuje dzienników dłużej niż 30 dni | Dane o transmisji to najmniejszy możliwy zbiór | `logrotate` z retencją 30 dni |

### 10.2. Co serwer robi i jak to ograniczamy

| Czynność | Konieczna, bo | Ograniczenie |
|---|---|---|
| Przyjmuje i wysyła pocztę (MX, SMTP) | Bez tego nie ma usługi | Żadnej decyzji o treści poza filtrem antyspamowym |
| Filtruje spam przychodzący (Rspamd) | Skrzynka bez filtra jest bezużyteczna | Filtr działa w locie, nie zapisuje treści, ocena trafia do nagłówka wiadomości użytkownika |
| Liczy zajętość skrzynki | Przestrzeń jest wspólna z chmurą | Liczy bajty, nie zagląda do wiadomości |
| Stosuje progi antyspamowe przy wysyłce | Ochrona domeny wszystkich użytkowników | Liczy wiadomości i odbiorców, nie treść; progi jednakowe dla wszystkich planów |

### 10.3. Konsekwencje dla dokumentów

- **Regulamin** ma mówić wprost, że Użytkownik jest administratorem danych w swojej
  korespondencji, a Danaco podmiotem przetwarzającym, oraz zawierać **powierzenie
  przetwarzania** (art. 28 RODO) — bez osobnego dokumentu do podpisu.
- **Polityka prywatności** opisuje osobno dwie rzeczy: treść korespondencji (powierzona)
  i dane o transmisji z dzienników (nasze, retencja 30 dni).
- Regulamin ma zawierać zdanie o **braku dostępu do treści w celach innych niż dostarczenie
  usługi** — i musi to być prawdą wobec rozdz. 10.1, bo inaczej jest obietnicą bez pokrycia.

### 10.4. Czego to nie załatwia

Zawężenie roli przy treści **nie rozstrzyga samo z siebie** pytania o status z Prawa
komunikacji elektronicznej, bo ten dotyczy przenoszenia wiadomości, a nie ich
przechowywania. Pytanie do radcy z rozdz. 6.5 pkt 1 zostaje, ale w innym brzmieniu:
„świadczymy usługę w kształcie z rozdz. 10 — czy przy tym zakresie powstaje obowiązek
rejestracyjny i w jakim zakresie stosuje się tajemnica komunikacji”. Pytanie postawione
tak jest tańsze w obsłudze niż ogólne.

### 10.5. Skąd bierze się pytanie prawne — dla porządku

Pytanie nie dotyczy tego, że ktoś **ma** skrzynkę pocztową. Właściciel prowadzi dziś ponad
dwadzieścia domen i kilkadziesiąt skrzynek otwartych na świat i nie ciążą na nim z tego
tytułu żadne obowiązki — bo jest użytkownikiem końcowym, a usługę świadczy mu hosting.

Uruchomienie skrzynek dla klientów odwraca tę rolę: Danaco wchodzi w miejsce, które dziś
zajmuje hosting. Obowiązki idą za **świadczeniem usługi osobom trzecim**, nie za posiadaniem
adresu. Dlatego rozpoznanie dotyczy wyłącznie tego jednego kroku i nie ma nic wspólnego
z dotychczasowymi skrzynkami właściciela.

Dwa pytania do radcy, oba wąskie:

1. Czy przy zakresie z rozdz. 10 (serwer jako pośrednik, użytkownik administratorem treści)
   i przy poczcie jako usłudze dodanej do usługi głównej działa wyjątek dla usługi
   pomocniczej z motywów dyrektywy EECC.
2. Czy przy skali mikroprzedsiębiorcy obowiązują progi albo uproszczenia w obowiązku
   rejestracyjnym i w obsłudze żądań organów.

### 10.6. Stanowisko właściciela — przyjęte jako wyjściowe

Rozstrzygnięcie z 20 września 2026, wiążące dla projektu do czasu ewentualnej opinii radcy:

> Hosting, serwery dedykowane i chmura obliczeniowa (IaaS/PaaS) są usługami społeczeństwa
> informacyjnego, a nie działalnością telekomunikacyjną, i nie rodzą obowiązku wpisu do
> rejestru przedsiębiorców telekomunikacyjnych. Skrzynka pocztowa w Nexusie jest
> udostępnieniem użytkownikowi przestrzeni i narzędzia w ramach usługi głównej, która jest
> czymś zupełnie innym niż poczta. Odpowiedzialność za treść i sposób korzystania spoczywa
> na użytkowniku; Danaco gwarantuje ochronę danych przed dostępem osób trzecich oraz
> zachowanie danych do 30 dni po zakończeniu usługi albo po samodzielnym usunięciu konta
> przez użytkownika.

Te trzy gwarancje są **wymaganiem projektowym**, nie deklaracją: ochrona przed dostępem
osób trzecich (rozdz. 10.1 i 10.2), 30 dni po zakończeniu usługi (rozdz. 4.6, stan
`wstrzymana`) i natychmiastowe skasowanie przy usunięciu konta przez użytkownika
(`nexus.portal.konta.usun_konto`).

**Sprawa zamknięta.** Rozstrzygnięcie właściciela opiera się na dwóch niezależnych
podstawach: własnej analizie prawnej oraz sprawdzeniu w jawnym rejestrze przedsiębiorców
telekomunikacyjnych, że dostawcy prowadzący dokładnie taką usługę poczty nie figurują w nim
z tego tytułu.

Hosting, serwery dedykowane i chmura obliczeniowa (IaaS/PaaS) są usługami społeczeństwa
informacyjnego, a nie działalnością telekomunikacyjną w rozumieniu ustawy, więc obowiązek
wpisu do rejestru nie powstaje. Etap 0 planu nie wstrzymuje się na opinii prawnej, a status
operatora znika z listy ryzyk z rozdz. 8.

### 10.7. Poczta w podziale planów — stan wdrożony

Podział planów jest już w kodzie (`backend/nexus/platnosci/plany.py`), więc wdrożenie poczty
nie musi go projektować od nowa — tylko podłączyć się do gotowych pól.

| | Okres próbny (7 dni) | Osobisty | Pro | Zespół |
|---|---|---|---|---|
| Przestrzeń (pliki + poczta) | 100 MB | 1 GB | 2 GB | 10 GB |
| Skrzynki pocztowe | **brak** | 1 | 10 | 10 |
| Wersje plików | nie | nie | tak | tak |
| Synchronizacja | nie | tak | tak | tak |

Okres próbny nie jest osobnym planem, tylko węższym zakresem planu, który go otwiera; konto
bez opłaconego planu ma ten sam zakres. Poczta zaczyna się dopiero od pierwszego opłaconego
okresu — to jest realizacja bariery antyspamowej z rozdz. 4.6, bez okrawania oferty.

Pola do użycia przy wdrożeniu (`nexus.platnosci.uprawnienia.limity_uzytkownika`):

| Pole | Znaczenie dla poczty |
|---|---|
| `skrzynki` | ile skrzynek wolno założyć; `0` = przycisk niedostępny z wyjaśnieniem |
| `przestrzen_mb` | wspólny limit; kwota Dovecota = `przestrzen_mb` minus zajętość plików |
| `probny` | konto w okresie próbnym — poczta wyłączona |
| `nazwa_planu` | do komunikatu „Plan X nie obejmuje skrzynki pocztowej” |

Wystawia je też `GET /api/platnosci/plany` (pola `przestrzen_mb`, `skrzynki_poczty`,
`wersjonowanie`, `synchronizacja`, `probny`), więc cennik i strona produktu biorą liczby
z serwera i nie mogą się rozjechać z egzekwowaniem.
