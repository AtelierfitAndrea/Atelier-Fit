import { useState } from "react";
import { toast } from "sonner";
import { FileText } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function TermsGate() {
  const { user, refresh } = useAuth();
  const [checked, setChecked] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!user || !user.terms_current_version || user.terms_version === user.terms_current_version) return null;

  const accept = async () => {
    setSaving(true);
    try {
      await api.post("/terms/accept", { version: user.terms_current_version, accepted: true });
      await refresh();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Errore");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/40 backdrop-blur-sm p-6" translate="no" data-testid="terms-gate">
      <div className="max-w-lg w-full bg-white border hairline p-6 md:p-8">
        <FileText size={30} weight="duotone" className="text-[#8C7355]" />
        <h2 className="mt-3 font-serif text-2xl md:text-3xl tracking-tight">Prima di iniziare</h2>
        <p className="mt-3 text-sm md:text-base leading-relaxed text-neutral-700">
          Per usare Atelier Fit ti chiediamo di leggere e accettare i Termini e Condizioni.
          {user.terms_version && " I Termini sono stati aggiornati."}
        </p>
        <label className="mt-6 flex items-start gap-3 cursor-pointer" data-testid="terms-gate-label">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="mt-1 w-4 h-4 accent-[#0A0A0A]"
            data-testid="terms-gate-checkbox"
          />
          <span className="text-sm leading-relaxed">
            Ho letto e accetto i{" "}
            <a href="/termini" target="_blank" rel="noopener noreferrer" className="underline" data-testid="terms-gate-link">
              Termini e Condizioni
            </a>{" "}
            di Atelier Fit (versione {user.terms_current_version}).
          </span>
        </label>
        <button
          onClick={accept}
          disabled={!checked || saving}
          className="mt-6 btn-primary w-full justify-center disabled:opacity-40 disabled:cursor-not-allowed"
          data-testid="terms-gate-accept-btn"
        >
          {saving ? "…" : "Accetta e continua"}
        </button>
      </div>
    </div>
  );
}
