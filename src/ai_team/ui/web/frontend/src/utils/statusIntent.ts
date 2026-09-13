export const STATUS_INTENT = {
  running: "accent",
  connecting: "neutral",
  complete: "success",
  complete_approved: "success",
  error: "danger",
  cancelled: "warning",
  cancelling: "warning",
  awaiting_human: "special",
  pending: "neutral",
  idle: "neutral",
  working: "warning",
  done: "success",
} as const;

export type StatusIntent = (typeof STATUS_INTENT)[keyof typeof STATUS_INTENT];

/** Map a run or agent status string to a chip intent. */
export function statusIntent(status: string): StatusIntent {
  return STATUS_INTENT[status as keyof typeof STATUS_INTENT] ?? "neutral";
}

export function statusChipClass(status: string): string {
  return `chip chip-sm chip-${statusIntent(status)}`;
}

export function statusChipClassMd(status: string): string {
  return `chip chip-md chip-${statusIntent(status)}`;
}
