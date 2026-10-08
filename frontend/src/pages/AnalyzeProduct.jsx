import { useState } from "react";
import { toast } from "sonner";
import { Link as LinkIcon, Sparkle, CloudArrowUp, CheckCircle, Warning } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function AnalyzeProduct() {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [needsScreenshot, setNeedsScreenshot] = useState(false);
  const [screenshotLoading, setScreenshotLoading] = useState(false);

  const analyze = async () => {
    if (!/^https?:\/\//.test(url.trim())) { toast.error("Incolla un link valido"); return; }
    setLoading(true); setResult(null); setNeedsScreenshot(false);
    try {
      const { data } = await api.post("/product/analyze", { url });
      if (data.needs_screenshot) {
        setNeedsScreenshot(true);
        toast.message(data.reason || "Serve lo screenshot della tabella taglie");
      } else if (data.ok) {
        setResult(data);
      } else {
        setNeedsScreenshot(true);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setLoading(false); }
  };

  const onScreenshot = async (file) => {
    if (!file) return;
    setScreenshotLoading(true); setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const q = url ? `?url=${encodeURIComponent(url)}` : "";
      const { data } = await api.post(`/product/analyze-screenshot${q}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      if (data.ok) {
        setResult(data);
        setNeedsScreenshot(false);
      } else {
        toast.error("Non siamo riusciti a leggere la tabella — prova con un'immagine più nitida.");
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analisi non riuscita");
    } finally { setScreenshotLoading(false); }
  };

  return (
    <div className="space-y-10" data-testid="analyze-root">
      <header className="max-w-3xl">
        <div className="label-caps mb-3">{t("analyze.kicker")}</div>
        <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1]">
          {t("analyze.title")}
        </h1>
        <p className="mt-5 text-neutral-600 leading-relaxed">
          {t("analyze.subtitle")}
        </p>
      </header>

      <section className="border hairline bg-white p-6 md:p-8">
        <label className="label-caps block mb-3">{t("analyze.urlLabel")}</label>
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1 flex items-center border hairline focus-within:border-[#0A0A0A] transition-colors">
            <LinkIcon size={16} weight="bold" className="ml-3 text-neutral-500" />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") analyze(); }}
              placeholder={t("analyze.placeholder")}
              className="w-full px-3 py-4 bg-transparent outline-none font-serif text-lg"
              data-testid="analyze-url-input"
            />
          </div>
          <button
            onClick={analyze}
            disabled={loading}
            className="btn-primary disabled:opacity-60 md:w-auto"
            data-testid="analyze-cta"
          >
            {loading ? t("analyze.working") : (<><Sparkle size={14} weight="bold" /> {t("analyze.cta")}</>)}
          </button>
        </div>

        {needsScreenshot && (
          <ScreenshotFallback
            onPick={onScreenshot}
            loading={screenshotLoading}
            label={t("analyze.screenshotLabel")}
            hint={t("analyze.screenshotHint")}
          />
        )}
      </section>

      {result?.ok && <Result result={result} />}
    </div>
  );
}

function ScreenshotFallback({ onPick, loading, label, hint }) {
  return (
    <div className="mt-6 border-t hairline pt-6">
      <div className="label-caps mb-3 text-[#B91C1C] flex items-center gap-2">
        <Warning size={14} weight="fill" /> {label}
      </div>
      <p className="text-sm text-neutral-600 mb-4">{hint}</p>
      <label
        className="upload-zone p-6 flex items-center gap-4 cursor-pointer"
        data-testid="analyze-screenshot-dropzone"
      >
        <CloudArrowUp size={28} weight="duotone" />
        <div>
          <div className="font-serif text-lg">{loading ? "…" : "Carica screenshot"}</div>
          <div className="text-xs text-neutral-500">JPG / PNG — tabella taglie leggibile</div>
        </div>
        <input
          type="file"
          accept="image/*"
          className="hidden"
          disabled={loading}
          onChange={(e) => onPick(e.target.files?.[0])}
          data-testid="analyze-screenshot-input"
        />
      </label>
    </div>
  );
}

function Result({ result }) {
  const { recommended_size, explanation, brand, product_name, category, confidence, size_chart, fit_notes } = result;
  const conf = typeof confidence === "number" ? Math.round(confidence * 100) : null;
  return (
    <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up" data-testid="analyze-result">
      <div className="lg:col-span-5 bg-[#0A0A0A] text-white p-8 md:p-10 flex flex-col justify-between">
        <div>
          <div className="label-caps !text-white/60">La tua taglia</div>
          {brand && <div className="label-caps !text-[#8C7355] mt-2" translate="no">{brand} {product_name ? `· ${product_name}` : ""}</div>}
        </div>
        <div className="my-10 flex items-baseline gap-5">
          <CheckCircle size={28} weight="fill" className="text-emerald-500" />
          <div className="font-serif text-[128px] md:text-[180px] leading-none" data-testid="analyze-result-size">
            {recommended_size}
          </div>
        </div>
        <div className="flex items-center justify-between text-sm text-white/70">
          {category && <span translate="no">{category}</span>}
          {conf !== null && <span translate="no">Affidabilità {conf}%</span>}
        </div>
      </div>

      <div className="lg:col-span-7 border hairline bg-white p-8 md:p-10">
        <div className="label-caps">Perché questa taglia</div>
        <p className="font-serif text-2xl md:text-3xl leading-snug mt-3" data-testid="analyze-result-explanation">
          {explanation}
        </p>
        {fit_notes && (
          <div className="mt-5 inline-block border hairline px-3 py-1 label-caps text-[#8C7355]" translate="no">
            {fit_notes}
          </div>
        )}
        {size_chart && typeof size_chart === "object" && (
          <div className="mt-8">
            <div className="label-caps mb-3">Tabella taglie del brand</div>
            <SizeChartTable chart={size_chart} highlight={recommended_size} />
          </div>
        )}
      </div>
    </section>
  );
}

function SizeChartTable({ chart, highlight }) {
  const sizes = Object.keys(chart);
  const allKeys = Array.from(new Set(sizes.flatMap((s) => Object.keys(chart[s] || {}))));
  return (
    <div className="overflow-auto border hairline">
      <table className="w-full text-sm" translate="no">
        <thead className="bg-neutral-50">
          <tr>
            <th className="text-left px-3 py-2 label-caps">Taglia</th>
            {allKeys.map((k) => <th key={k} className="text-left px-3 py-2 label-caps">{k.replace("_cm","")}</th>)}
          </tr>
        </thead>
        <tbody>
          {sizes.map((s) => (
            <tr key={s} className={s === highlight ? "bg-[#0A0A0A] text-white" : "border-t hairline"}>
              <td className="px-3 py-2 font-serif text-lg">{s}</td>
              {allKeys.map((k) => <td key={k} className="px-3 py-2">{chart[s]?.[k] ?? "—"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
