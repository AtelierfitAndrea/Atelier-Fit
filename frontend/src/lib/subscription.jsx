import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Ctx = createContext({ status: null, loading: true, refresh: () => {}, openPaywall: () => {}, closePaywall: () => {}, paywallOpen: false });

export function SubscriptionProvider({ children }) {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paywallOpen, setPaywallOpen] = useState(false);
  // Founder/admin bypass: unlimited, the 3 free try-ons are never counted and the payment popup never opens.
  const isAdmin = !!user && (user.role === "admin" || user.isFounder === true || user.isAdmin === true || user.is_owner === true
    || (user.email || "").toLowerCase() === "andremo2014@gmail.com");

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/subscription/status");
      setStatus(isAdmin ? { ...data, is_blocked: false, tryons_limit: 9999, tryons_remaining: 9999 } : data);
    } catch (_e) { /* ignore */ } finally { setLoading(false); }
  }, [isAdmin]);

  useEffect(() => { if (user) refresh(); else { setStatus(null); setLoading(false); } }, [user, refresh]);

  useEffect(() => {
    const open = () => { if (isAdmin) return; setPaywallOpen(true); refresh(); };
    window.addEventListener("atelier-paywall", open);
    return () => window.removeEventListener("atelier-paywall", open);
  }, [refresh, isAdmin]);

  return (
    <Ctx.Provider value={{
      status,
      loading,
      refresh,
      paywallOpen: paywallOpen && !isAdmin,
      openPaywall: () => { if (!isAdmin) setPaywallOpen(true); },
      closePaywall: () => setPaywallOpen(false),
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useSubscription = () => useContext(Ctx);
