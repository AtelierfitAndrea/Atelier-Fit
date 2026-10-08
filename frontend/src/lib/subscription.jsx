import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const Ctx = createContext({ status: null, loading: true, refresh: () => {}, openPaywall: () => {}, closePaywall: () => {}, paywallOpen: false });

export function SubscriptionProvider({ children }) {
  const { user } = useAuth();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paywallOpen, setPaywallOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/subscription/status");
      setStatus(data);
    } catch (_e) { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (user) refresh(); else { setStatus(null); setLoading(false); } }, [user, refresh]);

  return (
    <Ctx.Provider value={{
      status,
      loading,
      refresh,
      paywallOpen,
      openPaywall: () => setPaywallOpen(true),
      closePaywall: () => setPaywallOpen(false),
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useSubscription = () => useContext(Ctx);
