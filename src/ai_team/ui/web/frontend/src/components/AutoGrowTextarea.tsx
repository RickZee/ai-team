import { useEffect, useRef } from "react";

interface AutoGrowTextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxRows?: number;
  id?: string;
  "aria-describedby"?: string;
  "data-testid"?: string;
}

/** Textarea that grows with content up to maxRows. */
export function AutoGrowTextarea({
  value,
  onChange,
  placeholder,
  maxRows = 12,
  id,
  "aria-describedby": describedBy,
  "data-testid": testId,
}: AutoGrowTextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const lineHeight = parseInt(getComputedStyle(el).lineHeight, 10) || 22;
    const maxHeight = lineHeight * maxRows;
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, [value, maxRows]);

  return (
    <textarea
      ref={ref}
      id={id}
      aria-describedby={describedBy}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      rows={3}
      data-testid={testId}
      className="auto-grow-textarea"
    />
  );
}
