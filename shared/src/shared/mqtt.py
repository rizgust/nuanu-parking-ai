"""MQTT client helpers using aiomqtt (async).

Usage:
    async with MQTTClientManager(host="mosquitto", port=1883) as client:
        await client.publish("parking/lot-a/state", payload, retain=True)

NOTE: aiomqtt 2.x API — use `async with aiomqtt.Client(...)` pattern.
Do NOT use paho-mqtt directly; aiomqtt is the async wrapper used throughout.
"""

import json
import logging
from typing import Any

import aiomqtt

logger = logging.getLogger(__name__)


class MQTTClientManager:
    """Async context manager wrapping aiomqtt.Client with helpers."""

    def __init__(self, host: str, port: int = 1883) -> None:
        self.host = host
        self.port = port
        self._client: aiomqtt.Client | None = None

    async def __aenter__(self) -> "MQTTClientManager":
        self._client = aiomqtt.Client(hostname=self.host, port=self.port)
        await self._client.__aenter__()
        logger.info("MQTT connected to %s:%d", self.host, self.port)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.__aexit__(*args)
            logger.info("MQTT disconnected")

    async def publish(self, topic: str, payload: dict | str, retain: bool = False, qos: int = 1) -> None:
        """Publish a message. Payload dict is serialized to JSON."""
        if self._client is None:
            raise RuntimeError("MQTTClientManager not entered — use as async context manager")
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        await self._client.publish(topic, payload=payload, retain=retain, qos=qos)
        logger.debug("MQTT publish → %s (retain=%s)", topic, retain)

    async def subscribe(self, topic: str, qos: int = 1) -> None:
        """Subscribe to a topic."""
        if self._client is None:
            raise RuntimeError("MQTTClientManager not entered")
        await self._client.subscribe(topic, qos=qos)
        logger.debug("MQTT subscribed ← %s", topic)

    @property
    def messages(self):
        """Async iterator over incoming messages. Use in `async for msg in client.messages:`."""
        if self._client is None:
            raise RuntimeError("MQTTClientManager not entered")
        return self._client.messages
