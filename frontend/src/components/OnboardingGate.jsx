import { useState } from "react";
import { toast } from "sonner";
import { CheckCircle } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAvatar } from "@/lib/avatar";
import AvatarBox from "@/components/AvatarBox";
import MeasuresForm from "@/components/MeasuresForm";

const STEP_N = { name: 1, email: 2, photo: 3, measures: 4 };
export const EMAIL_NOTE = "La tua email serve solo per ritrovare il tuo account se cambi telefono. Zero spam, zero pubblicità, zero vendita a terzi. Mai.";

// First login: name, email (account key), Avatar photo, then real measurements (optional).
export default function OnboardingGate() {
  const { user, refresh } = useAuth();
  const { avatar, loading } = useAvatar();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState(null);

  const termsOk = user && (!user.terms_current_version || user.terms_version === user.terms_current_version);
  const current = step || (user?.display_name ? null : "name");
  if (!termsOk || loading || !current || current === "done") return null;

  const confirmEmail = async () => {
    setSaving(true);
    try { await api.post("/profile/confirm-email", { email: user.email }); setStep("photo"); }
    catch (e) { toast.error(e?.response?.data?.detail || "Conferma non riuscita"); }
    finally { setSaving(false); }
  };

  const saveName = async () => {
    setSaving(true);
    try {
      await api.put("/profile/display-name", { name });
      setStep("email");
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Inserisci il tuo nome"); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm overflow-y-auto p-4 md:p-8" translate="no" data-testid="onboarding-gate">
      <div className="max-w-3xl mx-auto bg-white border hairline p-6 md:p-8">
        <div className="label-caps text-[#8C7355]">Benvenuto in My Atelier · {STEP_N[current]} di 4</div>
        {current === "name" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Come ti chiami?</h2>
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder="Il tuo nome"
              className="mt-6 w-full border hairline px-4 py-3 font-serif text-xl outline-none focus:border-[#0A0A0A]" data-testid="onboarding-name-input" />
            <button onClick={saveName} disabled={!name.trim() || saving} className="btn-primary mt-5 disabled:opacity-40" data-testid="onboarding-name-submit">
              {saving ? "Salvo…" : "Continua"}
            </button>
          </>
        )}
        {current === "email" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">La tua email</h2>
            <div className="mt-6 flex items-center border hairline px-4 py-3 bg-[#FAF8F5]">
              <input readOnly value={user.email || ""} className="flex-1 bg-transparent font-serif text-xl outline-none" data-testid="onboarding-email-input" />
              <span className="flex items-center gap-1 text-xs text-emerald-700 shrink-0" data-testid="onboarding-email-verified"><CheckCircle size={16} weight="fill" /> Verificata con Google</span>
            </div>
            <p className="mt-2 text-xs text-neutral-500 leading-relaxed" data-testid="onboarding-email-note">{EMAIL_NOTE}</p>
            <button onClick={confirmEmail} disabled={saving} className="btn-primary mt-5 disabled:opacity-40" data-testid="onboarding-email-confirm">
              {saving ? "Salvo…" : "Conferma e continua"}
            </button>
          </>
        )}
        {current === "measures" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Dacci le tue misure reali, le salviamo noi per te!</h2>
            <p className="mt-2 text-sm text-neutral-600">Non dovrai più misurarti: la taglia per ogni brand è calcolata da queste.</p>
            <div className="mt-6"><MeasuresForm onSaved={() => setStep("done")} /></div>
            <button onClick={() => setStep("done")} className="mt-4 text-xs text-neutral-500 underline" data-testid="onboarding-skip-measures">Lo faccio dopo</button>
          </>
        )}
        {current === "photo" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Ora la tua foto Avatar</h2>
            <p className="mt-2 text-sm text-neutral-600">Una sola foto a corpo intero, dalla testa ai piedi.</p>
            <div className="mt-6"><AvatarBox /></div>
            <button onClick={() => setStep("measures")} className="btn-primary mt-4" disabled={!avatar?.path} data-testid="onboarding-photo-next">Continua</button>
            <button onClick={() => setStep("measures")} className="ml-4 mt-4 text-xs text-neutral-500 underline" data-testid="onboarding-skip-photo">Lo faccio dopo</button>
          </>
        )}
      </div>
    </div>
  );
}
