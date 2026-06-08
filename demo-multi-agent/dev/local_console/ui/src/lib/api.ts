/**
 * JSON-RPC 2.0 client for matbot's A2A surface (POST /a2a).
 *
 * `sendSync` calls `message/send` and resolves with the JSON-RPC
 * `result` (always a Task object for the chat skill).  `sendStream`
 * calls `message/stream`, parses the SSE `data: <json>` records, and
 * yields each JSON-RPC envelope so the caller can fold the incremental
 * `status-update` and `artifact-update` frames into the transcript.
 */
import type {
  OutboundMessage,
  StreamFrame,
  SyncTaskResult,
} from "@/types/invoke";

const RPC_PATH = "/a2a";
const AGENT_CARD_PATH = "/.well-known/agent-card.json";

interface RpcEnvelope<T> {
  jsonrpc: "2.0";
  id: string;
  result?: T;
  error?: { code: number; message: string; data?: unknown };
}

function buildRpcBody(method: string, message: OutboundMessage, id: string) {
  return JSON.stringify({
    jsonrpc: "2.0",
    id,
    method,
    params: { message },
  });
}

export async function sendSync(
  message: OutboundMessage,
  requestId: string,
  signal?: AbortSignal,
): Promise<{ status: number; envelope: RpcEnvelope<SyncTaskResult>; raw: string }> {
  const res = await fetch(RPC_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: buildRpcBody("message/send", message, requestId),
    signal,
  });
  const raw = await res.text();
  let envelope: RpcEnvelope<SyncTaskResult>;
  try {
    envelope = JSON.parse(raw) as RpcEnvelope<SyncTaskResult>;
  } catch {
    envelope = {
      jsonrpc: "2.0",
      id: requestId,
      error: { code: -32700, message: `Non-JSON response: ${raw.slice(0, 200)}` },
    };
  }
  return { status: res.status, envelope, raw };
}

export async function* sendStream(
  message: OutboundMessage,
  requestId: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamFrame, void, void> {
  const res = await fetch(RPC_PATH, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: buildRpcBody("message/stream", message, requestId),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    yield {
      error: {
        code: res.status,
        message: `HTTP ${res.status}: ${text || res.statusText}`,
      },
    };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sep: number;
      while ((sep = findRecordEnd(buffer)) !== -1) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        if (buffer.startsWith("\n")) buffer = buffer.slice(1);
        const parsed = parseFrame(raw);
        if (parsed) yield parsed;
      }
    }
    const tail = buffer.trim();
    if (tail) {
      const parsed = parseFrame(tail);
      if (parsed) yield parsed;
    }
  } finally {
    reader.releaseLock();
  }
}

function findRecordEnd(buf: string): number {
  const a = buf.indexOf("\n\n");
  const b = buf.indexOf("\r\n\r\n");
  if (a === -1) return b === -1 ? -1 : b;
  if (b === -1) return a;
  return Math.min(a, b);
}

function parseFrame(raw: string): StreamFrame | null {
  const dataLines: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
  }
  if (dataLines.length === 0) return null;
  const joined = dataLines.join("\n");
  try {
    const env = JSON.parse(joined) as RpcEnvelope<unknown>;
    return {
      id: env.id,
      result: env.result as StreamFrame["result"],
      error: env.error,
    };
  } catch {
    return { raw: joined };
  }
}

export async function probeAgentCard(
  signal?: AbortSignal,
): Promise<{ name: string; skills: string[] } | null> {
  try {
    const res = await fetch(AGENT_CARD_PATH, { signal });
    if (!res.ok) return null;
    const card = (await res.json()) as {
      name?: string;
      skills?: Array<{ id: string }>;
    };
    return {
      name: card.name ?? "agent",
      skills: (card.skills ?? []).map((s) => s.id).filter(Boolean),
    };
  } catch {
    return null;
  }
}

export async function probeHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch("/healthz", { method: "GET", signal });
    return res.ok;
  } catch {
    return false;
  }
}
