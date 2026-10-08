import { useEffect, useState } from "react";
import { toast } from "sonner";
import { LinkSimple, Ruler, Sparkle } from "@phosphor-icons/react";
import { api } from "@/lib/api";

const BRANDS = [
  { re: /zara/i,     name: "Zara",     fit: -1, note: "veste piccolo" },
  { re: /h&?m|hm\./i, name: "H&M",      fit: 0,  note: "veste conforme" },
  { re: /zalando/i,  name: "Zalando",  fit: 0,  note: "veste conforme" },
  { re: /asos/i,     name: "Asos",     fit: 0,  note: "veste conforme" },
  { re: /amazon/i,   name: "Amazon",   fit: 0,  note: "varia per venditore" },
  { re: /mango/i,    name: "Mango",    fit: -1, note: "veste piccolo" },
  { re: /uniqlo/i,   name: "Uniqlo",   fit: 1,  note: "veste largo" },
];

function sizeFromChestEU(chest) {
  // Men suit size ~ chest / 2
  if (!chest) return 50;
  return Math.max(44, Math.min(60, Math.round(chest / 2 / 2) * 2));
}
function letterFromChest(chest) {
  if (!chest) return "M";
  if (chest < 86) return "XS";
  if (chest < 92) return "S";
  if (chest < 98) return "M";
  if (chest < 106) return "L";
  if (chest < 116) return "XL";
  return "XXL";
}

export default function CalcolaTagliaBox() {
  const [url, setUrl] = useState("");
  const [m, setM] = useState({ height_cm: "", chest_cm: "", waist_cm: "", hips_cm: "", shoulder_cm: "" });
  const [result, setResult] = useState(null);
  const [working, setWorking] = useState(false);

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

  const compute = () => {
    if (!url.trim()) { toast.error("Incolla prima il link del prodotto"); return; }
    const chest = Number(m.chest_cm) || 0;
    const waist = Number(m.waist_cm) || 0;
    const hips = Number(m.hips_cm) || 0;
    if (!chest && !waist && !hips) { toast.error("Inserisci almeno una misura"); return; }
    setWorking(true);
    setTimeout(() => {
      const brand = BRANDS.find((b) => b.re.test(url)) || { name: "Negozio", fit: 0, note: "veste conforme" };
      const baseLetter = letterFromChest(chest || 94);
      const baseEU = sizeFromChestEU(chest || 94);
      // Adjust by brand fit (−1 veste piccolo → sali di 1 taglia)
      const letters = ["XS","S","M","L","XL","XXL"];
      const idx = Math.max(0, Math.min(letters.length - 1, letters.indexOf(baseLetter) - brand.fit));
      const letter = letters[idx];
      const eu = Math.max(44, Math.min(60, baseEU - brand.fit * 2));
      // Notes
      const notes = [];
      if (chest) notes.push("Torace ok");
      if (waist) {
        const ideal = chest ? chest - 20 : 72;
        const d = Math.round(waist - ideal);
        if (d >= 2) notes.push(`vita larga ${d}cm`);
        else if (d <= -2) notes.push(`vita stretta ${Math.abs(d)}cm`);
        else notes.push("vita ok");
      }
      if (hips) {
        const ideal = chest ? chest + 4 : 96;
        const d = Math.round(hips - ideal);
        if (d >= 3) notes.push(`fianchi larghi ${d}cm`);
        else if (d <= -3) notes.push(`fianchi stretti ${Math.abs(d)}cm`);
      }
      setResult({ brand: brand.name, note: brand.note, letter, eu, notes });
      setWorking(false);
    }, 650);
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
          placeholder="Incolla qui link prodotto (Zara, Amazon, H&M, Zalando...)"
          className="w-full px-3 py-4 bg-transparent outline-none font-serif text-lg"
          data-testid="calcola-url-input"
        />
      </div>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { k: "height_cm",   l: "Altezza" },
          { k: "chest_cm",    l: "Torace" },
          { k: "waist_cm",    l: "Vita" },
          { k: "hips_cm",     l: "Fianchi" },
          { k: "shoulder_cm", l: "Spalle" },
        ].map((f) => (
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
        <button
          onClick={compute}
          disabled={working}
          className="btn-primary"
          data-testid="calcola-cta"
        >
          {working ? "Calcolo..." : (<><Ruler size={14} weight="bold" /> Calcola la mia taglia</>)}
        </button>
        <span className="text-xs text-neutral-500">Risultato indicativo — presto collegato al vero scraping del brand.</span>
      </div>

      {result && (
        <div className="mt-6 border-t hairline pt-6 fade-up" data-testid="calcola-result">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
            <div className="md:col-span-5 bg-[#0A0A0A] text-white p-6 md:p-8">
              <div className="label-caps !text-white/60">Taglia consigliata · {result.brand}</div>
              <div className="font-serif text-[96px] md:text-[128px] leading-none mt-2">
                {result.eu}
              </div>
              <div className="label-caps !text-white/80">o equivalente {result.letter}</div>
            </div>
            <div className="md:col-span-7">
              <div className="label-caps">Perché questa taglia</div>
              <p className="font-serif text-xl md:text-2xl leading-snug mt-2">
                Per questo prodotto consigliato: <strong>{result.eu}</strong> — {result.notes.join(", ")}.
              </p>
              <div className="mt-4 inline-flex items-center gap-2 label-caps text-[#8C7355]">
                <Sparkle size={14} weight="duotone" /> {result.brand} {result.note}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
