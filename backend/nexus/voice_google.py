"""Mowa przez Google Cloud: synteza (Text-to-Speech, głosy Chirp 3 HD) i rozpoznawanie (Speech-to-Text).

Uwierzytelnianie kluczem API projektu Google Cloud (plik ``voice_google_key_file``,
prawa 600). Klucz musi mieć włączone interfejsy Cloud Text-to-Speech API
i Cloud Speech-to-Text API. Nagrania z przeglądarki (webm/opus, mp4/aac) są
przed wysłaniem zamieniane FFmpeg na 16 kHz mono PCM.
"""

from __future__ import annotations

import base64
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TTS_URL = "https://texttospeech.googleapis.com/v1"
STT_URL = "https://speech.googleapis.com/v1/speech:recognize"
LANGUAGE = "pl-PL"
# Najbardziej naturalne głosy najpierw; starsze rodziny tylko, gdy Chirp 3 HD jest niedostępny.
VOICE_FAMILIES = ("Chirp3-HD", "Chirp-HD", "Neural2", "Wavenet")
VOICES_TTL_SECONDS = 6 * 3600
TIMEOUT = httpx.Timeout(20.0, connect=5.0)
GENDERS = {"FEMALE": "kobieta", "MALE": "mężczyzna"}


class GoogleSpeechError(RuntimeError):
    """Błąd usługi mowy Google (klucz, uprawnienia, limit, sieć)."""


def read_key(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _voice_label(voice: dict[str, Any]) -> str:
    """Nazwa głosu do wyboru w interfejsie, np. „Aoede (kobieta)”."""
    gender = GENDERS.get(voice.get("ssmlGender", ""), "głos")
    return f"{voice['name'].rsplit('-', 1)[-1]} ({gender})"


class GoogleSpeech:
    """Klient REST usług mowy Google Cloud."""

    def __init__(self, key_file: Path, ffmpeg: str = "ffmpeg") -> None:
        self._key_file = key_file
        self._ffmpeg = ffmpeg
        self._http = httpx.Client(timeout=TIMEOUT)
        self._voices: list[dict[str, str]] = []
        self._voices_at = 0.0
        self._lock = threading.Lock()

    def available(self) -> bool:
        return bool(read_key(self._key_file))

    def _key(self) -> str:
        key = read_key(self._key_file)
        if not key:
            raise GoogleSpeechError(f"Brak klucza Google Cloud ({self._key_file}).")
        return key

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.post(url, json=payload, headers={"x-goog-api-key": self._key()})
        except httpx.HTTPError as error:
            raise GoogleSpeechError(f"Brak połączenia z Google Cloud: {error.__class__.__name__}") from error
        if response.status_code != 200:
            try:
                message = response.json().get("error", {}).get("message", "")
            except ValueError:
                message = response.text[:200]
            raise GoogleSpeechError(f"Google Cloud HTTP {response.status_code}: {message[:300]}")
        return response.json()

    # --- synteza ---------------------------------------------------------------------------

    def voices(self) -> list[dict[str, str]]:
        """Polskie głosy (najlepsza dostępna rodzina), z pamięcią podręczną."""
        with self._lock:
            if self._voices and time.monotonic() - self._voices_at < VOICES_TTL_SECONDS:
                return self._voices
            try:
                response = self._http.get(
                    f"{TTS_URL}/voices",
                    params={"languageCode": LANGUAGE},
                    headers={"x-goog-api-key": self._key()},
                )
                response.raise_for_status()
                listed = response.json().get("voices", [])
            except (httpx.HTTPError, GoogleSpeechError) as error:
                logger.warning("Nie udało się pobrać listy głosów Google: %s", error)
                return self._voices
            for family in VOICE_FAMILIES:
                chosen = [voice for voice in listed if f"-{family}-" in voice.get("name", "")]
                if chosen:
                    break
            self._voices = [
                {"id": f"google:{voice['name']}", "name": _voice_label(voice)}
                for voice in sorted(
                    chosen, key=lambda item: (item.get("ssmlGender") != "FEMALE", item["name"])
                )
            ]
            self._voices_at = time.monotonic()
            return self._voices

    def speak(self, text: str, voice_id: str, speed: float = 1.0) -> bytes:
        """Synteza do MP3."""
        name = voice_id.removeprefix("google:")
        payload = {
            "input": {"text": text},
            "voice": {"languageCode": LANGUAGE, "name": name},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": max(0.5, min(speed, 2.0))},
        }
        data = self._post(f"{TTS_URL}/text:synthesize", payload)
        return base64.b64decode(data["audioContent"])

    # --- rozpoznawanie ---------------------------------------------------------------------

    def _pcm16k(self, audio: Path) -> bytes:
        completed = subprocess.run(
            [
                self._ffmpeg,
                "-loglevel",
                "error",
                "-i",
                str(audio),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "-",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            raise ValueError("Nie udało się odczytać nagrania.")
        return completed.stdout

    def transcribe(self, audio: Path, language: str = "pl") -> tuple[str, float]:
        """Rozpoznanie krótkiej wypowiedzi (do ok. minuty); zwraca tekst i czas trwania."""
        pcm = self._pcm16k(audio)
        duration = len(pcm) / 32000
        if duration < 0.2:
            return "", duration
        payload = {
            "config": {
                "encoding": "LINEAR16",
                "sampleRateHertz": 16000,
                "languageCode": LANGUAGE if language in ("pl", "auto") else language,
                "model": "latest_short" if duration < 20 else "latest_long",
                "enableAutomaticPunctuation": True,
            },
            "audio": {"content": base64.b64encode(pcm).decode("ascii")},
        }
        data = self._post(STT_URL, payload)
        text = " ".join(
            result["alternatives"][0].get("transcript", "").strip()
            for result in data.get("results", [])
            if result.get("alternatives")
        ).strip()
        return text, duration

    def close(self) -> None:
        self._http.close()
