import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { getActiveProfile } from "@/lib/api";

export const PENDING_KEY = "myatelier_pending_outfit";
export const PENDING_TTL_MS = 5 * 60 * 1000;

export const clearPending = () => localStorage.removeItem(PENDING_KEY);

// Only references are stored: the Avatar stays encrypted on the server, garments are already uploaded.
export const savePending = (draft) => {
  const hasData = draft.selectedItems.length || draft.single?.garment_path;
  if (!hasData) { clearPending(); return; }
  try {
    localStorage.setItem(PENDING_KEY, JSON.stringify({ ...draft, profileId: getActiveProfile() || null, timestamp: Date.now() }));
  } catch { /* storage full or disabled: draft is best-effort */ }
};

export const loadPending = () => {
  let d;
  try { d = JSON.parse(localStorage.getItem(PENDING_KEY) || "null"); } catch { d = null; }
  if (!d) return null;
  const valid = Date.now() - (d.timestamp || 0) < PENDING_TTL_MS && (d.profileId || null) === (getActiveProfile() || null);
  if (!valid) { clearPending(); return null; }
  return d;
};

// Debounced (500ms) autosave of the Studio draft + resume/discard flow for the "outfit in sospeso" modal.
export const usePendingDraft = (state, skip, onRestore) => {
  const [draft, setDraft] = useState(null);
  const [ready, setReady] = useState(false);
  const sig = JSON.stringify({ items: state.selectedItems, single: state.single });
  const sigRef = useRef(sig);
  const doneSig = useRef(sig);
  const stateRef = useRef(state);
  sigRef.current = sig;
  stateRef.current = state;

  useEffect(() => {
    const d = skip ? null : loadPending();
    if (d) setDraft(d); else setReady(true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!ready || sig === doneSig.current) return undefined;
    const t = setTimeout(() => savePending(stateRef.current), 500);
    // Flush immediately if the user leaves the tab/app before the debounce fires.
    const flush = (e) => { if (e.type === "pagehide" || document.visibilityState === "hidden") { clearTimeout(t); savePending(stateRef.current); } };
    document.addEventListener("visibilitychange", flush);
    window.addEventListener("pagehide", flush);
    return () => { clearTimeout(t); document.removeEventListener("visibilitychange", flush); window.removeEventListener("pagehide", flush); };
  }, [sig, ready]);

  const close = () => { setDraft(null); doneSig.current = sigRef.current; setReady(true); };
  return {
    draft,
    resume: () => {
      if (Date.now() - draft.timestamp >= PENDING_TTL_MS) {
        clearPending();
        toast.error("Sono passati più di 5 minuti: l'outfit in sospeso è scaduto");
      } else onRestore(draft);
      close();
    },
    discard: () => { clearPending(); close(); },
    markDone: () => { clearPending(); doneSig.current = sigRef.current; },
  };
};
