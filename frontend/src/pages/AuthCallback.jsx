import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const hasProcessed = useRef(false);
  const { refresh } = useAuth();

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const hash = location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    const sid = match ? match[1] : null;
    if (!sid) {
      navigate("/", { replace: true });
      return;
    }
    (async () => {
      try {
        await api.post("/auth/session", { session_id: sid });
        window.history.replaceState(null, "", "/dashboard");
        await refresh();
        navigate("/dashboard", { replace: true });
      } catch {
        navigate("/", { replace: true });
      }
    })();
  }, [location.hash, navigate, refresh]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-xs tracking-[0.3em] uppercase text-neutral-500" data-testid="auth-callback-loader">
        Signing you in
      </div>
    </div>
  );
}
