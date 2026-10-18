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
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [gender, setGender] = useState("female");
  const bodyOk = Number(height) >= 120 && Number(height) <= 230 && Number(weight) >= 40 && Number(weight) <= 150;
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState(null);

  const termsOk = user && (!user.terms_current_version || user.terms_version === user.terms_current_version);
  const current = step || (user?.display_name ? null : "name");
  if (!termsOk || loading || !current || current === "done") return null;
  if (current === "photo" && avatar?.path) return null;

  const saveName = async () => {
    setSaving(true);
    try {
      await api.post("/profile/quick-estimate", { height_cm: Number(height), weight_kg: Number(weight), gender });
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
            <p className="mt-2 text-sm text-neutral-600">Nome, altezza e peso: li chiediamo una volta sola.</p>
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder="Il tuo nome"
              className="mt-6 w-full border hairline px-4 py-3 font-serif text-xl outline-none focus:border-[#0A0A0A]" data-testid="onboarding-name-input" />
            <div className="mt-6 label-caps">Altezza e peso · servono per la precisione al 98%</div>
            <div className="mt-3 flex flex-wrap gap-3 items-center">
              {[["cm", height, setHeight, "170", "onboarding-height-input"], ["kg", weight, setWeight, "65", "onboarding-weight-input"]].map(([u, v, set, ph, id]) => (
                <div key={u} className="flex items-center border hairline w-36 focus-within:border-[#0A0A0A]">
                  <input type="number" inputMode="numeric" value={v} placeholder={ph} onChange={(e) => set(e.target.value)}
                    className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl" data-testid={id} />
                  <span className="px-3 text-xs text-neutral-500">{u}</span>
                </div>
              ))}
              {[["female", "Donna"], ["male", "Uomo"]].map(([k, l]) => (
                <button key={k} type="button" onClick={() => setGender(k)}
                  className={`px-4 py-3 label-caps border hairline ${gender === k ? "bg-[#0A0A0A] !text-white" : "bg-white"}`} data-testid={`onboarding-gender-${k}`}>{l}</button>
              ))}
            </div>
            <button onClick={saveName} disabled={!name.trim() || !bodyOk || saving} className="btn-primary mt-5 disabled:opacity-40" data-testid="onboarding-name-submit">
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
