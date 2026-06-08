"""Kafka handler — declarative produce / consume over aiokafka.

Resolves connection details (``bootstrap_servers``, optional SSL +
SASL) from Dynaconf via ``spec.kafka_connection``, renders the topic
+ key + value templates against the call params, then drives either a
short-lived ``AIOKafkaProducer`` (``produce``) or ``AIOKafkaConsumer``
(``consume``).

Operations (``spec.kafka_operation``):

  * ``produce`` — send one message and wait for ack; returns
    ``{topic, partition, offset, timestamp, produced: True}``.
  * ``consume`` — poll once for up to ``spec.kafka_max_messages``;
    returns ``{messages: [...], count}``.  JSON values are decoded
    automatically (with UTF-8 fallback for non-JSON payloads).

Security:

  * ``security_protocol`` resolves from connection config
    (PLAINTEXT / SSL / SASL_PLAINTEXT / SASL_SSL).
  * mTLS via ``ssl_cafile`` + optional ``ssl_certfile`` / ``ssl_keyfile``
    is built into an :class:`ssl.SSLContext` by
    :func:`executor._build_kafka_ssl` — kept as an instance method on
    :class:`~agent_factory.tools.executor.ToolExecutor` because tests
    call it directly (``ex._build_kafka_ssl(...)``).
  * SASL/PLAIN with ``sasl_username`` / ``sasl_password`` is supported.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, TYPE_CHECKING

from ._base import ToolHandler
from ..executor import _render_template, logger

if TYPE_CHECKING:  # pragma: no cover
    from ..executor import ToolExecutor
    from ..pack_models import ToolSpec


class KafkaHandler(ToolHandler):
    type_name = "kafka"

    async def execute(
        self,
        *,
        tool_id: str,
        spec: "ToolSpec",
        params: dict[str, Any],
        executor: "ToolExecutor",
    ) -> dict[str, Any]:
        if spec.type != "kafka":
            return {"error": f"Tool '{tool_id}' is not a kafka tool"}

        from agent_factory.infrastructure.settings import get_config

        config = get_config()
        conn_cfg = (
            getattr(config, spec.kafka_connection, None)
            if spec.kafka_connection else None
        )
        if not conn_cfg:
            return {"error": f"Kafka connection '{spec.kafka_connection}' not configured"}

        enriched = executor._enrich_params_from_templates(params, [
            spec.kafka_topic_template,
            spec.kafka_key_template,
            *[str(v) for v in spec.kafka_value_template.values()],
        ])

        topic = _render_template(spec.kafka_topic_template, enriched) if spec.kafka_topic_template else ""
        if not topic:
            return {"error": "kafka_topic_template is required"}

        # Resolve broker config
        brokers = getattr(conn_cfg, "bootstrap_servers", "") or getattr(conn_cfg, "KAFKA_BROKERS", "")
        if not brokers:
            return {"error": "Kafka bootstrap_servers not configured"}

        # Optional security config
        security_protocol = getattr(conn_cfg, "security_protocol", "PLAINTEXT")
        ssl_cafile = getattr(conn_cfg, "ssl_cafile", "") or ""
        ssl_certfile = getattr(conn_cfg, "ssl_certfile", "") or ""
        ssl_keyfile = getattr(conn_cfg, "ssl_keyfile", "") or ""
        sasl_mechanism = getattr(conn_cfg, "sasl_mechanism", "") or ""
        sasl_username = getattr(conn_cfg, "sasl_username", "") or ""
        sasl_password = getattr(conn_cfg, "sasl_password", "") or ""

        operation = spec.kafka_operation

        try:
            if operation == "produce":
                return await self._produce(
                    spec, enriched, topic, brokers,
                    security_protocol, ssl_cafile, ssl_certfile, ssl_keyfile,
                    sasl_mechanism, sasl_username, sasl_password,
                    params, executor,
                )
            elif operation == "consume":
                return await self._consume(
                    spec, enriched, topic, brokers,
                    security_protocol, ssl_cafile, ssl_certfile, ssl_keyfile,
                    sasl_mechanism, sasl_username, sasl_password,
                    params, executor,
                )
            else:
                return {"error": f"Unknown Kafka operation: {operation}"}

        except ImportError:
            return {"error": "aiokafka not installed (pip install aiokafka)"}
        except Exception as e:  # noqa: BLE001 — surface to caller
            error_outcomes = spec.response.error_outcomes
            outcome = error_outcomes.get("default")
            if outcome:
                return {"outcome": outcome, "error": str(e), **params}
            logger.error(f"kafka tool '{tool_id}' failed: {e}", exc_info=True)
            return {"error": str(e), **params}

    async def _produce(
        self, spec, enriched, topic, brokers,
        security_protocol, ssl_cafile, ssl_certfile, ssl_keyfile,
        sasl_mechanism, sasl_username, sasl_password,
        params, executor,
    ) -> dict[str, Any]:
        """Produce a message to a Kafka topic."""
        from aiokafka import AIOKafkaProducer  # type: ignore
        from ..response_processors import apply_processor

        # Build message key and value
        key = None
        if spec.kafka_key_template:
            key = _render_template(spec.kafka_key_template, enriched).encode("utf-8")

        if spec.kafka_value_template:
            val_str = json.dumps(spec.kafka_value_template)
            val_str = _render_template(val_str, enriched)
            value = val_str.encode("utf-8")
        else:
            value = json.dumps(enriched).encode("utf-8")

        # Build producer kwargs
        producer_kwargs: dict[str, Any] = {
            "bootstrap_servers": brokers,
            "security_protocol": security_protocol,
        }
        if ssl_cafile:
            producer_kwargs["ssl_context"] = executor._build_kafka_ssl(ssl_cafile, ssl_certfile, ssl_keyfile)
        if sasl_mechanism:
            producer_kwargs["sasl_mechanism"] = sasl_mechanism
            producer_kwargs["sasl_plain_username"] = sasl_username
            producer_kwargs["sasl_plain_password"] = sasl_password

        producer = AIOKafkaProducer(**producer_kwargs)
        await producer.start()
        try:
            record_metadata = await producer.send_and_wait(topic, value=value, key=key)
            data = {
                "topic": record_metadata.topic,
                "partition": record_metadata.partition,
                "offset": record_metadata.offset,
                "timestamp": record_metadata.timestamp,
                "produced": True,
            }
        finally:
            await producer.stop()

        return apply_processor(spec.response.processor, data, spec.response, params)

    async def _consume(
        self, spec, enriched, topic, brokers,
        security_protocol, ssl_cafile, ssl_certfile, ssl_keyfile,
        sasl_mechanism, sasl_username, sasl_password,
        params, executor,
    ) -> dict[str, Any]:
        """Consume messages from a Kafka topic."""
        from aiokafka import AIOKafkaConsumer  # type: ignore
        from ..response_processors import apply_processor

        consumer_group = spec.kafka_consumer_group or f"matbot-{spec.id}"
        max_messages = spec.kafka_max_messages

        consumer_kwargs: dict[str, Any] = {
            "bootstrap_servers": brokers,
            "group_id": consumer_group,
            "auto_offset_reset": "latest",
            "enable_auto_commit": True,
            "security_protocol": security_protocol,
        }
        if ssl_cafile:
            consumer_kwargs["ssl_context"] = executor._build_kafka_ssl(ssl_cafile, ssl_certfile, ssl_keyfile)
        if sasl_mechanism:
            consumer_kwargs["sasl_mechanism"] = sasl_mechanism
            consumer_kwargs["sasl_plain_username"] = sasl_username
            consumer_kwargs["sasl_plain_password"] = sasl_password

        consumer = AIOKafkaConsumer(topic, **consumer_kwargs)
        await consumer.start()
        messages = []
        try:
            batch = await asyncio.wait_for(
                consumer.getmany(timeout_ms=5000, max_records=max_messages),
                timeout=float(spec.timeout_seconds),
            )
            for tp, msgs in batch.items():
                for msg in msgs:
                    try:
                        val = json.loads(msg.value.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        val = msg.value.decode("utf-8", errors="replace")
                    messages.append({
                        "topic": msg.topic,
                        "partition": msg.partition,
                        "offset": msg.offset,
                        "key": msg.key.decode("utf-8") if msg.key else None,
                        "value": val,
                        "timestamp": msg.timestamp,
                    })
        finally:
            await consumer.stop()

        data = {"messages": messages, "count": len(messages)}
        return apply_processor(spec.response.processor, data, spec.response, params)


__all__ = ["KafkaHandler"]
