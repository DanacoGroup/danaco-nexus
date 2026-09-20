"""Serwer MCP (stdio) udostępniający narzędzia Nexusa sesji Claude Code CLI.

Proces uruchamia CLI na czas jednego zadania (``--mcp-config``). Zadanie
i rozmowę wskazują zmienne ``NEXUS_RUN_ID`` i ``NEXUS_CONVERSATION_ID``.
Narzędzia działają w puli wątków; pliki wynikowe trafiają do magazynu,
a postęp – do zdarzeń zadania odczytywanych przez interfejs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from nexus import __version__
from nexus.config import get_settings
from nexus.db import ADMIN_OWNER, Database, RunEvent
from nexus.events import EventBus
from nexus.file_service import FileService
from nexus.logging_setup import configure_logging
from nexus.storage import FileStorage
from nexus.tools import registry
from nexus.tools.base import ToolCancelled, ToolContext, ToolError

logger = logging.getLogger("nexus.mcp")

SERVER_NAME = "nexus"
PROGRESS_MIN_INTERVAL = 0.7
# Claude Code przekazuje identyfikator wywołania narzędzia w ``_meta`` żądania MCP – dzięki
# niemu postęp równoległych wywołań (np. kilku podagentów) trafia do właściwego elementu.
TOOL_USE_ID_META = "claudecode/toolUseId"


def _image_content(data: bytes) -> types.ImageContent:
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return types.ImageContent(data=base64.standard_b64encode(data).decode("ascii"), mime_type=mime)


def _tool_use_id(params: types.CallToolRequestParams) -> str:
    """Identyfikator wywołania w sesji CLI (``_meta`` żądania), gdy klient go przekazuje."""
    meta = params.meta
    if hasattr(meta, "model_dump"):
        meta = meta.model_dump(by_alias=True)
    value = meta.get(TOOL_USE_ID_META) if isinstance(meta, dict) else None
    return value if isinstance(value, str) else ""


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=f"Błąd: {message}")], is_error=True)


class ToolServer:
    """Obsługa żądań MCP dla jednego zadania agenta."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._database = Database(self._settings.database_url)
        self._files = FileService(self._database, FileStorage(self._settings.files_dir))
        self._executor = ThreadPoolExecutor(max_workers=max(2, self._settings.tool_threads))
        self._run_id = uuid.UUID(os.environ["NEXUS_RUN_ID"])
        conversation = os.environ.get("NEXUS_CONVERSATION_ID", "")
        self._conversation_id = uuid.UUID(conversation) if conversation else None
        wlasciciel = os.environ.get("NEXUS_OWNER_ID", "")
        self._owner_id = uuid.UUID(wlasciciel) if wlasciciel else ADMIN_OWNER
        self._cancel = threading.Event()
        self._events = EventBus(self._settings.redis_url)

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        async with self._database.session() as session:
            session.add(RunEvent(run_id=self._run_id, type=event_type, data=data))
        await self._events.notify(self._run_id)

    async def list_tools(self, _ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=definition["name"],
                    description=definition["description"],
                    input_schema=definition["input_schema"],
                )
                for definition in registry.definitions()
            ]
        )

    def _context(self, loop: asyncio.AbstractEventLoop, name: str, tool_use_id: str = "") -> ToolContext:
        last = [0.0]
        base = {"name": name, "tool_use_id": tool_use_id} if tool_use_id else {"name": name}

        def progress(text: str) -> None:
            now = loop.time()
            if now - last[0] >= PROGRESS_MIN_INTERVAL:
                last[0] = now
                asyncio.run_coroutine_threadsafe(
                    self.emit("tool.progress", {**base, "text": text}), loop
                ).result()

        return ToolContext(
            self._settings,
            self._run_id,
            resolve_file=lambda file_id: asyncio.run_coroutine_threadsafe(
                self._files.resolve(file_id), loop
            ).result(),
            cancel=self._cancel,
            progress=progress,
            mark_indexed=lambda file_id: asyncio.run_coroutine_threadsafe(
                self._files.mark_indexed(file_id), loop
            ).result(),
            owner_id=self._owner_id,
        )

    async def call_tool(self, _ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        loop = asyncio.get_running_loop()
        try:
            tool = registry.get(params.name)
            arguments = tool.parse(params.arguments or {})
        except ToolError as error:
            return _error(str(error))
        context = self._context(loop, params.name, _tool_use_id(params))
        try:
            result = await loop.run_in_executor(self._executor, tool.handler, context, arguments)
            files = await self._files.store_outputs(self._run_id, self._conversation_id, result.files)
        except ToolCancelled:
            return _error("zadanie anulowane przez użytkownika")
        except ToolError as error:
            return _error(str(error))
        except Exception as error:  # noqa: BLE001 - błąd narzędzia przekazywany modelowi
            logger.exception("Błąd narzędzia %s (zadanie %s)", params.name, self._run_id)
            return _error(f"błąd wewnętrzny narzędzia: {error}")
        finally:
            await loop.run_in_executor(self._executor, context.cleanup)
        payload = {"summary": result.summary, "result": result.data}
        if files:
            payload["output_files"] = [
                {"file_id": f["id"], "name": f["name"], "mime": f["mime"], "size_bytes": f["size"]}
                for f in files
            ]
        content: list[types.ContentBlock] = [
            types.TextContent(text=json.dumps(payload, ensure_ascii=False, default=str))
        ]
        content.extend(_image_content(image) for image in result.images)
        return types.CallToolResult(content=content)

    async def serve(self) -> None:
        server = Server(
            SERVER_NAME,
            version=__version__,
            on_list_tools=self.list_tools,
            on_call_tool=self.call_tool,
        )
        try:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())
        finally:
            self._cancel.set()
            self._executor.shutdown(wait=False, cancel_futures=True)
            await self._events.close()
            await self._database.close()


def main() -> None:
    """Punkt wejścia serwera MCP."""
    settings = get_settings()
    configure_logging(settings.data_dir / "logs", "mcp", logging.WARNING, console=False, rotate=False)
    asyncio.run(ToolServer().serve())


if __name__ == "__main__":
    main()
