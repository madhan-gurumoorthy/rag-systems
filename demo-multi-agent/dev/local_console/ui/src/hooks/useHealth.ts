import { useEffect, useState } from "react";

export type HealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown";

interface HealthBody {
  status?: string;
}

/** Poll `/healthz` every 30s. First sample fires on mount so the dot
 *  lights up immediately instead of sitting on `unknown` for half a
 *  minute. */
export function useHealth(): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>("unknown");

  useEffect(() => {
    let cancelled = false;

    const sample = async () => {
      try {
        const res = await fetch("/healthz");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = (await res.json().catch(() => ({}))) as HealthBody;
        if (cancelled) return;
        const raw = body.status ?? "healthy";
        setStatus(
          raw === "healthy" || raw === "degraded" || raw === "unhealthy"
            ? raw
            : "healthy",
        );
      } catch {
        if (!cancelled) setStatus("unhealthy");
      }
    };

    void sample();
    const id = window.setInterval(sample, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return status;
}
