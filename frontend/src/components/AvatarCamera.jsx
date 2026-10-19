import { useEffect, useRef, useState } from "react";
import { X, Timer, Camera, ArrowsClockwise, Flashlight } from "@phosphor-icons/react";
import { toast } from "sonner";

const TIMER_S = 5;
const TIMER_DOUBLE_S = 10;

function UpperSilhouette() {
  return (
    <svg viewBox="0 0 100 120" className="absolute inset-0 m-auto h-[88%] pointer-events-none" style={{ filter: "drop-shadow(0 0 2px rgba(0,0,0,0.8))" }} aria-hidden="true" data-testid="avatar-camera-silhouette-upper">
      <g fill="none" stroke="#fff" strokeOpacity="0.95" strokeWidth="1.6">
        <ellipse cx="50" cy="16" rx="11" ry="13" />
        <path d="M38 32 Q50 37 62 32 L82 42 Q86 45 86 52 L90 110 M38 32 L18 42 Q14 45 14 52 L10 110" />
        <path d="M30 44 L30 112 Q50 118 70 112 L70 44" />
      </g>
      <line x1="0" x2="100" y1="96" y2="96" stroke="#D4AF37" strokeWidth="0.8" />
    </svg>
  );
}

function LowerSilhouette() {
  return (
    <svg viewBox="0 0 100 120" className="absolute inset-0 m-auto h-[88%] pointer-events-none" style={{ filter: "drop-shadow(0 0 2px rgba(0,0,0,0.8))" }} aria-hidden="true" data-testid="avatar-camera-silhouette-lower">
      <line x1="0" x2="100" y1="14" y2="14" stroke="#D4AF37" strokeWidth="0.8" />
      <g fill="none" stroke="#fff" strokeOpacity="0.95" strokeWidth="1.6">
        <path d="M28 6 Q50 14 72 6 L66 112 M28 6 L34 112 M50 16 L48 108 M50 16 L52 108" />
      </g>
    </svg>
  );
}

function Silhouette() {
  return (
    <svg viewBox="0 0 100 200" className="absolute inset-0 m-auto h-[80%] pointer-events-none" aria-hidden="true" data-testid="avatar-camera-silhouette">
      <g fill="none" stroke="#fff" strokeOpacity="0.85" strokeWidth="1.2" strokeDasharray="3 2">
        <ellipse cx="50" cy="16" rx="10" ry="12" />
        <path d="M40 30 Q50 34 60 30 L76 38 Q80 40 80 46 L84 92 M40 30 L24 38 Q20 40 20 46 L16 92" />
        <path d="M34 40 L34 98 Q50 104 66 98 L66 40" />
        <path d="M36 98 L38 190 M64 98 L62 190 M50 104 L49 186 M50 104 L51 186" />
      </g>
    </svg>
  );
}

const VIDEO = { width: { ideal: 1080 }, height: { ideal: 1920 } };
const NOT_NORMAL_LENS = /tele|zoom|periscop|macro/i;
const WIDE_LENS = /ultra|0[.,]5|grandangol/i;

// Widest lens available (0.5x ultra-wide when present), never telephoto, no digital zoom.
async function openNormalLens(facing) {
  let st = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, ...VIDEO }, audio: false });
  try {
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
    const side = facing === "user" ? /front|user|anteriore|frontale/i : /back|rear|environment|posteriore/i;
    const current = st.getVideoTracks()[0];
    const curLabel = current?.label || "";
    const onSide = devices.filter((d) => side.test(d.label) && !NOT_NORMAL_LENS.test(d.label));
    const pick = onSide.find((d) => WIDE_LENS.test(d.label)) || onSide[0];
    if (pick && pick.deviceId !== current.getSettings?.().deviceId && (NOT_NORMAL_LENS.test(curLabel) || WIDE_LENS.test(pick.label))) {
      st.getTracks().forEach((t) => t.stop());
      st = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: pick.deviceId }, ...VIDEO }, audio: false });
    }
    const track = st.getVideoTracks()[0];
    const zoom = track?.getCapabilities?.()?.zoom;
    if (zoom) await track.applyConstraints({ advanced: [{ zoom: zoom.min }] });
  } catch (_e) { /* keep the default stream */ }
  return st;
}

const say = (text) => {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "it-IT";
    synth.speak(u);
  } catch (_e) { /* voice not available */ }
};

export default function AvatarCamera({ open, onClose, onCapture, initialMode = "single", retakePart = null, keep = null }) {
  const videoRef = useRef();
  const streamRef = useRef();
  const fileRef = useRef();
  const [shotMode, setShotMode] = useState("single");
  const [facing, setFacing] = useState("environment");
  const [count, setCount] = useState(0);
  const [failed, setFailed] = useState(false);
  const [upper, setUpper] = useState(null);
  const [torch, setTorch] = useState(false);
  const twoStep = shotMode === "double";
  const timerS = twoStep ? TIMER_DOUBLE_S : TIMER_S;
  const part = retakePart || (upper ? "lower" : "upper");
  useEffect(() => { if (open) setShotMode("single"); }, [open]);
  useEffect(() => { setUpper(null); setCount(0); setTorch(false); }, [shotMode, open]);
  useEffect(() => { if (!open) window.speechSynthesis?.cancel(); }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setFailed(false);
    openNormalLens(facing)
      .then((st) => {
        if (cancelled) { st.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = st;
        if (videoRef.current) videoRef.current.srcObject = st;
      })
      .catch(() => setFailed(true));
    if (!navigator.mediaDevices?.getUserMedia) setFailed(true);
    return () => { cancelled = true; streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; };
  }, [open, facing]);

  useEffect(() => {
    if (!count) return undefined;
    const id = setTimeout(() => { if (count === 1) snap(); setCount(count - 1); }, 1000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);

  const startTimer = () => {
    say(!twoStep ? "Foto intera" : part === "upper" ? "Busto" : "Gambe");
    setCount(timerS);
  };

  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks?.()[0];
    if (!track?.getCapabilities?.()?.torch) { toast("Torcia non disponibile su questo dispositivo"); return; }
    try { await track.applyConstraints({ advanced: [{ torch: !torch }] }); setTorch(!torch); }
    catch { toast("Torcia non disponibile su questo dispositivo"); }
  };

  const snap = () => {
    const v = videoRef.current;
    if (!v?.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    const ctx = c.getContext("2d");
    // 2-shot mode is a mirror selfie with the rear camera: flip it back to the true orientation.
    if (twoStep && facing === "environment") { ctx.translate(c.width, 0); ctx.scale(-1, 1); }
    ctx.drawImage(v, 0, 0);
    c.toBlob((b) => {
      if (!b) return;
      const f = new File([b], "avatar.jpg", { type: "image/jpeg" });
      if (!twoStep) { onCapture(f); return; }
      if (retakePart) { onCapture({ ...keep, [retakePart]: f }); return; }
      if (part === "upper") { setUpper(f); say("Ora le gambe"); return; }
      onCapture({ upper, lower: f });
    }, "image/jpeg", 0.92);
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
            <p className="text-sm text-white/70">Non riusciamo ad aprire la fotocamera qui. Consenti l&apos;accesso alla fotocamera o scatta con quella del telefono (1 foto intera). La modalità 2 scatti per poco spazio richiede l&apos;accesso alla fotocamera.</p>
            <button onClick={() => fileRef.current?.click()} className="bg-white text-black px-6 py-3 label-caps" data-testid="avatar-camera-native-btn">Apri fotocamera</button>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onCapture(f); }} data-testid="avatar-camera-native-input" />
          </div>
        ) : (
          <video ref={videoRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-contain bg-black"
            style={{ transform: facing === "user" || twoStep ? "scaleX(-1)" : "none" }} data-testid="avatar-camera-video" />
        )}
        {!failed && (twoStep ? (part === "lower" ? <LowerSilhouette /> : <UpperSilhouette />) : <Silhouette />)}
        {!failed && (
          <p className="absolute top-3 left-1/2 -translate-x-1/2 w-[92%] max-w-md text-center text-xs text-white bg-black/70 backdrop-blur-sm px-4 py-2 rounded-full" data-testid="avatar-camera-hint">
            {twoStep
              ? (part === "lower" ? "2/2 Gambe: dalla vita ai piedi (la vita sulla linea dorata)" : "1/2 Busto: dalla testa a metà coscia (i fianchi sulla linea dorata)")
              : "Corpo intero dentro la sagoma, con spazio sopra la testa e sotto i piedi"}
          </p>
        )}
        {count > 0 && <div className="absolute inset-0 flex items-center justify-center font-serif text-8xl text-white" data-testid="avatar-camera-countdown">{count}</div>}
      </div>
      {!failed && (
        <div className="px-4 py-5 flex flex-col items-center gap-3 text-white">
          <p className="text-[11px] text-white/70 text-center max-w-xs" data-testid="avatar-camera-mode-desc">
            {twoStep ? "Per chi ha poco spazio davanti allo specchio, circa 1 metro: busto e gambe in 2 scatti, li uniamo noi." : "Il corpo intero in un solo scatto: telefono a 1,5-2 metri, grandangolo, lascia spazio sopra la testa e sotto i piedi."}
          </p>
          {twoStep ? (
            <>
              <button onClick={snap} disabled={count > 0}
                className="w-full max-w-xs bg-white text-black py-4 text-base font-semibold tracking-[0.3em] uppercase rounded-full active:scale-95 transition-transform disabled:opacity-50"
                data-testid="avatar-camera-big-snap">Scatta</button>
              <div className="flex items-center gap-5">
                <button onClick={() => setFacing(facing === "user" ? "environment" : "user")} aria-label="Cambia fotocamera" className="text-white/80" data-testid="avatar-camera-flip"><ArrowsClockwise size={24} /></button>
                <button onClick={startTimer} disabled={count > 0} className="flex items-center gap-2 border border-white/60 px-4 py-2 rounded-full text-xs tracking-[0.2em] uppercase" data-testid="avatar-camera-timer-btn">
                  <Timer size={18} /> Timer {TIMER_DOUBLE_S}s
                </button>
                <button onClick={toggleTorch} aria-label="Torcia" className={`flex items-center gap-2 border px-4 py-2 rounded-full text-xs tracking-[0.2em] uppercase ${torch ? "bg-[#D4AF37] border-[#D4AF37] text-black" : "border-white/60"}`} data-testid="avatar-camera-torch-btn">
                  <Flashlight size={18} /> Torcia
                </button>
              </div>
              <span className="text-[11px] text-white/60" data-testid="avatar-camera-step">
                {retakePart ? `Rifai solo ${retakePart === "upper" ? "il busto" : "le gambe"}` : `Scatto ${part === "lower" ? "2" : "1"} di 2`}
              </span>
            </>
          ) : (
            <>
              <div className="flex items-center gap-6">
                <button onClick={() => setFacing(facing === "user" ? "environment" : "user")} aria-label="Cambia fotocamera" className="text-white/80" data-testid="avatar-camera-flip"><ArrowsClockwise size={26} /></button>
                <button onClick={startTimer} disabled={count > 0}
                  className="w-20 h-20 rounded-full border-4 border-white flex items-center justify-center hover:scale-105 transition-transform" data-testid="avatar-camera-timer-btn">
                  <Timer size={30} />
                </button>
                <button onClick={snap} aria-label="Scatta subito" className="text-white/80" data-testid="avatar-camera-snap-btn"><Camera size={26} /></button>
              </div>
              <span className="text-[11px] text-white/60" data-testid="avatar-camera-step">Tocca il cerchio: scatto tra {TIMER_S} secondi</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
