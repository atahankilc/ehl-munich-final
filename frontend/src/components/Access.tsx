// Access panel in the bottom-left dock (D-063): on a cloud deployment anyone can look, changes need the shared access
// key. The key stays in this browser (lib/api.ts) and goes with every request; the server says whether it is right.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAccessKey, setAccessKey } from "@/lib/api";

export type AccessState = { required: boolean; valid: boolean };

export function useAccess() {
  return useQuery({ queryKey: ["access"], queryFn: () => api.get<AccessState>("/api/access"), staleTime: Infinity });
}

export function AccessPanel() {
  const qc = useQueryClient();
  const access = useAccess();
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const stored = getAccessKey();
  const valid = access.data?.valid ?? false;

  const apply = async (next: string) => {
    setBusy(true);
    setAccessKey(next);
    await qc.invalidateQueries({ queryKey: ["access"] });
    setKey("");
    setBusy(false);
  };

  return (
    <div className="guide access">
      <p className="guide-title">Access</p>
      <p className="guide-lead">
        Anyone can look around. Decisions, weights, settings and AI runs need the access key.
      </p>
      <p className="access-state" data-ok={valid || undefined} role="status">
        {access.isPending ? "Checking…" : valid ? "Key accepted: you can make changes."
          : stored ? "That key is wrong: read-only." : "No key: read-only."}
      </p>
      <form className="access-row" onSubmit={(e) => { e.preventDefault(); if (key.trim()) void apply(key.trim()); }}>
        <input className="access-input" type="password" autoComplete="off" spellCheck={false} aria-label="Access key"
               placeholder={stored ? "Replace the key" : "Access key"} value={key} onChange={(e) => setKey(e.target.value)} />
        <button type="submit" className="access-btn primary" disabled={!key.trim() || busy}>Unlock</button>
        {stored && <button type="button" className="access-btn" disabled={busy} onClick={() => void apply("")}>Forget</button>}
      </form>
    </div>
  );
}
