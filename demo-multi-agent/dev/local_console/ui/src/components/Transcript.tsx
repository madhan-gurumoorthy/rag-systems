import { useEffect, useRef } from "react";

import { MessageBubble } from "./MessageBubble";
import type { ChatMessage } from "@/types/invoke";

interface Props {
  messages: ChatMessage[];
}

/** Scrolling transcript surface. Auto-scrolls on every new message and
 *  on every content edit (streaming chunks mutate an existing bubble
 *  in place; without watching the last message's content the view
 *  would freeze mid-stream). */
export function Transcript({ messages }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, messages[messages.length - 1]?.content]);

  if (messages.length === 0) {
    return (
      <div
        ref={ref}
        className="flex flex-1 items-center justify-center px-6 py-10 text-center text-sm text-ink-faint"
      >
        <div className="max-w-md space-y-2">
          <p className="text-ink-muted">matbot local test console</p>
          <p>
            Pick a kind + mode in the topbar, type a query below, and hit{" "}
            <kbd className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-ink">
              Enter
            </kbd>{" "}
            to send. Two transports share the same dispatcher:{" "}
            <code className="font-mono text-accent">/a2a/invoke</code> (sync
            JSON) and{" "}
            <code className="font-mono text-accent">/a2a/invoke-stream</code>{" "}
            (SSE).
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
      role="log"
      aria-label="Conversation transcript"
      aria-live="polite"
    >
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
    </div>
  );
}
