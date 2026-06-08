import type { InvokeMode } from "@/types/invoke";

interface Props {
  mode: InvokeMode;
  onChange: (next: InvokeMode) => void;
  disabled?: boolean;
}

interface Option {
  value: InvokeMode;
  label: string;
  hint: string;
}

const OPTIONS: ReadonlyArray<Option> = [
  { value: "stream", label: "stream", hint: "SSE" },
  { value: "sync", label: "sync", hint: "JSON" },
];

/** Picks `/a2a/invoke-stream` (SSE) vs `/a2a/invoke` (sync JSON). */
export function ModeSelector({ mode, onChange, disabled }: Props) {
  return (
    <div
      role="radiogroup"
      aria-label="transport mode"
      className="inline-flex items-center rounded-chip border border-[var(--hairline)] bg-surface-2 p-0.5"
    >
      {OPTIONS.map((opt) => {
        const active = opt.value === mode;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={`flex items-center gap-1.5 rounded-chip px-3 py-1 text-xs font-medium transition-colors ${
              active
                ? "bg-accent-soft text-accent"
                : "text-ink-muted hover:text-ink hover:bg-surface-3"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            title={`mode=${opt.value} — ${opt.hint}`}
          >
            <span>{opt.label}</span>
            <span className="text-2xs text-ink-faint">{opt.hint}</span>
          </button>
        );
      })}
    </div>
  );
}
