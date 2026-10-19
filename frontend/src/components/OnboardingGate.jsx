import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAvatar } from "@/lib/avatar";
import AvatarBox from "@/components/AvatarBox";
import MeasuresForm from "@/components/MeasuresForm";

const STEP_N = { name: 1, measures: 2, photo: 3 };

// First login: name, real measurements, then the Avatar photo for try-ons.
export default function OnboardingGate() {
  const { user, refresh } = useAuth();
  const { avatar, loading } = useAvatar();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState(null);

  const termsOk = user && (!user.terms_current_version || user.terms_version === user.terms_current_version);
  const current = step || (user?.display_name ? null : "name");
  if (!termsOk || loading || !current || current === "done") return null;
  if (current === "photo" && avatar?.path) return null;

  const saveName = async () => {
    setSaving(true);
    try {
      await api.put("/profile/display-name", { name });
      setStep("measures");
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Inserisci il tuo nome"); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm overflow-y-auto p-4 md:p-8" translate="no" data-testid="onboarding-gate">
      <div className="max-w-3xl mx-auto bg-white border hairline p-6 md:p-8">
        <div className="label-caps text-[#8C7355]">Benvenuto in My Atelier · {STEP_N[current]} di 3</div>
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
        {current === "measures" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Dacci le tue misure reali, le salviamo una volta sola!</h2>
            <p className="mt-2 text-sm text-neutral-600">Non dovrai più misurarti: la taglia per ogni brand è calcolata da queste.</p>
            <div className="mt-6"><MeasuresForm onSaved={() => setStep("photo")} /></div>
            <button onClick={() => setStep("photo")} className="mt-4 text-xs text-neutral-500 underline" data-testid="onboarding-skip-measures">Lo faccio dopo</button>
          </>
        )}
        {current === "photo" && (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Ora la tua foto Avatar</h2>
            <p className="mt-2 text-sm text-neutral-600">Una sola foto a corpo intero, dalla testa ai piedi.</p>
            <div className="mt-6"><AvatarBox /></div>
            <button onClick={() => setStep("done")} className="mt-4 text-xs text-neutral-500 underline" data-testid="onboarding-skip-photo">Lo faccio dopo</button>
          </>
        )}
      </div>
    </div>
  );
}
