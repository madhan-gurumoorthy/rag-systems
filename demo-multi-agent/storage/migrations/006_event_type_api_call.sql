-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 006 — widen event.event_type CHECK to include 'api_call'.
--
-- The framework now emits one ``api_call`` event per outbound upstream
-- invocation (REST / BigQuery / Kafka / aiohttp / httpx) so the dashboard
-- can render the full fan-out underneath each owning tool row, rather
-- than collapsing to a single aggregate ``tool`` event.
--
-- Apply once against any DB created before this migration.
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE event
    DROP CONSTRAINT IF EXISTS event_event_type_check;

ALTER TABLE event
    ADD CONSTRAINT event_event_type_check
    CHECK (event_type IN ('dispatch', 'llm', 'tool', 'api_call', 'hitl', 'state', 'error'));
