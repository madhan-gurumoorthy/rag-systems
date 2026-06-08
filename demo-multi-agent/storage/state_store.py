"""PostgreSQL state manager with normalized message storage.

Stores conversation state as normalized rows (one row per message) instead of JSONB blobs.
Each session has multiple message rows with composite primary key (session_id, message_id).
Falls back gracefully if env vars are missing.
"""
import os
import json
import asyncio
import traceback
import re
import uuid
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from agent_factory.common.tracing import trace_function

# Type alias for source_type enum
SourceType = Literal['CHAT', 'AUTONOMOUS']

try:
    from agent_factory.common.logging import get_logger
    logger = get_logger(__name__)
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)

# Attempt to import asyncpg (LightRAG already ensures installation but be defensive)
try:
    import asyncpg  # type: ignore
    ASYNCPG_AVAILABLE = True
except ImportError:  # pragma: no cover
    ASYNCPG_AVAILABLE = False
    asyncpg = None  # type: ignore
    logger.warning("asyncpg not available; PostgreSQL state storage disabled")

class PostgreSQLStateManager:
    """Manages conversation state with normalized message storage.

    Schema: {agent_name}_conversation_state table with one row per message.
    Composite primary key: (session_id, message_id)
    Session-level state stored in the last message's 'state' JSONB field.
    """
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None  # type: ignore
        self.table_name: Optional[str] = None
        self.table_created = False
        self._init_lock = asyncio.Lock()
        self._we_created_pool = False
    
    def _sanitize_table_name(self, agent_name: str) -> str:
        """
        Convert agent name to valid PostgreSQL table name.
        Example: one-agent → one_agent_conversation_state
        """
        # Remove/replace special characters
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', agent_name.lower())
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return f"{sanitized}_conversation_state"

    async def initialize(self, agent_name: str, pg_config=None):
        """Initialize the PostgreSQL connection pool.

        Args:
            agent_name: Name of the agent; used to derive the
                per-agent ``table_name`` slot for any caller that
                still inspects it.
            pg_config: PostgreSQL configuration object (from
                ``get_config().postgresql``).  If None, falls back to
                environment variables.

        Returns:
            True if the pool was created (or was already alive).  The
            pool is the only resource downstream stores need from this
            manager — the canonical schema (``agent_registry``,
            ``session``, ``work_item``, ``event``) has no per-agent
            conversation_state table, so ``initialize()`` does not
            probe or create one.  The ``insert_message`` /
            ``get_session_messages`` write path gates itself via
            :meth:`is_available`, which stays False until that path
            is repointed at the canonical ``event`` table.

        NOTE: No tracing decorator - this runs during startup before any requests.
        """
        if self.pool is not None:
            return True
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available; cannot initialize PostgreSQL manager")
            return False

        async with self._init_lock:
            # Create pool if needed
            if self.pool is None:
                try:
                    # Use config object if provided, otherwise fall back to env vars
                    if pg_config:
                        host = getattr(pg_config, 'LIGHTRAG_POSTGRES_HOST', None)
                        port = getattr(pg_config, 'LIGHTRAG_POSTGRES_PORT', '5432')
                        user = getattr(pg_config, 'LIGHTRAG_POSTGRES_USER', None)
                        password = getattr(pg_config, 'LIGHTRAG_POSTGRES_PASSWORD', None)
                        database = getattr(pg_config, 'LIGHTRAG_POSTGRES_DATABASE', None)
                        logger.info("Using PostgreSQL config from secrets.toml")
                    else:
                        host = os.getenv("POSTGRES_HOST")
                        port = os.getenv("POSTGRES_PORT", "5432")
                        user = os.getenv("POSTGRES_USER")
                        password = os.getenv("POSTGRES_PASSWORD")
                        database = os.getenv("POSTGRES_DATABASE")
                        logger.info("Using PostgreSQL config from environment variables")

                    if not (host and user and password and database):
                        logger.warning("PostgreSQL configuration missing; state persistence disabled")
                        logger.warning(f"  host={bool(host)}, user={bool(user)}, password={bool(password)}, database={bool(database)}")
                        return False

                    # Pool sizing from settings (with sane defaults)
                    pool_min = int(getattr(pg_config, 'POSTGRES_POOL_MIN_SIZE', 0) or
                                   os.getenv("POSTGRES_POOL_MIN_SIZE", "1"))
                    pool_max = int(getattr(pg_config, 'POSTGRES_POOL_MAX_SIZE', 0) or
                                   os.getenv("POSTGRES_POOL_MAX_SIZE", "10"))
                    cmd_timeout = int(getattr(pg_config, 'POSTGRES_COMMAND_TIMEOUT_SECS', 0) or
                                      os.getenv("POSTGRES_COMMAND_TIMEOUT_SECS", "30"))

                    self.pool = await asyncpg.create_pool(  # type: ignore
                        host=host,
                        port=int(port),
                        user=user,
                        password=password,
                        database=database,
                        min_size=pool_min,
                        max_size=pool_max,
                        command_timeout=cmd_timeout,
                    )
                    self._we_created_pool = True
                    logger.info(
                        f"PostgreSQL pool created host={host} db={database} "
                        f"pool_min={pool_min} pool_max={pool_max} "
                        f"cmd_timeout={cmd_timeout}s"
                    )
                except Exception as e:  # pragma: no cover
                    logger.error(f"Failed to initialize PostgreSQL pool: {e}")
                    logger.debug(traceback.format_exc())
                    self.pool = None
                    return False

            # Record the per-agent table name so any caller that still
            # walks `self.table_name` finds a non-None value; the table
            # itself is not created or verified.
            if agent_name is None:
                agent_name = os.getenv("AGENT_NAME", "default_agent")
            self.table_name = self._sanitize_table_name(agent_name)

            return True

    def is_available(self) -> bool:
        """Check if PostgreSQL manager is ready to use.

        Stays False so the normalized-message write path silently
        no-ops.  Downstream stores (``work_item_store``,
        ``event_store`` etc.) bind to :attr:`pool` directly and don't
        consult this flag.
        """
        return self.pool is not None and self.table_created and self.table_name is not None

    # ============================================================================
    # New normalized storage methods
    # ============================================================================

    @trace_function(span_name="postgres.insert_message", attributes={"wm.span.category": "persistence"})
    async def insert_message(
        self,
        session_id: str,
        message_id: str,
        source_type: SourceType,
        source_channel: str,
        source_id: str,
        user_id: Optional[str],
        msg_type: str,
        content: str,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        error_data: Optional[Dict[str, Any]] = None,
        state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Insert a new message row.
        created_at and updated_at are auto-populated with UTC NOW().
        
        Args:
            session_id: Session identifier
            message_id: Unique message identifier
            source_type: Source type ('CHAT' or 'AUTONOMOUS')
            source_channel: Source channel ('mihu_ui', 'snow', 'slack', 'teams')
            source_id: Source identifier (e.g., INC49599616, ALERT123)
            user_id: Optional user identifier
            msg_type: Message type ('user', 'agent', 'system')
            content: Message content
            operation: Optional operation type ('triage', 'classify', 'analyze', 'approve', 'resolve', 'update')
            status: Optional status ('SUCCESS', 'FAILURE', 'timeout')
            error_data: Optional error data JSONB (for failed operations)
            state: Optional state JSONB (for session-level state)
            metadata: Optional metadata JSONB
        
        Returns:
            bool: True if successful
        """
        if not self.is_available():
            logger.debug("PostgreSQL insert_message skipped: not available")
            return False
        
        # Validate source_type
        if source_type not in ('CHAT', 'AUTONOMOUS'):
            logger.error(f"Invalid source_type: {source_type}. Must be 'CHAT' or 'AUTONOMOUS'")
            raise ValueError(f"Invalid source_type: {source_type}. Must be 'CHAT' or 'AUTONOMOUS'")
        
        try:
            error_data_json = json.dumps(error_data, ensure_ascii=False, default=str) if error_data else None
            state_json = json.dumps(state or {}, ensure_ascii=False, default=str)
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False, default=str)
            
            async with self.pool.acquire() as conn:  # type: ignore
                await conn.execute(
                    f"""
                    INSERT INTO {self.table_name} 
                    (session_id, message_id, source_type, source_channel, source_id, user_id, 
                     msg_type, operation, status, error_data, content, state, metadata, 
                     created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb, $11, $12::jsonb, 
                            $13::jsonb, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
                    """,
                    session_id, message_id, source_type, source_channel, source_id, user_id,
                    msg_type, operation, status, error_data_json, content, state_json, metadata_json
                )
            
            logger.debug(f"Message inserted: session={session_id} msg={message_id} type={msg_type}")
            return True
        except Exception as e:
            logger.error(f"Error inserting message: {e}")
            logger.debug(traceback.format_exc())
            return False

    @trace_function(span_name="postgres.delete_session", attributes={"wm.span.category": "persistence"})
    async def get_latest_message_state(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get the 'state' JSONB field from the LAST ASSISTANT message in session.
        This is where team state is stored (conversation memory, tool outputs, etc.)
        
        We specifically get assistant messages because:
        - User messages have empty state
        - Assistant messages contain the team state from processing
        
        Args:
            session_id: Session identifier
        
        Returns:
            Dict with team state, or empty dict if no assistant messages
        """
        if not self.is_available():
            return {}
        
        try:
            async with self.pool.acquire() as conn:  # type: ignore
                query = f"""
                    SELECT state
                    FROM {self.table_name}
                    WHERE session_id = $1 
                      AND msg_type = 'assistant'
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                
                row = await conn.fetchrow(query, session_id)
            
            if not row or not row['state']:
                return {}
            
            state = row['state']
            if isinstance(state, str):
                state = json.loads(state)
            
            return state if isinstance(state, dict) else {}
        except Exception as e:
            logger.error(f"Error getting latest state: {e}")
            logger.debug(traceback.format_exc())
            return {}

    @trace_function(span_name="postgres.get_session_messages", attributes={"wm.span.category": "persistence"})
    async def get_session_messages(
        self,
        session_id: str,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return the most-recent user/assistant messages for a session,
        ordered oldest-first.

        Only ``user`` and ``assistant`` rows are returned (system/tool rows
        are internal plumbing, not user-visible history).

        Args:
            session_id: Session identifier.
            limit: Maximum number of message rows to return.  We fetch
                the N most-recent and reverse the result so the caller
                sees oldest → newest, which is what LangChain expects
                for `chat_history`.

        Returns:
            List of ``{"msg_type": "user"|"assistant", "content": str,
            "message_id": str, "created_at": str}`` dicts, ordered
            oldest-first.  Empty list if the manager is unavailable
            or the session has no eligible messages.
        """
        if not self.is_available():
            return []
        if limit <= 0:
            return []

        try:
            async with self.pool.acquire() as conn:  # type: ignore
                # Fetch most-recent N then reverse to oldest-first.  We
                # sort by created_at DESC + message_id DESC as a stable
                # tiebreaker for messages created in the same millisecond.
                query = f"""
                    SELECT message_id, msg_type, content, created_at
                    FROM {self.table_name}
                    WHERE session_id = $1
                      AND msg_type IN ('user', 'assistant')
                    ORDER BY created_at DESC, message_id DESC
                    LIMIT $2
                """
                rows = await conn.fetch(query, session_id, limit)

            messages: List[Dict[str, Any]] = []
            for row in reversed(rows):
                messages.append({
                    "message_id": row["message_id"],
                    "msg_type": row["msg_type"],
                    "content": row["content"] or "",
                    "created_at": (
                        row["created_at"].isoformat()
                        if hasattr(row["created_at"], "isoformat")
                        else str(row["created_at"])
                    ),
                })
            return messages
        except Exception as e:
            logger.error(f"Error fetching session messages: {e}")
            logger.debug(traceback.format_exc())
            return []

    @trace_function(span_name="postgres.delete_session", attributes={"wm.span.category": "persistence"})
    async def delete_session(
        self,
        session_id: str
    ) -> bool:
        """
        Delete all messages for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            bool: True if successful
        """
        if not self.is_available():
            return False
        
        try:
            async with self.pool.acquire() as conn:  # type: ignore
                result = await conn.execute(
                    f"DELETE FROM {self.table_name} WHERE session_id = $1",
                    session_id
                )
            
            deleted = result.split()[-1] if isinstance(result, str) else "0"
            logger.info(f"Deleted {deleted} messages for session={session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            logger.debug(traceback.format_exc())
            return False

    @trace_function(span_name="postgres.finalize", attributes={"wm.span.category": "persistence"})
    async def finalize(self):  # pragma: no cover
        """Close the PostgreSQL connection pool."""
        if self.pool and self._we_created_pool:
            try:
                await self.pool.close()  # type: ignore
                logger.info("PostgreSQL pool closed")
            except Exception as e:
                logger.error(f"Error closing PostgreSQL pool: {e}")
            finally:
                self.pool = None
                self.table_created = False
                self.table_name = None


# Global singleton instance (exported)
postgres_state_manager = PostgreSQLStateManager()

__all__ = ["PostgreSQLStateManager", "postgres_state_manager"]
