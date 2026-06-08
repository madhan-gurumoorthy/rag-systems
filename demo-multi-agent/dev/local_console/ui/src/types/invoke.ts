/**
 * Wire-shape types for matbot's A2A surface (JSON-RPC 2.0 over /a2a).
 *
 * The console only exercises the chat skill — every prompt becomes a
 * single text `Part` on a `Message` sent via `message/send` (sync) or
 * `message/stream` (SSE).  Pack selection rides on
 * `message.metadata.agent_id`; the A2A `context_id` is the matbot
 * `session_id`.
 */

export type InvokeMode = "sync" | "stream";

/** Operator-controlled request settings. */
export interface RequestSettings {
  /** Pack id to route the message to (becomes message.metadata.agent_id). */
  agentId: string;
  /** Reused as A2A context_id == matbot session_id when present. */
  sessionId: string;
  /** Stable per-message id; the executor logs it as MID. */
  messageId: string;
  /** Optional metadata object shallow-merged onto message.metadata. */
  metadataJson: string;
}

/** A text `Part` as it appears on the wire. */
export interface TextPart {
  kind: "text";
  text: string;
}

/** Minimal Message shape we send. */
export interface OutboundMessage {
  kind: "message";
  messageId: string;
  role: "user";
  parts: TextPart[];
  metadata?: Record<string, unknown>;
  contextId?: string;
}

/** Conversation transcript entry kept in component state. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "error";
  /** Markdown-ish text. Assistant bubbles render through marked + DOMPurify. */
  content: string;
  /** Optional metadata chips shown under the bubble on hover. */
  meta?: Record<string, string | number | undefined>;
  /** True while an assistant bubble is still receiving chunks. */
  streaming?: boolean;
}

/** A single parsed `data: <json>` SSE frame for `message/stream`. */
export interface StreamFrame {
  /** JSON-RPC envelope id (echo of our request id). */
  id?: string | number;
  /** Decoded `result` from the JSON-RPC envelope. */
  result?: A2AResultEnvelope;
  /** Set when the envelope carries an error instead of a result. */
  error?: { code: number; message: string; data?: unknown };
  /** Raw fallback for non-JSON-RPC frames or parse failures. */
  raw?: string;
}

/** Union of the A2A `result.kind` shapes the chat skill emits. */
export type A2AResultEnvelope =
  | TaskEnvelope
  | StatusUpdateEnvelope
  | ArtifactUpdateEnvelope;

export interface TaskEnvelope {
  kind: "task";
  id: string;
  contextId: string;
  status: { state: string };
}

export interface StatusUpdateEnvelope {
  kind: "status-update";
  taskId: string;
  contextId: string;
  final: boolean;
  status: {
    state: string;
    timestamp?: string;
    message?: {
      parts?: TextPart[];
      role?: string;
      messageId?: string;
    };
  };
}

export interface ArtifactUpdateEnvelope {
  kind: "artifact-update";
  taskId: string;
  contextId: string;
  artifact: {
    artifactId: string;
    name?: string;
    parts?: TextPart[];
  };
}

/** Sync `message/send` always returns a Task object. */
export interface SyncTaskResult {
  kind: "task";
  id: string;
  contextId: string;
  status: {
    state: string;
    timestamp?: string;
    message?: {
      parts?: TextPart[];
      messageId?: string;
    };
  };
  artifacts?: Array<{
    artifactId: string;
    name?: string;
    parts?: TextPart[];
  }>;
  history?: unknown[];
}
