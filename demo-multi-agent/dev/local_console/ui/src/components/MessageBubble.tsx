import { useMemo, useState } from "react";

import { renderMarkdown } from "@/lib/markdown";
import type { ChatMessage } from "@/types/invoke";

interface Props {
  message: ChatMessage;
}

/** Single transcript entry — user / assistant / error variants. User
 *  bubbles render plain text; assistant bubbles render markdown;
 *  error bubbles render plain text in danger colours. Assistant
 *  bubbles expose a copy + metadata toolbar on hover. */
export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const isError = message.role === "error";
  const [copied, setCopied] = useState(false);

  const html = useMemo(() => {
    if (isUser || isError) return "";
    return renderMarkdown(message.content);
  }, [isUser, isError, message.content]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard denied — ignore */
    }
  };

  const labelText = isUser
    ? "you"
    : isError
      ? "error"
      : message.streaming
        ? "assistant · streaming"
        : "assistant";

  const labelTone = isUser
    ? "text-accent"
    : isError
      ? "text-danger"
      : "text-good";

  const bubbleClasses = isUser
    ? "bg-accent text-white rounded-tile rounded-br-sm shadow-tile"
    : isError
      ? "bg-danger-soft text-danger border border-[var(--hairline)] rounded-tile rounded-bl-sm"
      : "bg-surface-1 text-ink border border-[var(--hairline)] rounded-tile rounded-bl-sm shadow-tile";

  return (
    <div
      className={`group flex max-w-[88%] gap-2.5 animate-fade-in ${
        isUser ? "ml-auto flex-row-reverse" : "mr-auto"
      }`}
    >
      <Avatar role={message.role} streaming={message.streaming} />

      <div className="flex min-w-0 flex-1 flex-col">
        <div
          className={`mb-1 text-2xs font-semibold uppercase tracking-wider ${labelTone} ${
            isUser ? "text-right" : ""
          }`}
        >
          {labelText}
        </div>

        <div className={`px-4 py-3 text-sm leading-relaxed ${bubbleClasses}`}>
          {message.streaming && !message.content ? (
            <TypingDots />
          ) : isUser || isError ? (
            <div className="whitespace-pre-wrap break-words">
              {message.content}
            </div>
          ) : (
            <div
              className="md break-words"
              // eslint-disable-next-line react/no-danger -- sanitized by DOMPurify in lib/markdown.ts
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>

        {!isUser && !message.streaming && message.content && (
          <div className="mt-1 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onClick={handleCopy}
              className="rounded-md border border-[var(--hairline)] bg-surface-1 px-2 py-0.5 text-2xs text-ink-muted hover:border-accent hover:text-accent"
              title="Copy assistant message"
            >
              {copied ? "copied" : "copy"}
            </button>
            {message.meta &&
              Object.entries(message.meta)
                .filter(([, v]) => v !== "" && v != null)
                .map(([k, v]) => (
                  <span
                    key={k}
                    className="rounded-md bg-surface-2 px-2 py-0.5 text-2xs font-mono text-ink-faint"
                  >
                    {k}: {String(v).slice(0, 60)}
                  </span>
                ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface AvatarProps {
  role: ChatMessage["role"];
  streaming?: boolean;
}

function Avatar({ role, streaming }: AvatarProps) {
  const isUser = role === "user";
  const isError = role === "error";
  const isAssistant = !isUser && !isError;

  const glyph = isUser ? "U" : isError ? "!" : "A";

  const classes = isUser
    ? "bg-accent-soft text-accent"
    : isError
      ? "bg-danger-soft text-danger"
      : "bg-good-soft text-good";

  return (
    <div
      className={`mt-7 grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${classes}`}
      aria-hidden
    >
      {isAssistant && streaming ? <PulseDot /> : glyph}
    </div>
  );
}

function PulseDot() {
  return (
    <span className="block h-1.5 w-1.5 animate-phase-pulse rounded-full bg-current" />
  );
}

function TypingDots() {
  return (
    <span
      className="inline-flex items-center gap-1 py-0.5"
      role="status"
      aria-label="assistant is thinking"
    >
      <Dot delay="-0.32s" />
      <Dot delay="-0.16s" />
      <Dot delay="0s" />
    </span>
  );
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-ink-muted"
      style={{ animationDelay: delay, animationDuration: "1.1s" }}
    />
  );
}
