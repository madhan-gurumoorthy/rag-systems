import { useCallback, useMemo, useRef, useState } from "react";

import { sendStream, sendSync } from "@/lib/api";
import { uuid } from "@/lib/uuid";
import type {
  ArtifactUpdateEnvelope,
  ChatMessage,
  InvokeMode,
  OutboundMessage,
  RequestSettings,
  StatusUpdateEnvelope,
  SyncTaskResult,
  TextPart,
} from "@/types/invoke";

interface UseInvokeReturn {
  messages: ChatMessage[];
  busy: boolean;
  send: (prompt: string, mode: InvokeMode) => Promise<void>;
  cancel: () => void;
  clear: () => void;
  settings: RequestSettings;
  setSettings: (s: RequestSettings) => void;
  regenerateIds: () => void;
}

/**
 * Owns the chat transcript and the A2A request lifecycle.
 *
 * Sync (`message/send`) returns one Task; we pick the first text part
 * out of `artifacts[0].parts` (or fall back to `status.message.parts`)
 * and render it as a single assistant bubble.
 *
 * Stream (`message/stream`) yields:
 *   - one initial `task` envelope (we capture taskId/contextId)
 *   - one or more `status-update` envelopes with `final:false` whose
 *     `status.message.parts[*].text` carry incremental chat chunks
 *   - zero or more `artifact-update` envelopes (full artifact text)
 *   - one terminal `status-update` envelope with `final:true` whose
 *     `status.message.parts[*].text` carries the complete response
 */
export function useInvoke(): UseInvokeReturn {
  const initialIds = useMemo(
    () => ({ sessionId: uuid(), messageId: uuid() }),
    [],
  );

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<RequestSettings>({
    agentId: "",
    sessionId: initialIds.sessionId,
    messageId: initialIds.messageId,
    metadataJson: "{}",
  });

  const abortRef = useRef<AbortController | null>(null);
  const assistantIdRef = useRef<string | null>(null);
  const assistantContentRef = useRef<string>("");

  const upsertAssistant = useCallback(
    (mutate: (current: ChatMessage) => ChatMessage) => {
      const id = assistantIdRef.current;
      if (!id) return;
      setMessages((prev) => prev.map((m) => (m.id === id ? mutate(m) : m)));
    },
    [],
  );

  const beginAssistantBubble = useCallback(() => {
    const id = uuid();
    assistantIdRef.current = id;
    assistantContentRef.current = "";
    setMessages((prev) => [
      ...prev,
      { id, role: "assistant", content: "", streaming: true },
    ]);
  }, []);

  const finalizeAssistantBubble = useCallback(
    (finalContent: string, meta?: ChatMessage["meta"]) => {
      const id = assistantIdRef.current;
      assistantIdRef.current = null;
      if (!id) return;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id
            ? { ...m, content: finalContent, streaming: false, meta }
            : m,
        ),
      );
    },
    [],
  );

  const failAssistantBubble = useCallback((errorText: string) => {
    const id = assistantIdRef.current;
    assistantIdRef.current = null;
    if (!id) {
      setMessages((prev) => [
        ...prev,
        { id: uuid(), role: "error", content: errorText },
      ]);
      return;
    }
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? { ...m, role: "error", content: errorText, streaming: false }
          : m,
      ),
    );
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const clear = useCallback(() => {
    cancel();
    setMessages([]);
    assistantIdRef.current = null;
    assistantContentRef.current = "";
  }, [cancel]);

  const regenerateIds = useCallback(() => {
    setSettings((s) => ({ ...s, sessionId: uuid(), messageId: uuid() }));
  }, []);

  /** Build the outbound A2A Message from the prompt + current settings. */
  const buildMessage = useCallback(
    (prompt: string): OutboundMessage => {
      const metadata: Record<string, unknown> = {};
      if (settings.agentId.trim()) {
        metadata.agent_id = settings.agentId.trim();
      }
      const extra = settings.metadataJson.trim();
      if (extra && extra !== "{}") {
        const parsed = JSON.parse(extra) as unknown;
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          Object.assign(metadata, parsed as Record<string, unknown>);
        } else {
          throw new Error("metadata passthrough must be a JSON object");
        }
      }

      const message: OutboundMessage = {
        kind: "message",
        messageId: settings.messageId || uuid(),
        role: "user",
        parts: [{ kind: "text", text: prompt }],
      };
      if (Object.keys(metadata).length) message.metadata = metadata;
      if (settings.sessionId) message.contextId = settings.sessionId;
      return message;
    },
    [settings],
  );

  const send = useCallback(
    async (prompt: string, mode: InvokeMode) => {
      const trimmed = prompt.trim();
      if (!trimmed || busy) return;

      cancel();
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);

      setMessages((prev) => [
        ...prev,
        { id: uuid(), role: "user", content: trimmed },
      ]);
      beginAssistantBubble();

      let message: OutboundMessage;
      try {
        message = buildMessage(trimmed);
      } catch (err) {
        failAssistantBubble(err instanceof Error ? err.message : String(err));
        setBusy(false);
        abortRef.current = null;
        return;
      }

      try {
        if (mode === "sync") {
          await runSync(message, controller.signal);
        } else {
          await runStream(message, controller.signal);
        }
      } catch (err) {
        if ((err as { name?: string }).name === "AbortError") {
          finalizeAssistantBubble(
            assistantContentRef.current || "(cancelled)",
          );
        } else {
          failAssistantBubble(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setBusy(false);
        abortRef.current = null;
      }
    },
    // runSync / runStream close over the refs and helpers above; they
    // are stable across renders so the dep list only needs the helpers
    // they call out to.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [busy, cancel, beginAssistantBubble, buildMessage, failAssistantBubble],
  );

  const runSync = useCallback(
    async (message: OutboundMessage, signal: AbortSignal) => {
      const { status, envelope, raw } = await sendSync(
        message,
        uuid(),
        signal,
      );
      if (envelope.error) {
        failAssistantBubble(
          `RPC error ${envelope.error.code}: ${envelope.error.message}`,
        );
        return;
      }
      if (status < 200 || status >= 300 || !envelope.result) {
        failAssistantBubble(`HTTP ${status}\n${raw.slice(0, 2000)}`);
        return;
      }
      const task = envelope.result as SyncTaskResult;
      const text = extractTaskText(task);
      finalizeAssistantBubble(text || "(empty response)", {
        task: task.id.slice(0, 12),
        context: task.contextId.slice(0, 12),
        state: task.status?.state ?? "",
      });
    },
    [failAssistantBubble, finalizeAssistantBubble],
  );

  const runStream = useCallback(
    async (message: OutboundMessage, signal: AbortSignal) => {
      let taskId = "";
      let contextId = "";
      let lastState = "";

      for await (const frame of sendStream(message, uuid(), signal)) {
        if (frame.error) {
          failAssistantBubble(
            `RPC error ${frame.error.code}: ${frame.error.message}`,
          );
          return;
        }
        if (frame.raw) {
          assistantContentRef.current += frame.raw;
          upsertAssistant((m) => ({
            ...m,
            content: assistantContentRef.current,
          }));
          continue;
        }
        const result = frame.result;
        if (!result) continue;

        if (result.kind === "task") {
          taskId = result.id;
          contextId = result.contextId;
          lastState = result.status?.state ?? "";
        } else if (result.kind === "artifact-update") {
          const partsText = collectPartsText(
            (result as ArtifactUpdateEnvelope).artifact.parts,
          );
          if (partsText) {
            assistantContentRef.current = partsText;
            upsertAssistant((m) => ({
              ...m,
              content: assistantContentRef.current,
            }));
          }
        } else if (result.kind === "status-update") {
          const status = (result as StatusUpdateEnvelope).status;
          lastState = status.state ?? lastState;
          const chunkText = collectPartsText(status.message?.parts);
          if (chunkText) {
            // Final frames carry the complete message — replace
            // rather than append.  Mid-stream frames are incremental
            // deltas.
            if ((result as StatusUpdateEnvelope).final) {
              assistantContentRef.current = chunkText;
            } else {
              assistantContentRef.current += chunkText;
            }
            upsertAssistant((m) => ({
              ...m,
              content: assistantContentRef.current,
            }));
          }
          if ((result as StatusUpdateEnvelope).final) {
            finalizeAssistantBubble(
              assistantContentRef.current || "(empty response)",
              {
                task: taskId.slice(0, 12),
                context: contextId.slice(0, 12),
                state: lastState,
              },
            );
            return;
          }
        }
      }
      // Stream closed without a `final:true` frame — finalize defensively.
      if (assistantIdRef.current) {
        finalizeAssistantBubble(
          assistantContentRef.current || "(stream closed)",
          {
            task: taskId.slice(0, 12),
            context: contextId.slice(0, 12),
            state: lastState,
          },
        );
      }
    },
    [failAssistantBubble, finalizeAssistantBubble, upsertAssistant],
  );

  return {
    messages,
    busy,
    send,
    cancel,
    clear,
    settings,
    setSettings,
    regenerateIds,
  };
}

function collectPartsText(parts?: TextPart[]): string {
  if (!parts || parts.length === 0) return "";
  return parts
    .filter((p) => p && p.kind === "text" && typeof p.text === "string")
    .map((p) => p.text)
    .join("");
}

function extractTaskText(task: SyncTaskResult): string {
  if (task.artifacts && task.artifacts.length > 0) {
    for (const art of task.artifacts) {
      const text = collectPartsText(art.parts);
      if (text) return text;
    }
  }
  return collectPartsText(task.status?.message?.parts);
}
