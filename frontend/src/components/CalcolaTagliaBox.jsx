import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { LinkSimple, Camera, Sparkle, CheckCircle, CloudArrowUp, ArrowRight } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useProvalo } from "@/lib/provalo";
import SizeFallbackDualChoice from "@/components/SizeFallbackDualChoice";

export default function CalcolaTagliaBox() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState(null);
  const [needsFallback, setNeedsFallback] = useState(false);
  const [chartText, setChartText] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [dualOpen, setDualOpen] = useState(false);
  const [partial, setPartial] = useState(null);
  const { provalo: goProvalo, importing } = useProvalo();

  const analyze = async () => {
    if (!url.trim()) { toast.error("Incolla prima il link del prodotto"); return; }
    setWorking(true); setResult(null); setNeedsFallback(false); setPartial(null);
    try {
      const { data } = await api.post("/product/analyze", { url });
      handleResult(data);
      if (!data.ok) { setPartial(data); setDualOpen(true); }
    } catch (e) {
      if (e?.response?.data?.detail === "Completa le tue misure") { toast.error("Completa le tue misure"); navigate("/profile"); return; }
      // Site blocked / unreadable: ask the dual choice (international average or screenshot), never block.
      setNeedsFallback(true);
      setDualOpen(true);
    } finally { setWorking(false); }
  };

  const analyzeText = async () => {
    if (!chartText.trim()) { toast.error("Incolla la tabella taglie"); return; }
    setTextLoading(true); setResult(null);
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
    setNeedsFallback(true);
    if (fromFallback) toast.error("Non siamo riusciti a leggere la tabella. Riprova con uno screenshot più nitido.");
  };

  const provalo = () => goProvalo(result);

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

      <p className="mt-5 text-sm text-neutral-700" data-testid="calcola-help">
        Incolla il link del prodotto: usiamo le misure del tuo Avatar e ti diciamo la taglia perfetta. Niente metro, niente misure.
      </p>

      <div className="mt-5">
        <button onClick={analyze} disabled={working} className="btn-primary" data-testid="calcola-cta">
          {working ? "Calcolo in corso..." : (<><Camera size={14} weight="bold" /> CALCOLA CON IL MIO AVATAR</>)}
        </button>
      </div>

      <SizeFallbackDualChoice open={dualOpen} onOpenChange={setDualOpen} url={url} analysis={partial}
        onResult={(d) => { setResult(d); setNeedsFallback(false); }} onScreenshot={uploadScreenshot} screenshotLoading={textLoading} />

      {needsFallback && (
        <FallbackBlock
          onAverage={() => setDualOpen(true)}
          chartText={chartText}
          setChartText={setChartText}
          onAnalyzeText={analyzeText}
          onScreenshot={uploadScreenshot}
          loading={textLoading}
        />
      )}

      {result?.ok && (
        <GreenResult result={result} onProvalo={provalo} importing={importing} onNewScreenshot={() => setNeedsFallback(true)} />
      )}
    </section>
  );
}

function FallbackBlock({ chartText, setChartText, onAnalyzeText, onScreenshot, loading, onAverage }) {
  return (
    <div className="mt-6 border hairline p-5 md:p-6 fade-up" data-testid="calcola-fallback">
      <div className="font-serif text-lg" data-testid="calcola-fallback-title">
        Non riusciamo a leggere la tabella da questo link - Carica screenshot tabella taglie
      </div>
      <button type="button" onClick={onAverage} className="btn-ghost mt-3" data-testid="calcola-fallback-average-btn">
        Usa media internazionale (consigliato)
      </button>
      <label className={`mt-4 upload-zone p-5 flex items-center gap-3 cursor-pointer min-h-[120px] ${loading ? "opacity-60" : ""}`}>
        <CloudArrowUp size={24} weight="duotone" />
        <div>
          <div className="font-serif text-base">{loading ? "Leggo la tabella…" : "Carica screenshot tabella taglie"}</div>
          <div className="text-xs text-neutral-500">JPG / PNG / WEBP nitida</div>
        </div>
        <input
          type="file"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
          className="hidden"
          disabled={loading}
          onChange={(e) => { onScreenshot(e.target.files?.[0]); e.target.value = ""; }}
          data-testid="calcola-screenshot-input"
        />
      </label>
      <details className="mt-4">
        <summary className="label-caps cursor-pointer" data-testid="calcola-chart-text-toggle">Oppure incolla il testo della tabella</summary>
        <textarea
          value={chartText}
          onChange={(e) => setChartText(e.target.value)}
          placeholder={`es.\nS  Torace 86–90  Vita 70–74\nM  Torace 90–94  Vita 74–78`}
          rows={5}
          className="mt-3 w-full px-3 py-3 border hairline bg-transparent outline-none focus:border-[#0A0A0A] font-mono text-sm"
          data-testid="calcola-chart-text"
        />
        <button onClick={onAnalyzeText} disabled={loading} className="btn-primary mt-3" data-testid="calcola-text-cta">
          {loading ? "Analizzo..." : "Analizza il testo"}
        </button>
      </details>
    </div>
  );
}

function GreenResult({ result, onProvalo, importing, onNewScreenshot }) {
  const { recommended_size, explanation, brand, product_name, fit_notes, saved_chart, source, details } = result;
  return (
    <div className="mt-6 fade-up" data-testid="calcola-result">
      {saved_chart && (
        <div className="mb-3 flex flex-wrap items-center gap-3 border hairline px-4 py-3" data-testid="calcola-saved-chart">
          <span className="text-sm" data-testid="calcola-saved-chart-text">Tabella {saved_chart.brand} salvata dal tuo screenshot</span>
          <button type="button" onClick={onNewScreenshot} className="btn-ghost ml-auto" data-testid="calcola-new-screenshot-btn">Usa uno screenshot nuovo</button>
        </div>
      )}
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
            {source === "international_average" ? explanation : <>Motivo: {explanation}</>}
          </p>
          {source === "international_average" && details && (
            <p className="mt-1 text-sm text-emerald-800" data-testid="calcola-result-details">{details}</p>
          )}
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
