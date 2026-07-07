/** Display-layer mapping for raw activity-log messages (V-1). */

const MESSAGE_PATTERNS: { pattern: RegExp; display: string | ((m: RegExpMatchArray) => string) }[] = [
  {
    pattern: /^retry_(\w+)\s*→\s*phase\s+(\w+)/i,
    display: (m) => `retry → ${m[2]}`,
  },
  {
    pattern: /^retry_(\w+)/i,
    display: (m) => `retry → ${m[1]}`,
  },
  {
    pattern: /^__interrupt__:/i,
    display: "⏸ paused for human review",
  },
];

/** Human-readable log line; unknown messages pass through unchanged. */
export function formatLogMessage(raw: string): string {
  const trimmed = raw.trim();
  for (const { pattern, display } of MESSAGE_PATTERNS) {
    const match = trimmed.match(pattern);
    if (match) {
      return typeof display === "function" ? display(match) : display;
    }
  }
  return raw;
}

/** Compact time without seconds (HH:MM). */
export function formatLogTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}
