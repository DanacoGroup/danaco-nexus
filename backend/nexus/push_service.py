"""Powiadomienia Web Push o zakończonych zadaniach.

Klucz VAPID (krzywa P-256, PEM) powstaje przy pierwszym starcie API w pliku
``settings.vapid_file`` z prawami 600. API nasłuchuje kanału Redis
``nexus:run-finished`` (publikuje go proces roboczy po zakończeniu zadania)
i rozsyła powiadomienie do wszystkich zapisanych subskrypcji. Subskrypcje
odrzucone przez usługę push (404/410) są usuwane.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import delete, select, update

from nexus.config import Settings
from nexus.db import Database, utcnow
from nexus.models.push import PushSubscription

logger = logging.getLogger(__name__)

RUN_FINISHED_CHANNEL = "nexus:run-finished"
PUSH_TTL_SECONDS = 24 * 3600
GONE_STATUSES = frozenset({404, 410})
MAX_FAILURES = 5
RECONNECT_SECONDS = 15.0

# Wysyłka jednego powiadomienia: (subskrypcja w formacie PushSubscription.toJSON(), treść JSON) -> kod HTTP.
Sender = Callable[[dict[str, Any], str], int]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def endpoint_hash(endpoint: str) -> str:
    """Skrót adresu subskrypcji (unikalny indeks niezależny od długości adresu)."""
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def ensure_vapid_key(path: Path) -> str:
    """Tworzy klucz VAPID (jeśli brak) i zwraca klucz publiczny w formacie ``applicationServerKey``."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass  # drugi proces utworzył klucz w tej samej chwili – odczyt niżej
        else:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(pem)
            logger.info("Utworzono klucz VAPID powiadomień push: %s", path)
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError(f"Plik {path} nie zawiera klucza EC (VAPID).")
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(public)


def vapid_subject(settings: Settings) -> str:
    """Kontakt w oświadczeniu VAPID (``mailto:`` albo adres https serwisu)."""
    if settings.push_contact:
        return settings.push_contact
    return settings.public_url.rstrip("/") or "https://danaco-nexus.pl"


def pywebpush_sender(settings: Settings) -> Sender:
    """Wysyłka przez bibliotekę pywebpush (synchronicznie – wywoływana w wątku)."""
    from pywebpush import WebPushException, webpush

    key_file = str(settings.vapid_file)
    subject = vapid_subject(settings)

    def send(subscription: dict[str, Any], payload: str) -> int:
        try:
            response = webpush(
                subscription,
                data=payload,
                vapid_private_key=key_file,
                # pywebpush dopisuje do słownika „aud” i „exp” – nowy słownik na każdą wysyłkę.
                vapid_claims={"sub": subject},
                ttl=PUSH_TTL_SECONDS,
                timeout=15,
            )
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status is None:
                raise
            return int(status)
        return int(getattr(response, "status_code", 201))

    return send


@dataclass
class DeliveryReport:
    sent: int = 0
    removed: int = 0
    failed: int = 0


async def send_to_all(database: Database, sender: Sender, message: dict[str, Any]) -> DeliveryReport:
    """Wysyła powiadomienie do wszystkich subskrypcji; usuwa wygasłe."""
    payload = json.dumps(message, ensure_ascii=False)
    async with database.session() as session:
        subscriptions = (await session.scalars(select(PushSubscription))).all()
    report = DeliveryReport()
    for record in subscriptions:
        info = {"endpoint": record.endpoint, "keys": {"p256dh": record.p256dh, "auth": record.auth}}
        try:
            status = await asyncio.to_thread(sender, info, payload)
        except Exception as error:  # noqa: BLE001 - błąd sieci jednej subskrypcji nie przerywa wysyłki
            logger.warning("Powiadomienie push nie zostało wysłane: %s", error)
            status = 0
        async with database.session() as session:
            if status in GONE_STATUSES:
                await session.execute(delete(PushSubscription).where(PushSubscription.id == record.id))
                report.removed += 1
            elif 200 <= status < 300:
                await session.execute(
                    update(PushSubscription)
                    .where(PushSubscription.id == record.id)
                    .values(last_sent_at=utcnow(), failures=0)
                )
                report.sent += 1
            else:
                report.failed += 1
                if record.failures + 1 >= MAX_FAILURES:
                    await session.execute(delete(PushSubscription).where(PushSubscription.id == record.id))
                    report.removed += 1
                else:
                    await session.execute(
                        update(PushSubscription)
                        .where(PushSubscription.id == record.id)
                        .values(failures=PushSubscription.failures + 1)
                    )
    return report


def run_finished_message(event: dict[str, Any]) -> dict[str, Any] | None:
    """Treść powiadomienia dla komunikatu ``nexus:run-finished`` (``None`` – bez powiadomienia)."""
    status = str(event.get("status", ""))
    conversation = str(event.get("conversation_id", ""))
    if status == "cancelled" or not conversation:
        return None
    title = str(event.get("title") or "Rozmowa").strip()[:120]
    failed = status == "failed"
    return {
        "title": "Zadanie nie powiodło się" if failed else "Zadanie zakończone",
        "body": title,
        "url": f"/c/{conversation}",
        "tag": f"run-{conversation}",
        "run_id": str(event.get("run_id", "")),
        "status": status,
    }


async def listen_run_finished(settings: Settings, database: Database, sender: Sender) -> None:
    """Nasłuch kanału ``nexus:run-finished`` (do anulowania zadania asyncio)."""
    if not settings.redis_url:
        logger.info("Brak NEXUS_REDIS_URL – powiadomienia push o zakończonych zadaniach są wyłączone.")
        return
    import redis.asyncio as redis

    while True:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=5)
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe(RUN_FINISHED_CHANNEL)
            async for item in pubsub.listen():
                if item.get("type") != "message":
                    continue
                try:
                    event = json.loads(item["data"])
                except (TypeError, ValueError):
                    continue
                message = run_finished_message(event) if isinstance(event, dict) else None
                if message is not None:
                    report = await send_to_all(database, sender, message)
                    logger.info(
                        "Push o zadaniu %s: wysłane %s, usunięte %s, błędy %s",
                        message["run_id"],
                        report.sent,
                        report.removed,
                        report.failed,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - Redis chwilowo niedostępny: ponowna próba
            logger.warning("Nasłuch %s przerwany (%s) – ponowna próba.", RUN_FINISHED_CHANNEL, error)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.aclose()
            with contextlib.suppress(Exception):
                await client.aclose()
        await asyncio.sleep(RECONNECT_SECONDS)
