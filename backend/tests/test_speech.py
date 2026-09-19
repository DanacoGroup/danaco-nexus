"""Testy transkrypcji mowy (faster-whisper).

Test na prawdziwym modelu syntezuje polskie zdanie programem espeak-ng i jest
pomijany, gdy brak espeak-ng, środowiska faster-whisper albo modelu.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ToolHarness

from nexus.tools import registry
from nexus.tools.base import ToolError
from nexus.tools.speech import timestamp, to_srt, to_text


def call(harness: ToolHarness, name: str, /, **arguments: object):  # type: ignore[no-untyped-def]
    tool = registry.get(name)
    return tool.handler(harness.context(), tool.parse(arguments))


def test_timestamps_and_subtitles() -> None:
    assert timestamp(0) == "00:00:00,000"
    assert timestamp(3723.456) == "01:02:03,456"
    segments = [
        {"start": 0.0, "end": 1.5, "text": "Dzień dobry."},
        {"start": 1.5, "end": 3.25, "text": "Test."},
    ]
    assert to_srt(segments).startswith("1\n00:00:00,000 --> 00:00:01,500\nDzień dobry.\n")
    assert to_text(segments, with_times=True).splitlines()[1] == "[00:00:01] Test."
    assert to_text(segments, with_times=False) == "Dzień dobry.\nTest."


def test_transcription_rejects_non_media(harness: ToolHarness, tmp_path: Path) -> None:
    document = tmp_path / "notatka.txt"
    document.write_text("tekst", encoding="utf-8")
    with pytest.raises(ToolError, match="nie jest nagraniem"):
        call(harness, "transcribe_audio", file_id=harness.add(document))


def _whisper_ready(harness: ToolHarness) -> bool:
    settings = harness.settings
    return Path(settings.whisper_python).is_file() and (settings.whisper_model_dir / "model.bin").is_file()


@pytest.mark.skipif(shutil.which("espeak-ng") is None, reason="Brak espeak-ng")
def test_transcribes_polish_speech(harness: ToolHarness, tmp_path: Path) -> None:
    if not _whisper_ready(harness):
        pytest.skip("Brak środowiska faster-whisper lub modelu")
    recording = tmp_path / "nagranie.wav"
    subprocess.run(
        [
            "espeak-ng",
            "-v",
            "pl",
            "-s",
            "140",
            "-w",
            str(recording),
            "Faktura numer siedem. Termin płatności trzydzieści dni.",
        ],
        check=True,
        capture_output=True,
    )
    result = call(harness, "transcribe_audio", file_id=harness.add(recording), formats=["txt", "srt"])
    transcript = result.data["transcript"].lower()
    assert result.data["language"] == "pl"
    assert "faktur" in transcript and "płatności" in transcript
    assert sorted(output.name for output in result.files) == [
        "nagranie_transkrypcja.srt",
        "nagranie_transkrypcja.txt",
    ]
    assert result.files[1].path.read_text(encoding="utf-8").startswith("1\n00:00:")
