#!/usr/bin/env bash
# Odtwarzalna budowa podpisanej aplikacji Android Nexusa (APK wydania).
#
# Użycie:  deploy/android/buduj-apk.sh [--tylko-narzedzia] [--bez-testow]
#
# Skrypt jest idempotentny. Przy pierwszym uruchomieniu instaluje w katalogu projektu
# (nigdy globalnie):
#   programy/jdk-21        – Temurin 21 (wymagany przez Capacitor 8 i AGP 8.13),
#   programy/android-sdk   – Android SDK: cmdline-tools, platform-tools, platforma i build-tools,
#   .cache/gradle, .cache/npm – pamięć podręczna Gradle i npm.
# Klucz podpisu wydania (keystore + keystore.properties z hasłem) powstaje raz w katalogu
# $KLUCZE (domyślnie .tmp/android/keystore) z prawami 600 – hasło nie jest nigdzie wypisywane.
# Utrata klucza oznacza, że kolejnych wersji nie da się zainstalować jako aktualizacji.
#
# Zmienne (opcjonalne): NEXUS_PROJEKT, JDK21_HOME, ANDROID_HOME, WYJSCIE, KLUCZE, NODE_BIN.
set -euo pipefail

PROJEKT="${NEXUS_PROJEKT:-/danaco/projekty/danaco-nexus}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROGRAMY="$PROJEKT/programy"
JDK="${JDK21_HOME:-$PROGRAMY/jdk-21}"
SDK="${ANDROID_HOME:-$PROGRAMY/android-sdk}"
WYJSCIE="${WYJSCIE:-$PROJEKT/.tmp/android/out}"
KLUCZE="${KLUCZE:-$PROJEKT/.tmp/android/keystore}"
NODE_BIN="${NODE_BIN:-/danaco/programy/node/bin}"

CMDLINE_TOOLS_ZIP="commandlinetools-linux-16111833_latest.zip"
PLATFORMA="platforms;android-36"
BUILD_TOOLS="build-tools;36.0.0"
ALIAS="nexus"

TYLKO_NARZEDZIA=0
TESTY=1
for arg in "$@"; do
    case "$arg" in
        --tylko-narzedzia) TYLKO_NARZEDZIA=1 ;;
        --bez-testow) TESTY=0 ;;
        *) echo "Nieznana opcja: $arg" >&2; exit 2 ;;
    esac
done

export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$PROJEKT/.cache/gradle}"
export npm_config_cache="${npm_config_cache:-$PROJEKT/.cache/npm}"
export ANDROID_HOME="$SDK" ANDROID_SDK_ROOT="$SDK"
# Dane użytkownika narzędzi Android (AGP, Android CLI) w katalogu projektu, nie w $HOME.
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-$PROJEKT/.cache/android-user}"
export JAVA_HOME="$JDK"
export PATH="$JDK/bin:$SDK/cmdline-tools/latest/bin:$SDK/platform-tools:$NODE_BIN:$PATH"
# Pliki tymczasowe poza małą partycją systemową.
export TMPDIR="$PROJEKT/.tmp/android/tmp"
mkdir -p "$TMPDIR" "$GRADLE_USER_HOME" "$npm_config_cache" "$PROGRAMY" "$ANDROID_USER_HOME"

krok() { printf '\n==> %s\n' "$*"; }

zainstaluj_jdk() {
    if [ -x "$JDK/bin/java" ] && "$JDK/bin/java" -version 2>&1 | grep -q '"21\.'; then
        return
    fi
    krok "Instalacja Temurin 21 w $JDK"
    local api="https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=x64&image_type=jdk&os=linux&vendor=eclipse"
    local info link sum archiwum="$TMPDIR/jdk21.tar.gz"
    info="$(curl -fsSL "$api")"
    link="$(printf '%s' "$info" | grep -o '"link": *"[^"]*\.tar\.gz"' | head -1 | sed 's/.*"\(http[^"]*\)"/\1/')"
    sum="$(printf '%s' "$info" | grep -o '"checksum": *"[0-9a-f]\{64\}"' | head -1 | grep -o '[0-9a-f]\{64\}')"
    [ -n "$link" ] && [ -n "$sum" ] || { echo "Nie udało się ustalić adresu JDK 21." >&2; exit 1; }
    curl -fsSL -o "$archiwum" "$link"
    echo "$sum  $archiwum" | sha256sum -c --quiet
    rm -rf "$JDK.nowy" && mkdir -p "$JDK.nowy"
    tar -xzf "$archiwum" -C "$JDK.nowy" --strip-components=1
    rm -rf "$JDK" && mv "$JDK.nowy" "$JDK" && rm -f "$archiwum"
}

zainstaluj_sdk() {
    if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
        krok "Instalacja Android SDK cmdline-tools w $SDK"
        local repo sum archiwum="$TMPDIR/$CMDLINE_TOOLS_ZIP"
        repo="$(curl -fsSL https://dl.google.com/android/repository/repository2-3.xml)"
        sum="$(printf '%s' "$repo" | grep -B3 "<url>$CMDLINE_TOOLS_ZIP</url>" | grep -o '[0-9a-f]\{40\}' | head -1)"
        [ -n "$sum" ] || { echo "Brak sumy kontrolnej $CMDLINE_TOOLS_ZIP w repozytorium Google." >&2; exit 1; }
        curl -fsSL -o "$archiwum" "https://dl.google.com/android/repository/$CMDLINE_TOOLS_ZIP"
        echo "$sum  $archiwum" | sha1sum -c --quiet
        rm -rf "$SDK/cmdline-tools" && mkdir -p "$SDK/cmdline-tools"
        (cd "$SDK/cmdline-tools" && unzip -q "$archiwum" && mv cmdline-tools latest)
        rm -f "$archiwum"
    fi
    if [ ! -d "$SDK/platforms/android-36" ] || [ ! -d "$SDK/build-tools/36.0.0" ] || [ ! -d "$SDK/platform-tools" ]; then
        krok "Instalacja pakietów SDK ($PLATFORMA, $BUILD_TOOLS, platform-tools)"
        # Licencja Android SDK (akceptacja wymagana przez sdkmanager i AGP do budowy).
        # Nowy sdkmanager deleguje do „Android CLI”, które rozpakowuje się w $HOME – stąd HOME w projekcie.
        yes | HOME="$ANDROID_USER_HOME" sdkmanager --sdk_root="$SDK" --licenses > /dev/null || true
        HOME="$ANDROID_USER_HOME" sdkmanager --sdk_root="$SDK" "$PLATFORMA" "$BUILD_TOOLS" "platform-tools" > /dev/null
    fi
}

klucz_podpisu() {
    local plik="$KLUCZE/keystore.properties"
    if [ -f "$plik" ] && [ -f "$KLUCZE/nexus-release.jks" ]; then
        return
    fi
    krok "Generowanie klucza podpisu wydania w $KLUCZE"
    (
        umask 077
        mkdir -p "$KLUCZE"
        local haslo="$KLUCZE/.haslo"
        head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' > "$haslo"
        keytool -genkeypair -keystore "$KLUCZE/nexus-release.jks" -storetype PKCS12 \
            -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10000 \
            -dname "CN=Danaco Nexus, O=Danaco Group, C=PL" \
            -storepass:file "$haslo" -keypass:file "$haslo" > /dev/null
        {
            echo "storeFile=$KLUCZE/nexus-release.jks"
            printf 'storePassword=%s\n' "$(cat "$haslo")"
            echo "keyAlias=$ALIAS"
            printf 'keyPassword=%s\n' "$(cat "$haslo")"
        } > "$plik"
        rm -f "$haslo"
        chmod 600 "$plik" "$KLUCZE/nexus-release.jks"
    )
}

zainstaluj_jdk
zainstaluj_sdk
if [ "$TYLKO_NARZEDZIA" = 1 ]; then
    echo "Narzędzia gotowe: JDK $JDK, SDK $SDK."
    exit 0
fi
klucz_podpisu

krok "Zależności Capacitor (npm ci) i synchronizacja projektu"
cd "$REPO/android"
npm ci --no-audit --no-fund
npx cap sync android
if [ "$TESTY" = 1 ]; then
    krok "Testy skryptów mostka WebView (Node)"
    node scripts/test-mostek.mjs
fi

krok "Budowa Gradle"
cd "$REPO/android/android"
printf 'sdk.dir=%s\n' "$SDK" > local.properties
zadania=(lintRelease assembleRelease)
if [ "$TESTY" = 1 ]; then
    zadania=(testReleaseUnitTest "${zadania[@]}")
fi
./gradlew --no-daemon --console=plain -Pnexus.keystore="$KLUCZE/keystore.properties" "${zadania[@]}"

krok "Weryfikacja podpisu i kopiowanie wyniku"
apk="app/build/outputs/apk/release/app-release.apk"
"$SDK/build-tools/36.0.0/apksigner" verify --print-certs "$apk" | grep -E 'Signer #1 certificate (DN|SHA-256)'
mkdir -p "$WYJSCIE"
cp -f "$apk" "$WYJSCIE/nexus-android.apk"
cp -f app/build/reports/lint-results-release.html "$WYJSCIE/lint-results.html" 2>/dev/null || true
sha256sum "$WYJSCIE/nexus-android.apk"
echo "Gotowe: $WYJSCIE/nexus-android.apk"
