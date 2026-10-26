import { useEffect } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const KEY = "atelier_ref";

// Remember ?ref=CODE from the invite link (before login) and link the new account to the inviter after login.
try {
  const ref = new URLSearchParams(window.location.search).get("ref");
  if (ref && /^[A-Za-z0-9]{4,16}$/.test(ref)) localStorage.setItem(KEY, ref);
} catch (_e) { /* ignore */ }

export default function ReferralClaimer() {
  const { user } = useAuth();
  useEffect(() => {
    let code = null;
    try { code = localStorage.getItem(KEY); } catch (_e) { return; }
    if (!user || !code) return;
    api.post("/referral/claim", { code })
      .then(({ data }) => { if (!data.already) toast.success("Invito accettato: alla tua prima prova ricevi 5 prove bonus"); })
      .catch(() => {})
      .finally(() => { try { localStorage.removeItem(KEY); } catch (_e) { /* ignore */ } });
  }, [user]);
  return null;
}
