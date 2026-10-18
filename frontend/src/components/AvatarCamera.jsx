import { useEffect, useRef, useState } from "react";
import { X, Timer, Camera, ArrowsClockwise } from "@phosphor-icons/react";

const MODES = [
  { k: "environment", label: "Posteriore" },
  { k: "user", label: "Frontale" },
  { k: "mirror", label: "Specchio" },
];
const TIMER_S = 5;

function Silhouette() {
  return (
    <svg viewBox="0 0 100 200" className="absolute inset-0 m-auto h-[88%] pointer-events-none" aria-hidden="true" data-testid="avatar-camera-silhouette">
      <g fill="none" stroke="#fff" strokeOpacity="0.85" strokeWidth="1.2" strokeDasharray="3 2">
        <ellipse cx="50" cy="16" rx="10" ry="12" />
        <path d="M40 30 Q50 34 60 30 L76 38 Q80 40 80 46 L84 92 M40 30 L24 38 Q20 40 20 46 L16 92" />
        <path d="M34 40 L34 98 Q50 104 66 98 L66 40" />
        <path d="M36 98 L38 190 M64 98 L62 190 M50 104 L49 186 M50 104 L51 186" />
      </g>
    </svg>
  );
}

export default function AvatarCamera({ open, onClose, onCapture }) {
  const videoRef = useRef();
  const streamRef = useRef();
  const fileRef = useRef();
  const [mode, setMode] = useState("environment");
  const [count, setCount] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setFailed(false);
    const facing = mode === "user" ? "user" : "environment";
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: facing, width: { ideal: 1080 }, height: { ideal: 1920 } }, audio: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = s;
        if (videoRef.current) videoRef.current.srcObject = s;
      })
      .catch(() => setFailed(true));
    if (!navigator.mediaDevices?.getUserMedia) setFailed(true);
    return () => { cancelled = true; streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; };
  }, [open, mode]);

  useEffect(() => {
    if (!count) return undefined;
    const id = setTimeout(() => { if (count === 1) snap(); setCount(count - 1); }, 1000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);

  const snap = () => {
    const v = videoRef.current;
    if (!v?.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    const ctx = c.getContext("2d");
    // Mirror selfies are reversed: flip them back to the true orientation.
    if (mode === "mirror") { ctx.translate(c.width, 0); ctx.scale(-1, 1); }
    ctx.drawImage(v, 0, 0);
    c.toBlob((b) => b && onCapture(new File([b], "avatar.jpg", { type: "image/jpeg" })), "image/jpeg", 0.92);
  };

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] bg-black flex flex-col" data-testid="avatar-camera">
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <span className="label-caps !text-white/80">Il Mio Avatar</span>
        <button onClick={onClose} aria-label="Chiudi" data-testid="avatar-camera-close"><X size={24} /></button>
      </div>
      <div className="relative flex-1 overflow-hidden">
        {failed ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-white px-8 text-center" data-testid="avatar-camera-fallback">
            <p className="text-sm text-white/70">Non riusciamo ad aprire la fotocamera qui. Consenti l&apos;accesso alla fotocamera o scatta con quella del telefono.</p>
            <button onClick={() => fileRef.current?.click()} className="bg-white text-black px-6 py-3 label-caps" data-testid="avatar-camera-native-btn">Apri fotocamera</button>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onCapture(f); }} data-testid="avatar-camera-native-input" />
          </div>
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover"
            style={{ transform: mode === "environment" ? "none" : "scaleX(-1)" }} data-testid="avatar-camera-video" />
        )}
        {!failed && <Silhouette />}
        {!failed && <p className="absolute top-3 inset-x-0 text-center text-xs text-white/80">Allinea il corpo intero, dalla testa ai piedi</p>}
        {count > 0 && <div className="absolute inset-0 flex items-center justify-center font-serif text-8xl text-white" data-testid="avatar-camera-countdown">{count}</div>}
      </div>
      {!failed && (
        <div className="px-4 py-5 flex flex-col items-center gap-4 text-white">
          <div className="flex gap-2">
            {MODES.map((m) => (
              <button key={m.k} onClick={() => setMode(m.k)}
                className={`px-3 py-1.5 text-[11px] tracking-[0.2em] uppercase border ${mode === m.k ? "bg-white text-black border-white" : "border-white/40 text-white/80"}`}
                data-testid={`avatar-camera-mode-${m.k}`}>{m.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-6">
            <button onClick={() => setMode(mode === "user" ? "environment" : "user")} aria-label="Cambia fotocamera" className="text-white/80" data-testid="avatar-camera-flip"><ArrowsClockwise size={26} /></button>
            <button onClick={() => setCount(TIMER_S)} disabled={count > 0}
              className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center hover:scale-105 transition-transform" data-testid="avatar-camera-timer-btn">
              <Timer size={30} />
            </button>
            <button onClick={snap} aria-label="Scatta subito" className="text-white/80" data-testid="avatar-camera-snap-btn"><Camera size={26} /></button>
          </div>
          <span className="text-[11px] text-white/60">Tocca il cerchio: scatto tra {TIMER_S} secondi</span>
        </div>
      )}
    </div>
  );
}
