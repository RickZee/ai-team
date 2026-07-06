import { useEffect } from "react";

/**
 * Set the document title while a component is mounted, restoring the previous
 * title on unmount. Pass `null` to leave the title untouched (e.g. when another
 * effect owns it, like the Dashboard's "⏸ Action needed" HITL override).
 */
export function useDocumentTitle(title: string | null): void {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = title;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
