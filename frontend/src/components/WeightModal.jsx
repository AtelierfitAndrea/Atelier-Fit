import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { X } from "@phosphor-icons/react";

export default function WeightModal({ open, onClose, onSaved }) {
  const [weight, setWeight] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) setWeight(""); }, [open]);

  if (!open) return null;

  const save = async () => {
    const w = Number(weight);
    if (!w || w < 25 || w > 300) { toast.error("Inserisci un peso valido in kg"); return; }
    setSaving(true);
    // Optimistic — update the UI immediately so the animation plays
    toast.success("Peso aggiornato!");
    onSaved?.();
    onClose();
    try {
      await api.post("/profile/weight-history", { weight_kg: w });
    } catch {
      toast.error("Salvataggio sul server non riuscito");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      data-testid="weight-modal"
    >
      <div className="bg-white border hairline w-full max-w-md mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <div className="label-caps">Controllo peso</div>
            <h3 className="font-serif text-2xl mt-1">Aggiorna il tuo peso</h3>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-black" data-testid="weight-modal-close">
            <X size={20} weight="bold" />
          </button>
        </div>
        <p className="text-sm text-neutral-600 mt-2">
          Serve per mantenere taglie accurate e profilo affidabile per i brand partner.
        </p>
        <div className="mt-6">
          <label className="block">
            <span className="label-caps block mb-2">Peso (kg)</span>
            <div className="flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
              <input
                autoFocus
                type="number"
                step="0.1"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="—"
                onKeyDown={(e) => { if (e.key === "Enter") save(); }}
                className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl"
                data-testid="weight-modal-kg"
              />
              <span className="px-3 text-xs text-neutral-500">kg</span>
            </div>
          </label>
        </div>
        <div className="mt-6 flex gap-3">
          <button onClick={save} disabled={saving} className="btn-primary flex-1" data-testid="weight-modal-save">
            {saving ? "Salvo..." : "Salva"}
          </button>
          <button onClick={onClose} className="btn-ghost">Annulla</button>
        </div>
      </div>
    </div>
  );
}
