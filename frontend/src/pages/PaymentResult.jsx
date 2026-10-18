import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useSubscription } from "@/lib/subscription";

const POLL_MS = 2000;
const MAX_TRIES = 15;

export default function PaymentResult() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { refresh } = useSubscription();
  const started = useRef(false);
  const sessionId = new URLSearchParams(location.search).get("session_id");
  const cancelled = location.pathname === "/payment/cancel";

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (cancelled || !sessionId) {
      toast("Pagamento annullato: nessun addebito.");
      navigate("/dashboard", { replace: true });
      return;
    }
    (async () => {
      for (let i = 0; i < MAX_TRIES; i++) {
        try {
          const { data } = await api.get(`/payments/status/${sessionId}`);
          if (data.payment_status === "paid") {
            await refresh();
            toast.success(t("sub.paywall.success"));
            navigate("/dashboard", { replace: true });
            return;
          }
          if (["expired", "failed"].includes(data.payment_status)) break;
        } catch { /* retry */ }
        await new Promise((r) => setTimeout(r, POLL_MS));
      }
      toast.error("Pagamento non confermato. Se ti è stato addebitato, scrivi a studio@myatelierapp.it");
      navigate("/dashboard", { replace: true });
    })();
  }, [cancelled, sessionId, navigate, refresh, t]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="text-xs tracking-[0.3em] uppercase text-neutral-500" data-testid="payment-result-loader">
        Conferma pagamento in corso…
      </div>
    </div>
  );
}
