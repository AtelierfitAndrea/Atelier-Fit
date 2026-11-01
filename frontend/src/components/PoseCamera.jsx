import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { toast } from "sonner";
import { X, Camera, Timer } from "@phosphor-icons/react";

const Silhouette = () => (
  <svg viewBox="0 0 200 520" className="h-[82%] w-auto opacity-70" fill="none" stroke="white" strokeWidth="2.5" strokeDasharray="7 6" data-testid="pose-camera-silhouette">
    <ellipse cx="100" cy="48" rx="30" ry="37" />
    <path d="M86 84 L84 100 Q50 106 40 128 L26 250 Q24 262 34 262 L46 258 L58 160 L62 250 L56 330 L64 500 Q66 512 80 510 L92 508 L98 340 L102 340 L108 508 L120 510 Q134 512 136 500 L144 330 L138 250 L142 160 L154 258 L166 262 Q176 262 174 250 L160 128 Q150 106 116 100 L114 84" />
  </svg>
);

export default function PoseCamera({ open, onClose, onShot }) {
  const video = useRef(null);
  const stream = useRef(null);
  const [ready, setReady] = useState(false);
  const [timer, setTimer] = useState(false);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1920 } }, audio: false })
      .then((s) => {
        if (!alive) { s.getTracks().forEach((t) => t.stop()); return; }
        stream.current = s;
        video.current.srcObject = s;
        video.current.play().then(() => setReady(true)).catch(() => setReady(true));
      })
      .catch(() => { toast.error("Fotocamera non disponibile: consenti l'accesso o carica dalla galleria"); onClose(); });
    return () => { alive = false; stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null; setReady(false); setCount(0); };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const capture = () => {
    const v = video.current;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    c.toBlob((b) => { if (b) onShot(new File([b], `posa-${Date.now()}.jpg`, { type: "image/jpeg" })); }, "image/jpeg", 0.92);
  };
  const shoot = () => {
    if (!timer) { capture(); return; }
    let n = 5;
    setCount(n);
    const id = setInterval(() => {
      n -= 1; setCount(n);
      if (n <= 0) { clearInterval(id); capture(); }
    }, 1000);
  };

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[80] bg-black flex flex-col" data-testid="pose-camera">
      <div className="relative flex-1 overflow-hidden">
        <video ref={video} playsInline muted className="absolute inset-0 w-full h-full object-cover" data-testid="pose-camera-video" />
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none"><Silhouette /></div>
        <p className="absolute top-5 left-0 right-0 text-center text-white text-xs tracking-[0.3em] uppercase px-6">Inquadra tutto il corpo dentro la sagoma</p>
        <button onClick={onClose} className="absolute top-4 right-4 text-white p-2" aria-label="Chiudi" data-testid="pose-camera-close"><X size={26} /></button>
        {count > 0 && <div className="absolute inset-0 flex items-center justify-center text-white font-serif text-8xl" data-testid="pose-camera-countdown">{count}</div>}
      </div>
      <div className="bg-black py-6 flex items-center justify-center gap-10">
        <button onClick={() => setTimer((t) => !t)} className={`flex flex-col items-center text-[10px] tracking-[0.2em] ${timer ? "text-[#D4AF37]" : "text-white/60"}`} data-testid="pose-camera-timer">
          <Timer size={26} /> TIMER 5S
        </button>
        <button onClick={shoot} disabled={!ready || count > 0} aria-label="Scatta"
          className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center disabled:opacity-40 active:scale-95 transition-transform" data-testid="pose-camera-shutter">
          <span className="w-14 h-14 rounded-full bg-white flex items-center justify-center"><Camera size={24} className="text-black" /></span>
        </button>
        <span className="w-[52px]" />
      </div>
    </div>,
    document.body,
  );
}
