import { useCallback, useRef, type KeyboardEvent } from "react";

interface Props {
  onSend: (prompt: string) => void;
  onCancel: () => void;
  busy: boolean;
  placeholder?: string;
}

/**
 * Bottom-of-screen composer card. Auto-resizes the textarea up to
 * 240px, sends on Enter (Shift+Enter for newline), and exposes a
 * cancel button while a request is in-flight so the operator can
 * abort long streams.
 */
export function Composer({ onSend, onCancel, busy, placeholder }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    if (busy) return;
    const value = ref.current?.value ?? "";
    if (!value.trim()) return;
    onSend(value);
    if (ref.current) {
      ref.current.value = "";
      ref.current.style.height = "auto";
    }
  }, [busy, onSend]);

  const handleKey = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  const autoResize = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
  }, []);

  return (
    <div className="border-t border-[var(--hairline)] bg-surface-1 px-6 py-4">
      <div className="mx-auto flex max-w-3xl flex-col gap-2 rounded-tile border border-[var(--hairline)] bg-surface-0 px-3 py-2 focus-within:border-accent focus-within:shadow-tile">
        <textarea
          ref={ref}
          rows={2}
          disabled={busy}
          placeholder={placeholder ?? "Type a query and press Enter…"}
          onKeyDown={handleKey}
          onInput={autoResize}
          className="resize-none border-0 bg-transparent px-1 py-1 text-sm text-ink placeholder-ink-faint focus:outline-none disabled:opacity-50"
          spellCheck={false}
        />
        <div className="flex items-center justify-between border-t border-dashed border-[var(--hairline)] pt-2">
          <span className="text-2xs text-ink-faint">
            Enter to send · Shift+Enter for newline
          </span>
          <div className="flex items-center gap-2">
            {busy && (
              <button
                type="button"
                onClick={onCancel}
                className="rounded-md border border-[var(--hairline)] bg-surface-0 px-2.5 py-1 text-2xs font-medium text-ink-muted hover:border-danger hover:text-danger"
              >
                cancel
              </button>
            )}
            <button
              type="button"
              onClick={handleSend}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-tile transition-colors hover:bg-accent-strong disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
              <span aria-hidden>→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
