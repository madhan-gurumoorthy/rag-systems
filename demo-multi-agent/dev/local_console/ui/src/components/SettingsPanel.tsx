import type { RequestSettings } from "@/types/invoke";

interface Props {
  settings: RequestSettings;
  onSettingsChange: (s: RequestSettings) => void;
  onRegenerateIds: () => void;
  onClearTranscript: () => void;
}

/**
 * Right-side drawer for the A2A request settings.
 *
 * - `agent_id` selects the pack/skill the gateway should route to.
 * - `session_id` is reused as the A2A `context_id`, so successive
 *   sends with the same value land in the same matbot session.
 * - `message_id` stamps the outgoing `Message.messageId`.
 * - `metadata` JSON is shallow-merged onto `message.metadata` before
 *   the send, for pack-specific knobs.
 */
export function SettingsPanel({
  settings,
  onSettingsChange,
  onRegenerateIds,
  onClearTranscript,
}: Props) {
  const update =
    <K extends keyof RequestSettings>(key: K) =>
    (v: string) =>
      onSettingsChange({ ...settings, [key]: v });

  return (
    <aside className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-[var(--hairline)] bg-surface-1 p-4">
      <header className="flex items-baseline justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
          A2A request
        </h2>
        <button
          type="button"
          onClick={onRegenerateIds}
          className="text-2xs text-accent hover:text-accent-strong"
          title="Generate a fresh session-id and message-id"
        >
          regenerate
        </button>
      </header>

      <Field label="agent_id">
        <Input
          value={settings.agentId}
          onChange={update("agentId")}
          placeholder="(default skill)"
        />
      </Field>
      <Field label="session_id (context_id)">
        <Input
          value={settings.sessionId}
          onChange={update("sessionId")}
          mono
        />
      </Field>
      <Field label="message_id">
        <Input
          value={settings.messageId}
          onChange={update("messageId")}
          mono
        />
      </Field>

      <div className="border-t border-[var(--hairline)] pt-4">
        <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          metadata
        </h2>
        <p className="mb-2 text-2xs text-ink-faint">
          JSON object shallow-merged onto{" "}
          <code className="font-mono text-accent">message.metadata</code>{" "}
          before sending.
        </p>
        <textarea
          className="min-h-32 w-full rounded-md border border-[var(--hairline)] bg-surface-0 px-2.5 py-1.5 font-mono text-xs text-ink focus:border-accent focus:outline-none"
          value={settings.metadataJson}
          spellCheck={false}
          onChange={(e) =>
            onSettingsChange({ ...settings, metadataJson: e.target.value })
          }
          placeholder='{"user_id": "..."}'
        />
      </div>

      <div className="mt-auto pt-4">
        <button
          type="button"
          onClick={onClearTranscript}
          className="w-full rounded-md border border-[var(--hairline)] bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-muted hover:border-danger hover:text-danger"
        >
          Clear transcript
        </button>
      </div>
    </aside>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-2xs uppercase tracking-wider text-ink-muted">
      <span>{label}</span>
      {children}
    </label>
  );
}

interface InputProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  mono?: boolean;
}

function Input({ value, onChange, placeholder, mono }: InputProps) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      spellCheck={false}
      placeholder={placeholder}
      className={`w-full rounded-md border border-[var(--hairline)] bg-surface-0 px-2.5 py-1.5 ${
        mono ? "font-mono text-xs" : "text-sm"
      } text-ink placeholder-ink-faint focus:border-accent focus:outline-none`}
    />
  );
}
