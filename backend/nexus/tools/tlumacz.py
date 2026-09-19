"""Narzędzie Tłumacza: tłumaczenie dokumentów DOCX, PPTX, PDF, TXT i MD z zachowaniem układu."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from nexus.tools.base import OutputFile, ToolContext, ToolError, ToolInput, ToolResult, registry
from nexus.tools.common import with_suffix
from nexus.tworczy import tlumaczenie
from nexus.tworczy.tlumaczenie import STYLES, ClaudeTranslator, Translate, TranslationError


class TranslateDocumentInput(ToolInput):
    file_id: str = Field(description="Dokument: DOCX, PPTX, PDF (z tekstem cyfrowym), TXT albo MD.")
    target_language: str = Field(description="Kod języka docelowego ISO 639-1, np. 'en', 'de', 'uk'.")
    source_language: str = Field("auto", description="Kod języka źródłowego albo 'auto'.")
    style: str = Field("neutralny", description=f"Styl tłumaczenia: {', '.join(STYLES)}.")
    glossary: str = Field("", max_length=4000, description="Opcjonalny słowniczek, np. 'umowa = agreement'.")


def make_translator(ctx: ToolContext, args: TranslateDocumentInput) -> Translate:
    """Tłumacz segmentów: Claude Code CLI uruchamiany z przerywaniem po anulowaniu zadania."""

    def runner(command: list[str], env: dict[str, str], cwd: Path) -> str:
        return ctx.run_command(
            command, timeout=ctx.settings.tworczy_translate_timeout_s, cwd=cwd, env=env
        ).stdout

    return ClaudeTranslator(
        ctx.settings,
        args.target_language,
        args.source_language,
        args.style,
        args.glossary,
        runner=runner,
        progress=ctx.progress,
    )


@registry.register(
    "translate_document",
    """Tłumaczy dokument na inny język z zachowaniem układu i formatowania: DOCX (akapity, tabele,
nagłówki, stopki, pola tekstowe), PPTX (slajdy, tabele, notatki), PDF z tekstem cyfrowym (tłumaczenie
w tych samych miejscach strony, grafika bez zmian), TXT i MD. Skany PDF najpierw przepuść przez
ocr_documents. Wynik to nowy plik w tym samym formacie.""",
    TranslateDocumentInput,
)
def translate_document(ctx: ToolContext, args: TranslateDocumentInput) -> ToolResult:
    file = ctx.file(args.file_id)
    try:
        target_code = tlumaczenie.check_language(args.target_language)
        tlumaczenie.check_language(args.source_language, allow_auto=True)
        translator = tlumaczenie_factory(ctx, args)
        target = ctx.output_path(with_suffix(file.name, file.suffix, f"_{target_code}"))
        ctx.progress(f"Tłumaczenie {file.name} na: {tlumaczenie.language_name(target_code)}")
        count = tlumaczenie.translate_document(file.path, target, translator)
    except TranslationError as error:
        raise ToolError(str(error)) from error
    language = tlumaczenie.language_name(target_code)
    return ToolResult(
        {"output": target.name, "segments": count, "target_language": target_code},
        f"Przetłumaczono {file.name} na: {language} ({count} fragmentów)",
        files=[OutputFile(target, target.name, f"Tłumaczenie ({language}) – {file.name}")],
    )


# Fabryka tłumacza – w testach zastępowana atrapą.
tlumaczenie_factory = make_translator
