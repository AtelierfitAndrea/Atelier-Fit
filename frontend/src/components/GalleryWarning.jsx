import { useState } from "react";
import { WarningCircle } from "@phosphor-icons/react";

export const OLD_PHOTO_DAYS = 30;

export const photoAgeDays = async (file) => {
  let date = null;
  try {
    const exifr = (await import("exifr")).default;
    const tags = await exifr.parse(file, ["DateTimeOriginal", "CreateDate"]);
    date = tags?.DateTimeOriginal || tags?.CreateDate || null;
  } catch (_e) { date = null; }
  const ts = date instanceof Date && !isNaN(date) ? date.getTime() : file.lastModified;
  return { days: Math.floor((Date.now() - ts) / 86400000), fromExif: !!date };
};

function Step({ testid, title, text, label, onOk, onCancel }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="bg-white max-w-md w-full p-6 border-2 border-[#B45309] fade-up" data-testid={testid}>
      <div className="flex items-center gap-2 text-[#B45309]"><WarningCircle size={22} weight="fill" /><span className="label-caps">Attenzione</span></div>
      <h3 className="font-serif text-2xl mt-2 leading-tight">{title}</h3>
      <p className="text-sm text-neutral-700 mt-3">{text}</p>
      <label className="mt-4 flex items-start gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} className="mt-1" data-testid={`${testid}-checkbox`} />
        <span>{label}</span>
      </label>
      <div className="mt-5 flex gap-3">
        <button disabled={!ok} onClick={onOk} className="btn-primary disabled:opacity-40" data-testid={`${testid}-confirm`}>Procedi</button>
        <button onClick={onCancel} className="btn-ghost" data-testid={`${testid}-cancel`}>Annulla</button>
      </div>
    </div>
  );
}

export default function GalleryWarning({ info, onAccept, onCancel }) {
  const [step, setStep] = useState(1);
  if (!info) return null;
  const old = info.days > OLD_PHOTO_DAYS;
  return (
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-4" data-testid="gallery-warning">
      {step === 1 ? (
        <Step key="s1" testid="gallery-warning-1" title="Foto non recente"
          text="Attenzione: foto non recente, misurazioni e vestibilità potrebbero non essere attendibili per cambiamenti fisici nel tempo."
          label="Accetto e procedo a mio rischio" onCancel={onCancel}
          onOk={() => (old ? setStep(2) : onAccept())} />
      ) : (
        <Step key="s2" testid="gallery-warning-2" title={`Foto di ${info.days} giorni fa`}
          text={`Questa foto ha più di ${OLD_PHOTO_DAYS} giorni${info.fromExif ? "" : " (data stimata dal file)"}. Il tuo corpo potrebbe essere cambiato: misure e taglie suggerite potrebbero essere sbagliate. Ti consigliamo di scattare una foto nuova.`}
          label="Ho capito, uso comunque questa foto a mio rischio" onCancel={onCancel} onOk={onAccept} />
      )}
    </div>
  );
}
