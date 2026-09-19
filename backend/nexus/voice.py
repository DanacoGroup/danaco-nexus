"""Rozmowa głosowa: rozpoznawanie mowy (faster-whisper) i synteza mowy (Piper).

Modele są ładowane raz, przy pierwszym użyciu, i pozostają w pamięci procesu
API – krótkie wypowiedzi rozpoznaje się w ułamku sekundy do kilku sekund.
Obliczenia działają w wątkach (``asyncio.to_thread``), a dostęp do każdego
modelu jest szeregowany blokadą.
"""

from __future__ import annotations

import io
import logging
import re
import threading
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus.config import Settings

logger = logging.getLogger(__name__)

VOICE_NAMES = {
    "pl_PL-gosia-medium": "Gosia",
    "pl_PL-mc_speech-medium": "Magda",
    "pl_PL-darkman-medium": "Marek",
}
MARKDOWN = re.compile(
    r"(\*\*|__|`{1,3}|^#{1,6}\s*|^\s*[-*+]\s+|^\s*\d+\.\s+|\[([^\]]*)\]\([^)]*\))", re.MULTILINE
)


class VoiceUnavailable(RuntimeError):
    """Brak modelu rozpoznawania lub syntezy mowy."""


@dataclass(slots=True)
class Transcript:
    text: str
    language: str
    duration: float


def spoken_text(text: str) -> str:
    """Tekst do przeczytania: bez znaczników Markdown, adresów i nadmiarowych odstępów."""
    text = MARKDOWN.sub(lambda match: match.group(2) or "", text)
    text = re.sub(r"https?://\S+", "link", text)
    text = text.replace("|", " ").replace("–", ", ").replace("—", ", ")
    return re.sub(r"\s+", " ", text).strip()


class VoiceEngine:
    """Modele mowy współdzielone przez żądania API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._stt: Any = None
        self._voices: dict[str, Any] = {}
        self._stt_lock = threading.Lock()
        self._tts_lock = threading.Lock()

    # --- rozpoznawanie mowy ---------------------------------------------------------------

    @property
    def stt_model_dir(self) -> Path:
        return self._settings.voice_stt_model_dir

    def stt_available(self) -> bool:
        return (self.stt_model_dir / "model.bin").is_file()

    def _load_stt(self) -> Any:
        if self._stt is None:
            if not self.stt_available():
                raise VoiceUnavailable(f"Brak modelu rozpoznawania mowy w {self.stt_model_dir}.")
            from faster_whisper import WhisperModel

            logger.info("Ładowanie modelu rozpoznawania mowy %s", self.stt_model_dir)
            self._stt = WhisperModel(
                str(self.stt_model_dir),
                device="cpu",
                compute_type="int8",
                cpu_threads=self._settings.voice_threads,
            )
        return self._stt

    def transcribe(self, audio: Path, language: str = "pl") -> Transcript:
        """Rozpoznaje wypowiedź z pliku audio (webm/opus, mp4/aac, wav…)."""
        with self._stt_lock:
            model = self._load_stt()
            segments, info = model.transcribe(
                str(audio),
                language=None if language == "auto" else language,
                beam_size=1,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        return Transcript(text=text, language=info.language, duration=round(info.duration, 2))

    # --- synteza mowy ---------------------------------------------------------------------

    def voices(self) -> list[dict[str, str]]:
        directory = self._settings.voice_tts_dir
        found = []
        for model in sorted(directory.glob("*.onnx")) if directory.is_dir() else []:
            if model.with_suffix(".onnx.json").is_file():
                found.append({"id": model.stem, "name": VOICE_NAMES.get(model.stem, model.stem)})
        return found

    def default_voice(self) -> str:
        available = [voice["id"] for voice in self.voices()]
        preferred = self._settings.voice_default
        return preferred if preferred in available else (available[0] if available else "")

    def _load_voice(self, voice_id: str) -> Any:
        if voice_id not in self._voices:
            model = self._settings.voice_tts_dir / f"{voice_id}.onnx"
            if not model.is_file():
                raise VoiceUnavailable(f"Brak głosu {voice_id}.")
            from piper import PiperVoice

            logger.info("Ładowanie głosu %s", voice_id)
            self._voices[voice_id] = PiperVoice.load(str(model))
        return self._voices[voice_id]

    def warm_up(self) -> None:
        """Wczytuje modele z góry (w tle przy starcie API), żeby pierwsza rozmowa nie czekała."""
        try:
            if self.stt_available():
                with self._stt_lock:
                    self._load_stt()
            voice_id = self.default_voice()
            if voice_id:
                with self._tts_lock:
                    self._load_voice(voice_id)
        except Exception:  # noqa: BLE001 - rozgrzewanie jest tylko przyspieszeniem
            logger.exception("Nie udało się wczytać modeli mowy z góry")

    def speak(self, text: str, voice_id: str = "", speed: float = 1.0) -> bytes:
        """Syntezuje tekst do pliku WAV (mono, częstotliwość modelu głosu)."""
        text = spoken_text(text)
        if not text:
            raise ValueError("Brak tekstu do przeczytania.")
        voice_id = voice_id or self.default_voice()
        with self._tts_lock:
            voice = self._load_voice(voice_id)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                _synthesize(voice, text, wav, speed)
        return buffer.getvalue()


def _synthesize(voice: Any, text: str, wav: wave.Wave_write, speed: float) -> None:
    """Synteza zgodna z API piper-tts 1.3+ (``synthesize_wav``) i starszym (``synthesize``)."""
    length_scale = 1.0 / max(0.5, min(speed, 2.0))
    if hasattr(voice, "synthesize_wav"):
        from piper import SynthesisConfig

        voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=length_scale))
    else:
        voice.synthesize(text, wav, length_scale=length_scale)
