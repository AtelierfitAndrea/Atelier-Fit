import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { X } from "@phosphor-icons/react";

export default function WeightModal({ open, onClose, onSaved, initialDate }) {
  const [weight, setWeight] = useState("");
  const [date, setDate] = useState(initialDate || new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setWeight("");
      setDate(new Date().toISOString().slice(0, 10));
    }
  }, [open]);

  if (!open) return null;

  const save = async () => {
    const w = Number(weight);
    if (!w || w < 25 || w > 300) { toast.error("Inserisci un peso valido in kg"); return; }
    setSaving(true);
    try {
      const recorded_at = new Date(date + "T12:00:00").toISOString();
      await api.post("/profile/weight-history", { weight_kg: w, recorded_at });
      toast.success("Peso aggiornato — taglie ricalcolate");
      onSaved?.();
      onClose();
    } catch { toast.error("Salvataggio non riuscito"); }
    finally { setSaving(false); }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      data-testid="weight-modal"
    >
      <div
        className="bg-white border hairline w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
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
        <div className="mt-6 grid grid-cols-1 gap-4">
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
                className="w-full px-3 py-3 bg-transparent outline-none font-serif text-xl"
                data-testid="weight-modal-kg"
              />
              <span className="px-3 text-xs text-neutral-500">kg</span>
            </div>
          </label>
          <label className="block">
            <span className="label-caps block mb-2">Data</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              max={new Date().toISOString().slice(0, 10)}
              className="w-full px-3 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] transition-colors font-serif text-lg"
              data-testid="weight-modal-date"
            />
          </label>
        </div>
        <div className="mt-6 flex gap-3">
          <button onClick={save} disabled={saving} className="btn-primary flex-1" data-testid="weight-modal-save">
            {saving ? "Salvo..." : "Salva peso"}
          </button>
          <button onClick={onClose} className="btn-ghost">Annulla</button>
        </div>
      </div>
    </div>
  );
}
