"""
ParamX Hunter - WebSocket Analyzer
Captures WebSocket messages, parses JSON payloads, extracts parameters,
and reconstructs message schemas over the lifetime of a connection.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog
import websockets

from backend.core.extractors import ExtractedParameter, WebSocketExtractor

logger = structlog.get_logger(__name__)


@dataclass
class WSMessage:
    direction: str  # "send" | "receive"
    raw: str
    parsed: dict | Any | None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WSSchema:
    """Inferred JSON schema for a message 'type' / channel."""

    message_type: str
    fields: dict[str, str] = field(default_factory=dict)  # field_name -> inferred type
    sample_count: int = 0
    example: dict | None = None


class WebSocketAnalyzer:
    """
    Connects to (or replays captured traffic from) a WebSocket endpoint,
    extracts parameters from messages, and infers per-message-type schemas.
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.messages: list[WSMessage] = []
        self.schemas: dict[str, WSSchema] = {}
        self._extractor = WebSocketExtractor(endpoint, "WS")

    # ── Live capture ────────────────────────────────────────────────────────────

    async def capture_live(
        self,
        ws_url: str,
        send_messages: list[str] | None = None,
        headers: dict | None = None,
        duration_seconds: int = 10,
    ) -> list[WSMessage]:
        """
        Connect to a WebSocket endpoint, optionally send probe messages,
        and capture all traffic for `duration_seconds`.
        """
        import asyncio

        try:
            async with websockets.connect(
                ws_url,
                additional_headers=headers or {},
                open_timeout=10,
            ) as ws:
                # Send probe messages
                if send_messages:
                    for msg in send_messages:
                        await ws.send(msg)
                        self._record("send", msg)

                # Listen for responses with timeout
                try:
                    async with asyncio.timeout(duration_seconds):
                        async for raw in ws:
                            self._record(
                                "receive", raw if isinstance(raw, str) else raw.decode()
                            )
                except (asyncio.TimeoutError, TimeoutError):
                    pass

        except Exception as e:
            logger.warning("websocket_capture_failed", url=ws_url, error=str(e))

        return self.messages

    # ── Offline analysis ───────────────────────────────────────────────────────

    def ingest_message(self, raw: str, direction: str = "receive") -> WSMessage:
        """Process a single captured message (used by crawler integration)."""
        return self._record(direction, raw)

    def _record(self, direction: str, raw: str) -> WSMessage:
        parsed = None
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        msg = WSMessage(direction=direction, raw=raw, parsed=parsed)
        self.messages.append(msg)

        if isinstance(parsed, dict):
            self._update_schema(parsed)

        return msg

    def _update_schema(self, data: dict) -> None:
        """Infer/update schema based on a message's 'type'/'event'/'action' field."""
        msg_type = (
            data.get("type")
            or data.get("event")
            or data.get("action")
            or data.get("op")
            or "unknown"
        )
        msg_type = str(msg_type)

        schema = self.schemas.setdefault(
            msg_type, WSSchema(message_type=msg_type, example=data)
        )
        schema.sample_count += 1

        for key, value in data.items():
            inferred = type(value).__name__
            existing = schema.fields.get(key)
            if existing and existing != inferred:
                schema.fields[key] = f"{existing}|{inferred}"
            else:
                schema.fields[key] = inferred

    # ── Parameter extraction ───────────────────────────────────────────────────

    def extract_parameters(self) -> list[ExtractedParameter]:
        """Run extraction across all captured messages."""
        results: list[ExtractedParameter] = []
        for msg in self.messages:
            if msg.parsed is not None:
                for p in self._extractor.extract(msg.parsed):
                    p.extra["ws_direction"] = msg.direction
                    p.extra["ws_message_type"] = (
                        msg.parsed.get("type") if isinstance(msg.parsed, dict) else None
                    )
                    results.append(p)
        return results

    def get_schema_summary(self) -> list[dict]:
        """Return a JSON-serializable summary of all inferred schemas."""
        return [
            {
                "message_type": s.message_type,
                "fields": s.fields,
                "sample_count": s.sample_count,
                "example": s.example,
            }
            for s in self.schemas.values()
        ]

    def get_stats(self) -> dict:
        sent = sum(1 for m in self.messages if m.direction == "send")
        received = sum(1 for m in self.messages if m.direction == "receive")
        return {
            "total_messages": len(self.messages),
            "sent": sent,
            "received": received,
            "schemas_discovered": len(self.schemas),
            "message_types": list(self.schemas.keys()),
        }


# ── SSE (Server-Sent Events) Analyzer ──────────────────────────────────────────


class SSEAnalyzer:
    """
    Parses Server-Sent Events streams (text/event-stream) for parameters.
    """

    EVENT_RE = re.compile(r"^(event|data|id|retry):\s?(.*)$", re.MULTILINE)

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.events: list[dict] = []
        self._extractor = WebSocketExtractor(endpoint, "GET")

    def parse_stream(self, raw_stream: str) -> list[dict]:
        """Parse a raw SSE text stream into individual events."""
        events = []
        current: dict = {}

        for line in raw_stream.splitlines():
            line = line.strip()
            if not line:
                if current:
                    events.append(current)
                    current = {}
                continue
            match = self.EVENT_RE.match(line)
            if match:
                field_name, value = match.groups()
                if field_name == "data":
                    current.setdefault("data", []).append(value)
                else:
                    current[field_name] = value

        if current:
            events.append(current)

        self.events = events
        return events

    def extract_parameters(self) -> list[ExtractedParameter]:
        results = []
        for event in self.events:
            data_lines = event.get("data", [])
            joined = "\n".join(data_lines)
            try:
                parsed = json.loads(joined)
                for p in self._extractor.extract(parsed):
                    p.param_type = "sse"
                    p.source = "sse_stream"
                    p.extra["sse_event_type"] = event.get("event", "message")
                    results.append(p)
            except (json.JSONDecodeError, TypeError):
                continue
        return results
