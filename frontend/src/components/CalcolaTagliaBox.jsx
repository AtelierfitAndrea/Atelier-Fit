import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { LinkSimple, Ruler, Sparkle, CheckCircle, CloudArrowUp, Warning, ArrowRight } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const FIELDS = [
  { k: "height_cm",   l: "Altezza" },
  { k: "chest_cm",    l: "Torace" },
  { k: "waist_cm",    l: "Vita" },
  { k: "hips_cm",     l: "Fianchi" },
  { k: "shoulder_cm", l: "Spalle" },
];

export default function CalcolaTagliaBox() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [m, setM] = useState({ height_cm: "", chest_cm: "", waist_cm: "", hips_cm: "", shoulder_cm: "" });
  const [result, setResult] = useState(null);
  const [working, setWorking] = useState(false);
  const [needsFallback, setNeedsFallback] = useState(false);
  const [reason, setReason] = useState("");
  const [chartText, setChartText] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/profile/measurements");
        if (data) setM((prev) => ({
          height_cm: data.height_cm ?? prev.height_cm,
          chest_cm: data.chest_cm ?? prev.chest_cm,
          waist_cm: data.waist_cm ?? prev.waist_cm,
          hips_cm: data.hips_cm ?? prev.hips_cm,
          shoulder_cm: data.shoulder_cm ?? prev.shoulder_cm,
        }));
      } catch (_e) { /* ignore */ }
    })();
  }, []);

  // Persist edits so the backend compares with the actually visible numbers.
  const persistMeasurements = async () => {
    const payload = Object.fromEntries(
      Object.entries(m).filter(([_, v]) => v !== "" && v !== null && v !== undefined)
    );
    if (Object.keys(payload).length === 0) return false;
    try { await api.put("/profile/measurements", payload); return true; } catch { return false; }
  };

  const analyze = async () => {
    if (!url.trim()) { toast.error("Incolla prima il link del prodotto"); return; }
    setWorking(true); setResult(null); setNeedsFallback(false); setReason("");
    await persistMeasurements();
    try {
      const { data } = await api.post("/product/analyze", { url });
      handleResult(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setWorking(false); }
  };

  const analyzeText = async () => {
    if (!chartText.trim()) { toast.error("Incolla la tabella taglie"); return; }
    setTextLoading(true); setResult(null);
    await persistMeasurements();
    try {
      const { data } = await api.post("/product/analyze-text", { chart_text: chartText, url });
      handleResult(data, true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setTextLoading(false); }
  };

  const uploadScreenshot = async (file) => {
    if (!file) return;
    setTextLoading(true); setResult(null);
    await persistMeasurements();
    try {
      const fd = new FormData(); fd.append("file", file);
      const q = url ? `?url=${encodeURIComponent(url)}` : "";
      const { data } = await api.post(`/product/analyze-screenshot${q}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      handleResult(data, true);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setTextLoading(false); }
  };

  const handleResult = (data, fromFallback = false) => {
    if (data.ok) {
      setResult(data);
      setNeedsFallback(false);
      return;
    }
    if (data.needs_screenshot) {
      setNeedsFallback(true);
      setReason(data.reason || "Il sito blocca la lettura automatica. Incolla la tabella o carica uno screenshot.");
      if (fromFallback) {
        toast.error("Non siamo riusciti a leggere la tabella. Riprova con dati più nitidi.");
      }
      return;
    }
    toast.error("Nessun risultato valido");
  };

  const provalo = async () => {
    if (!result) return;
    setImporting(true);
    try {
      let garment_path = null;
      if (result.product_image_url) {
        const { data } = await api.post("/product/import-image", {
          image_url: result.product_image_url,
          category: result.category,
          name: result.product_name,
        });
        garment_path = data.path;
      }
      navigate("/studio", {
        state: {
          preset: {
            garment_path,
            name: [result.brand, result.product_name].filter(Boolean).join(" · "),
            category: (result.category || "top").toLowerCase(),
            chosen_size: result.recommended_size,
          },
        },
      });
    } catch (e) {
      toast.error("Non siamo riusciti a importare la foto del prodotto. Caricala manualmente nello Studio.");
      navigate("/studio");
    } finally { setImporting(false); }
  };

  return (
    <section className="border hairline bg-white p-6 md:p-8" data-testid="calcola-taglia-box" translate="no">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <div className="label-caps mb-2 text-[#8C7355]">Beta · Veloce</div>
          <h2 className="font-serif text-3xl md:text-4xl tracking-tighter leading-[1]">Calcola taglia da link</h2>
        </div>
      </div>

      <label className="label-caps block mt-6 mb-2">Link prodotto</label>
      <div className="flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
        <LinkSimple size={16} weight="bold" className="ml-3 text-neutral-500" />
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") analyze(); }}
          placeholder="Incolla qui link prodotto (Zara, Amazon, H&M, Zalando...)"
          className="w-full px-3 py-4 bg-transparent outline-none font-serif text-lg"
          data-testid="calcola-url-input"
        />
      </div>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-3">
        {FIELDS.map((f) => (
          <label key={f.k} className="block">
            <span className="label-caps block mb-2">{f.l}</span>
            <div className="flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
              <input
                type="number"
                step="0.1"
                value={m[f.k] ?? ""}
                onChange={(e) => setM((prev) => ({ ...prev, [f.k]: e.target.value === "" ? "" : Number(e.target.value) }))}
                placeholder="—"
                className="w-full px-3 py-3 bg-transparent outline-none font-serif text-lg"
                data-testid={`calcola-m-${f.k}`}
              />
              <span className="px-3 text-xs text-neutral-500">cm</span>
            </div>
          </label>
        ))}
      </div>

      <div className="mt-6 flex items-center gap-3 flex-wrap">
        <button onClick={analyze} disabled={working} className="btn-primary" data-testid="calcola-cta">
          {working ? "Leggo il sito..." : (<><Ruler size={14} weight="bold" /> Calcola la mia taglia</>)}
        </button>
        <span className="text-xs text-neutral-500">Leggiamo la tabella del brand e confrontiamo con le tue misure.</span>
      </div>

      {needsFallback && (
        <FallbackBlock
          reason={reason}
          chartText={chartText}
          setChartText={setChartText}
          onAnalyzeText={analyzeText}
          onScreenshot={uploadScreenshot}
          loading={textLoading}
        />
      )}

      {result?.ok && (
        <GreenResult result={result} onProvalo={provalo} importing={importing} />
      )}
    </section>
  );
}

function FallbackBlock({ reason, chartText, setChartText, onAnalyzeText, onScreenshot, loading }) {
  return (
    <div className="mt-6 border-t hairline pt-6 fade-up" data-testid="calcola-fallback">
      <div className="label-caps mb-2 text-[#B91C1C] flex items-center gap-2">
        <Warning size={14} weight="fill" /> {reason}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mt-3">
        <div className="md:col-span-8">
          <label className="label-caps block mb-2">Incolla tabella taglie</label>
          <textarea
            value={chartText}
            onChange={(e) => setChartText(e.target.value)}
            placeholder={`es.\nS  Torace 86–90  Vita 70–74\nM  Torace 90–94  Vita 74–78\nL  Torace 94–98  Vita 78–82`}
            rows={6}
            className="w-full px-3 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] transition-colors font-mono text-sm"
            data-testid="calcola-chart-text"
          />
          <button onClick={onAnalyzeText} disabled={loading} className="btn-primary mt-3" data-testid="calcola-text-cta">
            {loading ? "Analizzo..." : "Analizza il testo"}
          </button>
        </div>
        <div className="md:col-span-4">
          <label className="label-caps block mb-2">…o carica screenshot</label>
          <label className="upload-zone p-5 flex items-center gap-3 cursor-pointer min-h-[160px]">
            <CloudArrowUp size={24} weight="duotone" />
            <div>
              <div className="font-serif text-base">Carica immagine</div>
              <div className="text-xs text-neutral-500">JPG / PNG nitida</div>
            </div>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              disabled={loading}
              onChange={(e) => onScreenshot(e.target.files?.[0])}
              data-testid="calcola-screenshot-input"
            />
          </label>
        </div>
      </div>
    </div>
  );
}

function GreenResult({ result, onProvalo, importing }) {
  const { recommended_size, explanation, brand, product_name, fit_notes } = result;
  return (
    <div className="mt-6 fade-up" data-testid="calcola-result">
      <div className="border-2 p-6 md:p-8 flex flex-col md:flex-row items-start md:items-center gap-6" style={{ borderColor: "#059669", background: "#F0FDF4" }}>
        <CheckCircle size={48} weight="fill" className="text-emerald-600 shrink-0" />
        <div className="flex-1">
          <div className="label-caps text-emerald-800">
            {brand ? `${brand}${product_name ? " · " + product_name : ""}` : "Taglia consigliata"}
          </div>
          <div className="font-serif text-4xl md:text-5xl mt-2 text-emerald-900">
            La tua taglia è <span className="text-6xl md:text-7xl font-bold" data-testid="calcola-result-size">{recommended_size}</span>
          </div>
          <p className="mt-3 text-emerald-900 text-lg leading-snug" data-testid="calcola-result-reason">
            Motivo: {explanation}
          </p>
          {fit_notes && (
            <div className="mt-3 inline-block bg-white border border-emerald-200 px-3 py-1 label-caps text-emerald-700">
              {fit_notes}
            </div>
          )}
        </div>
      </div>
      <button
        onClick={onProvalo}
        disabled={importing}
        className="mt-5 inline-flex items-center justify-center gap-3 bg-[#0A0A0A] text-white px-7 py-4 text-sm font-semibold tracking-[0.2em] uppercase border border-[#0A0A0A] hover:bg-[#8C7355] hover:border-[#8C7355] transition-colors duration-200 disabled:opacity-60"
        data-testid="calcola-provalo-cta"
      >
        <Sparkle size={16} weight="bold" />
        {importing ? "Preparo lo Studio..." : "Provalo su di te"}
        <ArrowRight size={16} weight="bold" />
      </button>
    </div>
  );
}
