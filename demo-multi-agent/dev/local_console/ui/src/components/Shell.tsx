import type { ReactNode } from "react";

import { HealthDot } from "./HealthDot";
import { ModeSelector } from "./ModeSelector";
import { ThemeToggle } from "./ThemeToggle";
import { useHealth } from "@/hooks/useHealth";
import { useTheme } from "@/hooks/useTheme";
import type { InvokeMode } from "@/types/invoke";

interface Props {
  mode: InvokeMode;
  onModeChange: (next: InvokeMode) => void;
  busy: boolean;
  children: ReactNode;
}

/**
 * Outermost layout: topbar with brand chip, mode pill (sync/stream),
 * health dot, and theme toggle.  Underneath, a flex row containing
 * the chat column and the settings drawer.
 */
export function Shell({ mode, onModeChange, busy, children }: Props) {
  const health = useHealth();
  const { theme, toggle: toggleTheme } = useTheme();

  return (
    <div className="flex h-full flex-col bg-surface-0 text-ink">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--hairline)] bg-surface-1 px-4">
        <BrandChip />
        <div className="h-5 w-px bg-[var(--hairline)]" aria-hidden />
        <ModeSelector mode={mode} onChange={onModeChange} disabled={busy} />
        <div className="ml-auto flex items-center gap-3">
          <HealthDot status={health} />
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <div className="flex flex-1 min-h-0">{children}</div>
    </div>
  );
}

function BrandChip() {
  return (
    <div className="flex items-center gap-2">
      <div
        className="grid h-7 w-7 place-items-center rounded-md text-white shadow-tile"
        style={{
          background:
            "linear-gradient(135deg, var(--accent), var(--accent-strong))",
        }}
        aria-hidden
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path
            d="M2 12.5l3.2-5.3 2.1 3.2L9.6 6l3.4 6.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="13.2" cy="4.4" r="1.2" fill="var(--spark)" />
        </svg>
      </div>
      <div className="flex flex-col leading-tight">
        <span className="text-sm font-semibold tracking-tight text-ink">
          matbot
        </span>
        <span className="text-2xs uppercase tracking-wider text-ink-faint">
          a2a test console
        </span>
      </div>
    </div>
  );
}
