"""Transkrypcja mowy (faster-whisper) uruchamiana w osobnym interpreterze.

Skrypt nie importuje modułów Nexusa – działa w środowisku Pythona z
faster-whisper (``whisper_python``). Wynik to JSON na standardowym wyjściu:
``{"language", "language_probability", "duration", "segments": [{start, end, text}]}``.
Postęp (sekundy nagrania) trafia na standardowe wyjście błędów.

Użycie: python transkrypcja_proces.py MODEL PLIK [JĘZYK] [WĄTKI]
"""

import json
import sys


def main() -> int:
    model_dir, media = sys.argv[1], sys.argv[2]
    language = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "auto" else None
    threads = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    from faster_whisper import WhisperModel

    model = WhisperModel(model_dir, device="cpu", compute_type="int8", cpu_threads=threads)
    segments, info = model.transcribe(
        media,
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
    )
    result = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            result.append({"start": round(segment.start, 2), "end": round(segment.end, 2), "text": text})
        sys.stderr.write(f"POSTEP {segment.end:.1f} {info.duration:.1f}\n")
        sys.stderr.flush()
    json.dump(
        {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": result,
        },
        sys.stdout,
        ensure_ascii=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
