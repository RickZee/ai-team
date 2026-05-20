import { useEffect, useState } from "react";
import { getBackends, getProfiles } from "./useApi";
import type { BackendInfo, ProfileInfo } from "../types";

export function useCatalog() {
  const [backends, setBackends] = useState<BackendInfo[]>([]);
  const [profiles, setProfiles] = useState<Record<string, ProfileInfo>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [bRes, pRes] = await Promise.all([getBackends(), getProfiles()]);
        if (cancelled) return;
        setBackends(bRes.backends);
        setProfiles(pRes as Record<string, ProfileInfo>);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load catalog");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { backends, profiles, profileNames: Object.keys(profiles), loading, error };
}
