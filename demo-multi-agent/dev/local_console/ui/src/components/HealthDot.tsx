import type { HealthStatus } from "@/hooks/useHealth";

interface Props {
  status: HealthStatus;
}

const COLOR: Record<HealthStatus, string> = {
  healthy: "bg-good",
  degraded: "bg-warn",
  unhealthy: "bg-danger",
  unknown: "bg-ink-faint",
};

const LABEL: Record<HealthStatus, string> = {
  healthy: "healthy",
  degraded: "degraded",
  unhealthy: "unreachable",
  unknown: "checking…",
};

/** Tiny status dot + label for the topbar. Pulses softly when healthy
 *  so the operator sees the page is alive without a spinner. */
export function HealthDot({ status }: Props) {
  return (
    <div className="flex items-center gap-1.5 text-2xs text-ink-muted">
      <span
        className={`inline-block h-2 w-2 rounded-full ${COLOR[status]} ${
          status === "healthy" ? "animate-pulse-dot" : ""
        }`}
        aria-hidden
      />
      <span>{LABEL[status]}</span>
    </div>
  );
}
