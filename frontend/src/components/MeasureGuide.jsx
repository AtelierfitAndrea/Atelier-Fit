import { cloneElement } from "react";
import { X } from "@phosphor-icons/react";

export const GUIDES = {
  height_cm: { title: "Altezza", text: "In piedi scalzo, schiena e talloni contro il muro: segna il punto più alto della testa e misura fino a terra." },
  chest_cm: { title: "Torace", text: "Passa il metro sotto le ascelle, sul punto più pieno del petto. Tienilo orizzontale e senza stringere." },
  waist_cm: { title: "Vita", text: "Misura nel punto più stretto del busto, appena sopra l'ombelico, respirando normalmente." },
  hips_cm: { title: "Fianchi", text: "Piedi uniti: misura il punto più largo di glutei e fianchi, con il metro orizzontale." },
  shoulder_cm: { title: "Spalle", text: "Da un'estremità della spalla all'altra, passando dietro il collo lungo la parte alta della schiena." },
  foot_cm: { title: "Lunghezza piede", text: "Scalzo, tallone contro il muro e piede ben appoggiato: misura dal tallone alla punta dell'alluce. Misura entrambi i piedi e usa il più lungo." },
  inseam_cm: { title: "Lunghezza gamba", text: "Dall'inguine fino alla caviglia, lungo l'interno gamba. In alternativa misura un pantalone che ti sta bene." },
};

export const BODY = "M54 34 L54 40 L34 46 Q28 48 27 56 L22 120 L28 121 L36 64 L40 100 L37 128 L42 245 L56 245 L59 140 L61 140 L64 245 L78 245 L83 128 L80 100 L84 64 L92 121 L98 120 L93 56 Q92 48 86 46 L66 40 L66 34 Z";

const TAPE = {
  height_cm: <path d="M108 9 L108 245" />,
  chest_cm: <ellipse cx="60" cy="62" rx="27" ry="5" />,
  waist_cm: <ellipse cx="60" cy="100" rx="22" ry="4.5" />,
  hips_cm: <ellipse cx="60" cy="128" rx="25" ry="5" />,
  shoulder_cm: <path d="M33 46 Q60 40 87 46" />,
  inseam_cm: <path d="M57 141 L52 242" />,
};

const TAPE_CSS = `
  .mg-tape{fill:none;stroke:#8C7355;stroke-width:1.6;stroke-dasharray:100;stroke-linecap:round;animation:mgDraw 5s ease-in-out infinite}
  @keyframes mgDraw{0%{stroke-dashoffset:100;opacity:1}50%{stroke-dashoffset:0;opacity:1}85%{stroke-dashoffset:0;opacity:1}100%{stroke-dashoffset:0;opacity:0}}
`;

function FootFigure() {
  return (
    <svg viewBox="0 0 200 110" className="w-56 h-auto mx-auto" data-testid="measure-guide-figure-foot_cm">
      <style>{TAPE_CSS}</style>
      <path d="M14 20 L14 92" stroke="#0A0A0A" strokeWidth="0.8" />
      <path d="M16 70 Q16 52 34 50 L120 44 Q150 42 170 52 Q188 60 186 72 Q184 82 168 82 L40 84 Q16 86 16 70 Z" fill="none" stroke="#0A0A0A" strokeWidth="0.8" strokeLinejoin="round" />
      <path d="M8 92 L194 92" stroke="#0A0A0A" strokeWidth="0.5" strokeDasharray="2 3" />
      <path d="M16 100 L186 100" pathLength="100" className="mg-tape" data-testid="measure-guide-tape" />
      <path d="M16 96 L16 104 M186 96 L186 104" stroke="#8C7355" strokeWidth="1" />
      <text x="16" y="16" fontSize="7" fill="#8C7355">tallone</text>
      <text x="168" y="40" fontSize="7" fill="#8C7355">punta</text>
    </svg>
  );
}

function Figure({ field }) {
  if (field === "foot_cm") return <FootFigure />;
  return (
    <svg viewBox="0 0 120 260" className="w-40 h-auto mx-auto" data-testid={`measure-guide-figure-${field}`}>
      <style>{TAPE_CSS}</style>
      <circle cx="60" cy="22" r="11" fill="none" stroke="#0A0A0A" strokeWidth="0.8" />
      <path d={BODY} fill="none" stroke="#0A0A0A" strokeWidth="0.8" strokeLinejoin="round" />
      {cloneElement(TAPE[field], { pathLength: 100, className: "mg-tape", "data-testid": "measure-guide-tape" })}
    </svg>
  );
}

export default function MeasureGuide({ field, onClose }) {
  if (!field) return null;
  const g = GUIDES[field];
  return (
    <div className="fixed inset-0 z-[90] bg-black/50 flex items-center justify-center p-4" onClick={onClose} data-testid="measure-guide">
      <div className="bg-white max-w-sm w-full p-6 border hairline fade-up relative" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-3 right-3" aria-label="Chiudi" data-testid="measure-guide-close"><X size={18} /></button>
        <div className="label-caps text-[#8C7355]">Guarda come · 5 sec</div>
        <h3 className="font-serif text-2xl mt-1" data-testid="measure-guide-title">{g.title}</h3>
        <div className="mt-4 bg-[#FAF8F5] py-4"><Figure field={field} /></div>
        <p className="mt-4 text-sm text-neutral-700 leading-relaxed" data-testid="measure-guide-text">{g.text}</p>
      </div>
    </div>
  );
}
