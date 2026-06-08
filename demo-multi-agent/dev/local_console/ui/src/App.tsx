import { useState } from "react";

import { Composer } from "@/components/Composer";
import { SettingsPanel } from "@/components/SettingsPanel";
import { Shell } from "@/components/Shell";
import { Transcript } from "@/components/Transcript";
import { useInvoke } from "@/hooks/useInvoke";
import type { InvokeMode } from "@/types/invoke";

const PLACEHOLDER =
  "Ask matbot — sent as an A2A text message via JSON-RPC /a2a…";

/** Root component. Owns the mode (sync/stream) selection and delegates
 *  the request lifecycle to `useInvoke`. */
export function App() {
  const [mode, setMode] = useState<InvokeMode>("stream");
  const {
    messages,
    busy,
    send,
    cancel,
    clear,
    settings,
    setSettings,
    regenerateIds,
  } = useInvoke();

  return (
    <Shell mode={mode} onModeChange={setMode} busy={busy}>
      <main className="flex min-w-0 flex-1 flex-col">
        <Transcript messages={messages} />
        <Composer
          onSend={(q) => send(q, mode)}
          onCancel={cancel}
          busy={busy}
          placeholder={PLACEHOLDER}
        />
      </main>
      <SettingsPanel
        settings={settings}
        onSettingsChange={setSettings}
        onRegenerateIds={regenerateIds}
        onClearTranscript={clear}
      />
    </Shell>
  );
}
