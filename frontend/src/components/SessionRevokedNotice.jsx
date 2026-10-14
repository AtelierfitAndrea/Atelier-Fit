import { useEffect, useState } from "react";
import { UserCircle } from "@phosphor-icons/react";
import { SESSION_REVOKED_KEY } from "@/lib/api";

const readFlag = () => { try { return localStorage.getItem(SESSION_REVOKED_KEY) === "1"; } catch { return false; } };

export default function SessionRevokedNotice() {
  const [open, setOpen] = useState(readFlag);

  useEffect(() => {
    const on = () => setOpen(true);
    window.addEventListener("atelier-session-revoked", on);
    return () => window.removeEventListener("atelier-session-revoked", on);
  }, []);

  if (!open) return null;
  const close = () => {
    try { localStorage.removeItem(SESSION_REVOKED_KEY); } catch (_e) { /* ignore */ }
    setOpen(false);
    if (window.location.pathname !== "/") window.location.href = "/";
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 backdrop-blur-sm p-6" translate="no" data-testid="session-revoked-notice">
      <div className="max-w-md w-full bg-[#E8F5E9] border border-[#A5D6A7] text-[#1B5E20] p-6">
        <UserCircle size={32} weight="duotone" />
        <h2 className="mt-3 font-semibold text-lg">Il tuo Atelier è stato aperto su un altro dispositivo</h2>
        <p className="mt-2 text-sm leading-relaxed">
          Per questo ti abbiamo disconnesso qui. L&apos;account è personale: non è per bloccarti, è per proteggere la tua vestibilità. Se presti l&apos;account, il nostro sarto digitale sbaglia tutto.
        </p>
        <p className="mt-2 text-sm leading-relaxed">Se eri tu, accedi di nuovo da questo dispositivo quando vuoi.</p>
        <button onClick={close} className="mt-5 bg-[#1B5E20] text-white px-5 py-2 label-caps" data-testid="session-revoked-ok-btn">
          Ho capito
        </button>
      </div>
    </div>
  );
}
