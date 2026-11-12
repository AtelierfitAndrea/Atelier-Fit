import { useRef, useState } from "react";
import { toast } from "sonner";
import { CloudArrowUp, Play, ArrowsClockwise, FilePdf } from "@phosphor-icons/react";
import { exportPosePdf } from "@/lib/posePdf";
import { api, fileUrl } from "@/lib/api";
import { postRender } from "@/lib/renderJob";
import { ResultNote } from "../components/ResultNote";

const U = (id) => `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=1400&q=85`;
const POSES = [
  { k: "bed-leg", t: "Seduto sul letto, gamba alzata", src: U("1730990393837-04a157fc9f12") },
  { k: "stool-leg", t: "Seduto su sgabello, gamba alzata", src: U("1600159663244-e36e172bc539") },
  { k: "hip-out", t: "Culo in fuori, petto in avanti", src: U("1784881574333-a334bfa421fe") },
  { k: "jump", t: "Salto in aria", src: U("1593010932917-92bd21088dee") },
  { k: "mirror", t: "Specchio bagno selfie", src: U("1717749874416-ec87aa6964d9") },
  { k: "pocket", t: "Mano in tasca, in piedi street", src: U("1581382575275-97901c2635b7") },
  { k: "low-half", t: "Mezzo busto dal basso", src: U("1772927253232-91fb2e5c30b0") },
  { k: "crossed", t: "Gambe incrociate su sedia", src: "https://images.pexels.com/photos/10423654/pexels-photo-10423654.jpeg?auto=compress&cs=tinysrgb&w=1400" },
];
const SLOTS = [{ k: "top", l: "Top" }, { k: "bottom", l: "Pantaloni" }, { k: "shoes", l: "Scarpe" }];

const upload = async (file, kind) => {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post(`/upload?kind=${kind}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
  return data.path;
};

function FilePick({ onFile, children, testid, className }) {
  const ref = useRef();
  return (
    <button type="button" onClick={() => ref.current?.click()} className={className} data-testid={testid}>
      <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }} />
      {children}
    </button>
  );
}

function OutfitBar({ outfit, setOutfit }) {
  const set = async (k, f) => {
    const preview = URL.createObjectURL(f);
    setOutfit((o) => ({ ...o, [k]: { preview, uploading: true } }));
    try {
      const path = await upload(f, "garment");
      setOutfit((o) => ({ ...o, [k]: { preview, path } }));
    } catch {
      setOutfit((o) => { const n = { ...o }; delete n[k]; return n; });
      toast.error("Caricamento capo non riuscito");
    }
  };
  return (
    <section className="border hairline bg-white p-6" data-testid="test-pose-outfit">
      <div className="label-caps">Outfit unico per tutte le 8 pose</div>
      <div className="mt-4 grid grid-cols-3 gap-4 max-w-lg">
        {SLOTS.map((s) => (
          <FilePick key={s.k} onFile={(f) => set(s.k, f)} testid={`test-pose-slot-${s.k}`}
            className="upload-zone relative aspect-square flex flex-col items-center justify-center text-neutral-500 overflow-hidden">
            {outfit[s.k]?.preview
              ? <img src={outfit[s.k].preview} alt="" className="absolute inset-0 w-full h-full object-contain bg-neutral-50" />
              : <><CloudArrowUp size={26} weight="thin" /><span className="text-xs mt-1">{s.l}</span></>}
            {outfit[s.k]?.uploading && <span className="absolute bottom-1 text-[10px] bg-white px-1">Caricamento…</span>}
          </FilePick>
        ))}
      </div>
    </section>
  );
}

function PoseCard({ pose, items, busy, setBusy, onResult }) {
  const [own, setOwn] = useState(null);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const shown = own?.preview || pose.src;
  const run = async () => {
    if (!items.length) { toast.error("Scegli prima l'outfit in cima"); return; }
    setRunning(true); setBusy(true); setResult(null);
    try {
      const person = own?.path || (await api.post("/test-pose/import", { url: pose.src })).data.path;
      const { data } = await postRender("/outfit/generate-from-uploads", { person_path: person, preserve_pose: true, items });
      setResult(data.result_path);
      onResult(pose.k, { title: pose.t, before: fileUrl(person), after: fileUrl(data.result_path) });
      toast.success(`${pose.t}: pronto`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test non riuscito");
    } finally {
      setRunning(false); setBusy(false);
    }
  };
  const changePhoto = async (f) => {
    const preview = URL.createObjectURL(f);
    try { setOwn({ preview, path: await upload(f, "person") }); setResult(null); }
    catch { toast.error("Caricamento foto non riuscito"); }
  };
  return (
    <article className="border hairline bg-white p-4 flex flex-col" data-testid={`pose-card-${pose.k}`}>
      <div className="label-caps text-xs min-h-[2.5rem]" data-testid={`pose-title-${pose.k}`}>{pose.t}</div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <img src={shown} alt={pose.t} className="w-full aspect-[3/4] object-cover bg-neutral-100" data-testid={`pose-before-${pose.k}`} />
        <div className="w-full aspect-[3/4] bg-neutral-50 flex items-center justify-center text-xs text-neutral-400 text-center px-2">
          {result ? <img src={fileUrl(result)} alt="Dopo" className="w-full h-full object-cover" data-testid={`pose-after-${pose.k}`} />
            : running ? "Ti sto vestendo…" : "Dopo"}
        </div>
      </div>
      <div className="mt-4 flex gap-2">
        <button onClick={run} disabled={busy} className="btn-primary flex-1 justify-center disabled:opacity-40" data-testid={`pose-test-btn-${pose.k}`}>
          <Play size={14} weight="fill" /> {running ? "In corso…" : "TEST"}
        </button>
        <FilePick onFile={changePhoto} testid={`pose-change-photo-${pose.k}`} className="border hairline px-3 label-caps text-xs flex items-center gap-1">
          <ArrowsClockwise size={14} /> Cambia foto
        </FilePick>
      </div>
      {result && <ResultNote testid={`pose-note-${pose.k}`} />}
      {result && <a href={fileUrl(result)} target="_blank" rel="noreferrer" className="mt-2 text-xs underline" data-testid={`pose-open-${pose.k}`}>Apri a tutta pagina</a>}
    </article>
  );
}

export default function TestPose() {
  const [outfit, setOutfit] = useState({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState({});
  const [exporting, setExporting] = useState(false);
  const pages = POSES.filter((p) => done[p.k]).map((p) => done[p.k]);
  const exportPdf = async () => {
    setExporting(true);
    try { await exportPosePdf(pages); toast.success("PDF scaricato"); }
    catch { toast.error("Esportazione PDF non riuscita"); }
    finally { setExporting(false); }
  };
  const items = SLOTS.filter((s) => outfit[s.k]?.path).map((s) => ({ slot: s.k, image_path: outfit[s.k].path }));
  return (
    <div className="max-w-6xl mx-auto px-4 py-10 space-y-8" data-testid="test-pose-page">
      <div>
        <h1 className="font-serif text-4xl">Test 8 pose social</h1>
        <p className="mt-2 text-sm text-neutral-600">Solo proprietario. Ogni TEST fa 1 sola generazione, solo quando lo premi: un test alla volta.</p>
        <button onClick={exportPdf} disabled={!pages.length || exporting} className="mt-5 btn-primary disabled:opacity-40" data-testid="test-pose-export-pdf">
          <FilePdf size={16} /> {exporting ? "Preparo il PDF…" : `ESPORTA PDF PRIMA/DOPO (${pages.length})`}
        </button>
      </div>
      <OutfitBar outfit={outfit} setOutfit={setOutfit} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {POSES.map((p) => <PoseCard key={p.k} pose={p} items={items} busy={busy} setBusy={setBusy} onResult={(k, v) => setDone((d) => ({ ...d, [k]: v }))} />)}
      </div>
    </div>
  );
}
