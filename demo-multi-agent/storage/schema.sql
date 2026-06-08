-- ═══════════════════════════════════════════════════════════════════════════
-- matbot-multi-agents — Consolidated Schema
-- ═══════════════════════════════════════════════════════════════════════════
--
-- Single-file, idempotent schema definition for the matbot LangGraph runtime.
-- Replaces the prior per-step migration files (001-009) now that the data
-- model has stabilised around the four canonical tables defined in the
-- scalable-agent-flow drawio source of truth:
--
--     /docs/diagrams/data_model.drawio
--
--   1. agent_registry   — one row per deployed agent (model, budget, caps)
--   2. session          — one row per conversation thread (≡ langgraph.thread_id)
--   3. work_item        — polymorphic incident/action/approval/decision
--   4. event            — append-only, monthly RANGE-partitioned LLM/tool/HITL log
--
-- Apply with:
--     psql "$DATABASE_URL" -f storage/schema.sql
--
-- The file is safe to re-run: every object uses CREATE … IF NOT EXISTS (or
-- DROP … IF EXISTS for policies that need replacing).
--
-- See docs/data-model.html in scalable-agent-flow for the schema reference
-- and ADR-013 (column-promotion criteria) for why most extension columns
-- live in JSONB instead of typed columns.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── Extensions ─────────────────────────────────────────────────────────────
-- pgcrypto: gen_random_uuid() for UUIDv4 work_item_id / event_id.
-- PG 13+ ships gen_random_uuid() natively, so pgcrypto is only needed for
-- legacy clusters.  On AlloyDB the CREATE EXTENSION call requires
-- alloydbsuperuser, so we wrap it in a DO block that swallows
-- insufficient_privilege errors — gen_random_uuid() remains available either
-- way.
--
-- pg_partman (optional): monthly RANGE partition rotation on `event`. The
-- bootstrap DO block below creates the first three monthly partitions so the
-- table is usable without partman; install it separately if you want
-- automatic rotation.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
EXCEPTION
    WHEN OTHERS THEN
        -- AlloyDB / managed clusters reject CREATE EXTENSION for
        -- non-allowlisted extensions (the error class varies — sometimes
        -- it's a role-resolution failure on alloydbsuperuser, sometimes
        -- insufficient_privilege).  gen_random_uuid() is built-in on
        -- PG 13+ so this is harmless.
        RAISE NOTICE 'pgcrypto extension not installed (% %) — relying on built-in gen_random_uuid()',
            SQLSTATE, SQLERRM;
END $$;


-- ═══════════════════════════════════════════════════════════════════════════
-- 1. agent_registry  [9 cols]
-- ═══════════════════════════════════════════════════════════════════════════
-- One row per deployed agent.  config JSONB carries model defaults, budget
-- caps, capabilities, slo, graph_name, pack_id — promoted to typed cols only
-- per ADR-013.
CREATE TABLE IF NOT EXISTS agent_registry (
    agent_id      TEXT PRIMARY KEY,
    agent_name    TEXT NOT NULL,
    agent_version TEXT NOT NULL,                          -- semver
    owner_team    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'paused', 'retired')),
    config        JSONB NOT NULL DEFAULT '{}'::jsonb,     -- model.{default,fallback}, budget.*, capabilities, slo, topology_hash, pack_id
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_registry_status
    ON agent_registry (status)
    WHERE archived_at IS NULL;


-- ═══════════════════════════════════════════════════════════════════════════
-- 2. session  [10 cols]   ⇄  langgraph.thread_id  (same UUID, no FK — diff schema)
-- ═══════════════════════════════════════════════════════════════════════════
-- session_id IS the langgraph thread_id (UUIDv7 generated app-side).
--
-- A session represents a long-lived conversation thread.  In chat
-- integrations (Slack, Teams, SMS) one thread can carry many distinct
-- work-item requests over its lifetime, so the per-run state (deadline,
-- payload, current pipeline status) lives on `work_item`, not here.
-- `status` covers the thread lifecycle only.
CREATE TABLE IF NOT EXISTS session (
    session_id        UUID PRIMARY KEY,
    agent_id          TEXT NOT NULL
                      REFERENCES agent_registry (agent_id) ON DELETE RESTRICT,
    tenant_id         TEXT NOT NULL,                        -- RLS axis (org-level)
    parent_session_id UUID REFERENCES session (session_id) ON DELETE SET NULL,
    status            TEXT NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'paused', 'completed', 'failed')),
    trace_id          TEXT,                                 -- W3C traceparent
    idempotency_key   TEXT,                                 -- UNIQUE per agent
    domain_data       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- agent-specific extension
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at          TIMESTAMPTZ,
    archived_at       TIMESTAMPTZ                            -- BQ roll-up complete
);

-- Idempotent column drops so the file re-applies cleanly against a
-- database that was bootstrapped with the previous run-state columns on
-- session.  Run-state has moved to `work_item` because a single session
-- (thread) hosts many work-item invocations.
ALTER TABLE session DROP COLUMN IF EXISTS run_state;
ALTER TABLE session DROP COLUMN IF EXISTS run_started_at;
ALTER TABLE session DROP COLUMN IF EXISTS run_deadline_at;
ALTER TABLE session DROP COLUMN IF EXISTS run_finished_at;
ALTER TABLE session DROP COLUMN IF EXISTS run_payload;
ALTER TABLE session DROP COLUMN IF EXISTS pack_id;
DROP INDEX IF EXISTS idx_session_pack_status;
DROP INDEX IF EXISTS idx_session_run_in_flight;

-- Hot indexes
CREATE INDEX IF NOT EXISTS idx_session_agent_tenant_active
    ON session (agent_id, tenant_id, status)
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_session_trace
    ON session (trace_id)
    WHERE trace_id IS NOT NULL;

-- Drop the pack-scoped idempotency index in favour of an agent-scoped one
-- (pack_id was removed from session per the multi-work-per-thread model).
DROP INDEX IF EXISTS uq_session_idempotency;
CREATE UNIQUE INDEX IF NOT EXISTS uq_session_idempotency
    ON session (agent_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_session_parent
    ON session (parent_session_id)
    WHERE parent_session_id IS NOT NULL;


-- ═══════════════════════════════════════════════════════════════════════════
-- 3. work_item  [22 cols]   polymorphic via kind discriminator + kind_data JSONB
-- ═══════════════════════════════════════════════════════════════════════════
-- kind ∈ {incident, action, approval, decision}.  title and external_ref are
-- universal keys INSIDE kind_data per ADR-003 / ADR-013 (sparse → JSONB).
--
-- pack_id is denormalised here for the same reasons as on session — every
-- callback / interrupt-key / external_ref / idempotency lookup routes on
-- (pack_id, …) so the planner gets a single-seek composite predicate.
CREATE TABLE IF NOT EXISTS work_item (
    work_item_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id               TEXT NOT NULL
                           REFERENCES agent_registry (agent_id) ON DELETE RESTRICT,
    pack_id                TEXT NOT NULL,                   -- logical content identity
    session_id             UUID NOT NULL
                           REFERENCES session (session_id) ON DELETE CASCADE,
    parent_work_item_id    UUID REFERENCES work_item (work_item_id) ON DELETE CASCADE,
    kind                   TEXT NOT NULL
                           CHECK (kind IN ('incident', 'action', 'approval', 'decision')),
    -- status is intentionally OPEN-ENDED (no CHECK constraint) — each kind
    -- has its own FSM and we don't want migrations every time a pack adds
    -- a transient state.  Canonical values by kind:
    --   approval   : pending → approved | rejected | expired
    --   incident   : open    → in_progress → resolved | escalated | skipped
    --   action     : pending → executing → done | failed
    --   decision   : pending → routed
    -- App-layer validation lives in the store (`set_status` for non-approvals,
    -- guarded `approve()`/`reject()` for approvals).
    status                 TEXT NOT NULL DEFAULT 'pending',
    priority               TEXT NOT NULL DEFAULT 'p3'
                           CHECK (priority IN ('p0', 'p1', 'p2', 'p3', 'p4')),
    idempotency_key        TEXT,
    -- LangGraph interrupt composite key (for kind='approval')
    interrupt_checkpoint_ns  TEXT,
    interrupt_checkpoint_id  TEXT,
    interrupt_task_id        TEXT,
    interrupt_idx            INT,
    -- Approval lifecycle
    assignee               TEXT,
    approved_by            TEXT,
    approved_at            TIMESTAMPTZ,
    expires_at             TIMESTAMPTZ,
    -- Polymorphic payload — kind-specific fields + universal title/external_ref
    kind_data              JSONB NOT NULL DEFAULT '{}'::jsonb,
    domain_data            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at            TIMESTAMPTZ,
    -- Framework-owned run-state slots for the 3-minute response contract.
    -- `status` already carries the pipeline state (running, awaiting_approval,
    -- done, failed, skipped, etc. — open-ended, app-validated). `created_at`
    -- is the run start; `updated_at` is the last touch (= run end on terminal
    -- transitions). The two slots below are the only ones with no natural
    -- equivalent on the row:
    --   run_deadline_at: deadline race + stale detection by GET endpoint.
    --   run_payload:     cached inline body so re-POSTs and pollers can
    --                    surface terminal results without re-running.
    run_deadline_at        TIMESTAMPTZ,
    run_payload            JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Idempotent column additions for live databases that pre-date the
-- 3-minute response contract.
ALTER TABLE work_item ADD COLUMN IF NOT EXISTS run_deadline_at TIMESTAMPTZ;
ALTER TABLE work_item ADD COLUMN IF NOT EXISTS run_payload     JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Hot indexes
CREATE INDEX IF NOT EXISTS idx_wi_session_kind
    ON work_item (session_id, kind);

CREATE INDEX IF NOT EXISTS idx_wi_agent_kind_status_pending
    ON work_item (agent_id, kind, status)
    WHERE archived_at IS NULL AND status = 'pending';

-- Idempotency scoped by (pack_id, idempotency_key) — pack is the correct
-- isolation axis once a single agent_id can host multiple packs.
CREATE UNIQUE INDEX IF NOT EXISTS uq_wi_idempotency
    ON work_item (pack_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- Approval SLA — partial index on expires_at when pending
CREATE INDEX IF NOT EXISTS idx_wi_approval_expires
    ON work_item (expires_at)
    WHERE kind = 'approval' AND status = 'pending';

-- LangGraph interrupt lookup (callback → resume), session-scoped
CREATE INDEX IF NOT EXISTS idx_wi_interrupt_lookup
    ON work_item (session_id, interrupt_checkpoint_id, interrupt_task_id, interrupt_idx)
    WHERE kind = 'approval';

-- Same interrupt lookup, pack-scoped — defense-in-depth filter on the
-- approval-callback path so the planner nails a single-seek even when the
-- session axis is bypassed.
CREATE INDEX IF NOT EXISTS idx_wi_pack_interrupt_lookup
    ON work_item (pack_id, session_id, interrupt_checkpoint_id, interrupt_task_id, interrupt_idx)
    WHERE kind = 'approval';

-- external_ref lookups: GIN-on-expression for the JSONB key, plus a B-tree
-- composite (pack_id, external_ref) for the equality-equality access pattern
-- that the Concord approval callback uses.
CREATE INDEX IF NOT EXISTS idx_wi_external_ref_gin
    ON work_item USING GIN ((kind_data -> 'external_ref'))
    WHERE kind_data ? 'external_ref';

CREATE INDEX IF NOT EXISTS idx_wi_pack_external_ref
    ON work_item (pack_id, (kind_data ->> 'external_ref'))
    WHERE kind_data ? 'external_ref';

-- In-flight run lookup for the 3-minute response contract.  Powers
-- stale-detection on GET /a2a/work-item/{external_ref} and the v2
-- recovery cron that scans for runs whose deadline has elapsed.
CREATE INDEX IF NOT EXISTS idx_wi_run_in_flight
    ON work_item (status, run_deadline_at)
    WHERE archived_at IS NULL AND status IN ('running', 'awaiting_approval');


-- ═══════════════════════════════════════════════════════════════════════════
-- 4. event  [23 cols]   append-only, monthly RANGE partitioned on created_at
-- ═══════════════════════════════════════════════════════════════════════════
-- Drives fine-tuning extraction, telemetry, replay safety.  trace_id is the
-- ONLY typed correlation col; langchain_run_id / langgraph_checkpoint_id live
-- in domain_data per ADR-013.
--
-- NOTE on FKs: pre-PG 15, partitioned tables could not have FK targets at all.
-- PG 16 lifts that for many cases, but FKs FROM a partitioned table still need
-- careful ON DELETE planning across partitions.  We deliberately omit FK
-- declarations on event.session_id / event.work_item_id and rely on:
--   (a) every writer using these stores (which enforce existence at the app
--       layer via FK-bearing inserts on session / work_item)
--   (b) BQ-roll-up archive sweeps that DELETE event rows older than N days
-- If a session/work_item is hard-deleted before its events are archived,
-- the events become orphaned.  We accept this for the partitioned table.
CREATE TABLE IF NOT EXISTS event (
    event_id              UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id            UUID NOT NULL,                     -- logical FK to session.session_id (no constraint; see note above)
    agent_id              TEXT NOT NULL,                     -- denormalized — partition pruning
    tenant_id             TEXT NOT NULL,                     -- denormalized — RLS axis
    work_item_id          UUID,                              -- logical FK to work_item.work_item_id (nullable)
    parent_event_id       UUID,                              -- causal chain
    seq_num               INT NOT NULL,                      -- per-session ordering
    event_type            TEXT NOT NULL
                          CHECK (event_type IN ('dispatch', 'llm', 'tool', 'api_call', 'hitl', 'state', 'error')),
    trace_id              TEXT,                              -- W3C traceparent (only typed correlation col)
    -- LLM call fields (NULL for non-llm events)
    model_provider        TEXT,
    model_name            TEXT,
    input_messages        JSONB,                             -- fine-tuning shape
    output_message        JSONB,
    input_tokens          INT NOT NULL DEFAULT 0,
    output_tokens         INT NOT NULL DEFAULT 0,
    cache_read_tokens     INT NOT NULL DEFAULT 0,            -- UsageMetadata
    cache_creation_tokens INT NOT NULL DEFAULT 0,            -- UsageMetadata
    reasoning_tokens      INT NOT NULL DEFAULT 0,            -- UsageMetadata
    llm_metadata          JSONB,                             -- response_metadata.{model_id,id,stop_reason}
    -- Latency (ADR-007)
    llm_latency_ms        INT,
    tool_latency_ms       INT,
    time_to_first_token_ms INT,
    -- Catch-all
    domain_data           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, created_at)                       -- partition key must be in PK
) PARTITION BY RANGE (created_at);

-- Bootstrap partitions: current month + next 2 months.
-- pg_partman (when installed) will manage rolling additions.
DO $$
DECLARE
    cur_start DATE := date_trunc('month', NOW())::date;
    p_start   DATE;
    p_end     DATE;
    p_name    TEXT;
BEGIN
    FOR i IN 0..2 LOOP
        p_start := (cur_start + (i * INTERVAL '1 month'))::date;
        p_end   := (cur_start + ((i + 1) * INTERVAL '1 month'))::date;
        p_name  := 'event_y' || to_char(p_start, 'YYYY') || 'm' || to_char(p_start, 'MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF event FOR VALUES FROM (%L) TO (%L)',
            p_name, p_start, p_end
        );
    END LOOP;
END $$;

-- Indexes are inherited by partitions when created on parent (PG 11+)
CREATE INDEX IF NOT EXISTS idx_event_session_seq
    ON event (session_id, seq_num);

CREATE INDEX IF NOT EXISTS idx_event_session_created
    ON event (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_event_agent_tenant_created
    ON event (agent_id, tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_event_trace
    ON event (trace_id)
    WHERE trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_event_work_item
    ON event (work_item_id)
    WHERE work_item_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_event_type_created
    ON event (event_type, created_at DESC);

-- GIN-on-expression for replay lookups via provider message id
CREATE INDEX IF NOT EXISTS idx_event_llm_response_id_gin
    ON event USING GIN ((llm_metadata -> 'response_metadata' -> 'id'))
    WHERE llm_metadata IS NOT NULL;


-- ═══════════════════════════════════════════════════════════════════════════
-- 5. updated_at triggers (single shared function)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_agent_registry_updated_at ON agent_registry;
CREATE TRIGGER trg_agent_registry_updated_at
    BEFORE UPDATE ON agent_registry
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_work_item_updated_at ON work_item;
CREATE TRIGGER trg_work_item_updated_at
    BEFORE UPDATE ON work_item
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ═══════════════════════════════════════════════════════════════════════════
-- 6. Row-Level Security — tenant-scoped on session / work_item / event
-- ═══════════════════════════════════════════════════════════════════════════
-- Contract:
--   • The app sets `SET LOCAL app.tenant_id = <tenant>` at the top of every
--     store transaction that touches these tables.
--   • The policy permits rows that match the GUC.
--   • When the GUC is unset (NULL) the policy permits everything — this
--     keeps admin / migration / superuser paths working without plumbing a
--     tenant_id (DDL, COPY, ops queries).  The app role is never expected
--     to leave the GUC unset; if it does, the worst case is degraded
--     isolation, not a hard failure.
--
-- The CHECK side (write-time) uses the same predicate so a mis-set GUC
-- can't write a row attributed to a different tenant.
--
-- work_item has no tenant_id column of its own; isolation is inherited via
-- the session FK using an EXISTS sub-query.  The RLS optimiser hoists the
-- predicate so we only pay one b-tree seek per row.  If telemetry shows a
-- hotspot, denormalise tenant_id onto work_item in a future change.

ALTER TABLE session    ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_item  ENABLE ROW LEVEL SECURITY;
ALTER TABLE event      ENABLE ROW LEVEL SECURITY;

-- Drop any pre-existing policies (legacy permissive bootstrap + current
-- tenant-isolation) so the file is safe to re-apply against a database
-- previously bootstrapped from the older per-step migration files.
DROP POLICY IF EXISTS session_permissive         ON session;
DROP POLICY IF EXISTS work_item_permissive       ON work_item;
DROP POLICY IF EXISTS event_permissive           ON event;
DROP POLICY IF EXISTS session_tenant_isolation   ON session;
DROP POLICY IF EXISTS work_item_tenant_isolation ON work_item;
DROP POLICY IF EXISTS event_tenant_isolation     ON event;

CREATE POLICY session_tenant_isolation ON session
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR tenant_id = current_setting('app.tenant_id', true)
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NULL
        OR tenant_id = current_setting('app.tenant_id', true)
    );

CREATE POLICY work_item_tenant_isolation ON work_item
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR EXISTS (
            SELECT 1 FROM session s
             WHERE s.session_id = work_item.session_id
               AND s.tenant_id  = current_setting('app.tenant_id', true)
        )
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NULL
        OR EXISTS (
            SELECT 1 FROM session s
             WHERE s.session_id = work_item.session_id
               AND s.tenant_id  = current_setting('app.tenant_id', true)
        )
    );

CREATE POLICY event_tenant_isolation ON event
    USING (
        current_setting('app.tenant_id', true) IS NULL
        OR tenant_id = current_setting('app.tenant_id', true)
    )
    WITH CHECK (
        current_setting('app.tenant_id', true) IS NULL
        OR tenant_id = current_setting('app.tenant_id', true)
    );


-- ═══════════════════════════════════════════════════════════════════════════
-- 7. Bootstrap row for gif_tote_validation_agent
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO agent_registry (
    agent_id,
    agent_name,
    agent_version,
    owner_team,
    status,
    config
) VALUES (
    'gif_tote_validation_agent',
    'GIF Tote Validation Agent',
    '1.0.0',
    'MerchantOps - Item Setup/Maintenance',
    'active',
    jsonb_build_object(
        'model', jsonb_build_object(
            'default',     'gpt-4.1-mini',
            'fallback',    'gpt-4.1-mini',
            'provider',    'azure_openai',
            'temperature', 0.1,
            'max_tokens',  4096
        ),
        'budget', jsonb_build_object(
            'per_session_token_cap', 30000,
            'per_session_event_cap', 200
        ),
        'capabilities', jsonb_build_object(
            'supports_hitl',      true,
            'supports_streaming', true
        ),
        'slo',          jsonb_build_object('p95_ms', 30000),
        'graph_name',   'gif_tote_validation_graph',
        'pack_id',      'gif_tote_validation'
    )
) ON CONFLICT (agent_id) DO NOTHING;
