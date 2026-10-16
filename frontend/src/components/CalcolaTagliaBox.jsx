import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { LinkSimple, Camera, Sparkle, CheckCircle, CloudArrowUp, ArrowRight, X } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { extractBodyRatios } from "@/lib/pose";

export default function CalcolaTagliaBox() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [photo, setPhoto] = useState(null);
  const [savedHeight, setSavedHeight] = useState(null);
  const [askHeight, setAskHeight] = useState(false);
  const [lastPhotoAt, setLastPhotoAt] = useState(null);
  const [height, setHeight] = useState("");
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState(null);
  const [needsFallback, setNeedsFallback] = useState(false);
  const [chartText, setChartText] = useState("");
  const [textLoading, setTextLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const photoRef = useRef();

  useEffect(() => {
    api.get("/profile/measurements").then(({ data }) => {
      setSavedHeight(data?.height_cm || null);
      setLastPhotoAt(data?.photo_measured_at || (data?.method === "auto_photo" ? data?.updated_at : null));
    }).catch(() => {});
  }, []);

  const pickPhoto = (f) => {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) { toast.error("Usa una foto jpg, png o webp"); return; }
    setPhoto({ file: f, preview: URL.createObjectURL(f) });
  };

  // Body measured from the photo (in the browser); height from the profile is the only scale.
  const measureFromPhoto = async () => {
    let ratios;
    try { ratios = await extractBodyRatios(photo.file); }
    catch (e) {
      toast.error(e.message === "not_full_body" ? "Serve la foto intera: dalla testa ai piedi, ben visibili." : "Non vediamo bene la tua figura. Riprova con una foto più luminosa, frontale e intera.");
      return false;
    }
    const params = new URLSearchParams({ features: JSON.stringify(ratios) });
    if (askHeight) params.set("height_cm", String(Number(height)));
    const fd = new FormData();
    fd.append("photo", photo.file);
    try {
      const { data } = await api.post(`/profile/auto-measure?${params}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setSavedHeight(data.measurements.height_cm);
      setLastPhotoAt(data.measurements.photo_measured_at || new Date().toISOString());
      setAskHeight(false);
      return true;
    } catch (e) {
      if (e?.response?.data?.detail === "need_height") { setAskHeight(true); return false; }
      toast.error(e?.response?.data?.detail || "Calcolo non riuscito");
      return false;
    }
  };

  const analyze = async () => {
    if (!url.trim()) { toast.error("Incolla prima il link del prodotto"); return; }
    if (!photo && !lastPhotoAt) { toast.error("Carica una tua foto intera"); return; }
    if (photo && !savedHeight && !askHeight) { setAskHeight(true); return; }
    if (askHeight && !(Number(height) >= 120 && Number(height) <= 230)) { toast.error("Inserisci la tua altezza in cm (120-230)"); return; }
    setWorking(true); setResult(null); setNeedsFallback(false);
    // A new photo is measured; otherwise the last photo's (encrypted) measurements are reused.
    if (photo && !(await measureFromPhoto())) { setWorking(false); return; }
    try {
      const { data } = await api.post("/product/analyze", { url });
      handleResult(data);
    } catch (_e) {
      // Site blocked / unreadable: go straight to the screenshot box, no error for the user.
      setNeedsFallback(true);
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

      <div className="mt-6">
        <span className="label-caps block mb-2">La tua foto intera</span>
        <input ref={photoRef} type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" className="hidden"
          onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} data-testid="calcola-photo-input" />
        {photo ? (
          <div className="flex items-center gap-4" data-testid="calcola-photo-selected">
            <img src={photo.preview} alt="" className="w-16 h-20 object-cover border hairline" />
            <button type="button" onClick={() => photoRef.current?.click()} className="btn-ghost" data-testid="calcola-photo-change">Cambia foto</button>
            <button type="button" onClick={() => setPhoto(null)} className="text-neutral-500 hover:text-[#0A0A0A]" aria-label="Rimuovi" data-testid="calcola-photo-remove"><X size={16} /></button>
          </div>
        ) : lastPhotoAt ? (
          <div className="flex flex-wrap items-center gap-4 border hairline px-4 py-3" data-testid="calcola-last-photo">
            <CheckCircle size={18} weight="fill" className="text-emerald-600" />
            <span className="text-sm" data-testid="calcola-last-photo-text">
              Usiamo la tua ultima foto intera (del {new Date(lastPhotoAt).toLocaleDateString("it-IT", { day: "2-digit", month: "2-digit" })})
            </span>
            <button type="button" onClick={() => photoRef.current?.click()} className="btn-ghost ml-auto" data-testid="calcola-last-photo-change">Cambia foto</button>
          </div>
        ) : (
          <button type="button" onClick={() => photoRef.current?.click()}
            onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); pickPhoto(e.dataTransfer.files?.[0]); }}
            className="w-full upload-zone py-6 flex items-center justify-center gap-3 label-caps !text-[#0A0A0A]" data-testid="calcola-photo-btn">
            <CloudArrowUp size={20} /> Carica una foto intera
          </button>
        )}
      </div>

      {askHeight && (
        <div className="mt-5 flex flex-wrap items-center gap-3 fade-up" data-testid="calcola-ask-height">
          <span className="text-sm">Quanto sei alto?</span>
          <div className="flex items-center border hairline focus-within:border-[#0A0A0A] w-36">
            <input type="number" inputMode="numeric" value={height} onChange={(e) => setHeight(e.target.value)} placeholder="es. 182"
              className="w-full px-3 py-2 bg-transparent outline-none font-serif text-lg" data-testid="calcola-height-input" />
            <span className="px-3 text-xs text-neutral-500">cm</span>
          </div>
          <span className="text-xs text-neutral-500">Te lo chiediamo solo questa volta.</span>
        </div>
      )}

      <p className="mt-5 text-sm text-neutral-700" data-testid="calcola-help">
        Carica una tua foto intera e incolla il link del prodotto, noi ti diciamo la taglia perfetta. Niente metro, niente misure.
      </p>

      <div className="mt-5">
        <button onClick={analyze} disabled={working} className="btn-primary" data-testid="calcola-cta">
          {working ? "Calcolo in corso..." : (<><Camera size={14} weight="bold" /> CALCOLA CON LA MIA FOTO</>)}
        </button>
      </div>

      {needsFallback && (
        <FallbackBlock
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

function FallbackBlock({ chartText, setChartText, onAnalyzeText, onScreenshot, loading }) {
  return (
    <div className="mt-6 border hairline p-5 md:p-6 fade-up" data-testid="calcola-fallback">
      <div className="font-serif text-lg" data-testid="calcola-fallback-title">
        Non riusciamo a leggere la tabella da questo link - Carica screenshot tabella taglie
      </div>
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
  const { recommended_size, explanation, brand, product_name, fit_notes, saved_chart } = result;
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
