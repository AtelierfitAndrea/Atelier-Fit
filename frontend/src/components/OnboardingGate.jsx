import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAvatar } from "@/lib/avatar";
import AvatarBox from "@/components/AvatarBox";

// First login: ask the name, then the single Avatar photo.
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
      setStep("photo");
      await refresh();
    } catch (e) { toast.error(e?.response?.data?.detail || "Inserisci il tuo nome"); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-[80] bg-black/50 backdrop-blur-sm overflow-y-auto p-4 md:p-8" translate="no" data-testid="onboarding-gate">
      <div className="max-w-3xl mx-auto bg-white border hairline p-6 md:p-8">
        <div className="label-caps text-[#8C7355]">Benvenuto in My Atelier · {current === "name" ? "1" : "2"} di 2</div>
        {current === "name" ? (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Come ti chiami?</h2>
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder="Il tuo nome"
              onKeyDown={(e) => { if (e.key === "Enter" && name.trim()) saveName(); }}
              className="mt-6 w-full border hairline px-4 py-3 font-serif text-xl outline-none focus:border-[#0A0A0A]" data-testid="onboarding-name-input" />
            <button onClick={saveName} disabled={!name.trim() || saving} className="btn-primary mt-5 disabled:opacity-40" data-testid="onboarding-name-submit">
              {saving ? "Salvo…" : "Continua"}
            </button>
          </>
        ) : (
          <>
            <h2 className="mt-3 font-serif text-3xl tracking-tight">Ora la tua foto Avatar</h2>
            <p className="mt-2 text-sm text-neutral-600">Una sola foto a corpo intero: calcoliamo le misure e la usiamo per ogni prova.</p>
            <div className="mt-6"><AvatarBox /></div>
            <button onClick={() => setStep("done")} className="mt-4 text-xs text-neutral-500 underline" data-testid="onboarding-skip-photo">Lo faccio dopo</button>
          </>
        )}
      </div>
    </div>
  );
}
