import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { X } from "@phosphor-icons/react";
import { api, fileUrl } from "@/lib/api";
import { JOB_EVENT, clearJob, liveJobs, loadJob } from "@/lib/renderJob";
import { askBook, SaveBookBar } from "@/components/PoseBook";
import ShareLook from "@/components/ShareLook";
import { ResultNote } from "./ResultNote";

const POLL_MS = 3000;
const MAX_AGE_MS = 15 * 60 * 1000;

// Background renders survive leaving the page: shows progress anywhere in the app and the photo when it is ready.
export default function JobWatcher() {
  const navigate = useNavigate();
  const [job, setJob] = useState(() => loadJob());
  const [outfit, setOutfit] = useState(null);

  useEffect(() => {
    const sync = () => setJob(loadJob());
    window.addEventListener(JOB_EVENT, sync);
    return () => window.removeEventListener(JOB_EVENT, sync);
  }, []);

  useEffect(() => {
    if (!job) return undefined;
    if (Date.now() - job.t > MAX_AGE_MS) { clearJob(); return undefined; }
    let alive = true;
    const tick = async () => {
      if (!alive || liveJobs.has(job.id)) return;
      try {
        const { data } = await api.get(`/render-jobs/${job.id}`);
        if (data.status !== "done" || !alive || liveJobs.has(job.id)) return;
        clearJob();
        const r = data.result;
        askBook(job.kind, r.id);
        toast.success("La tua foto è pronta");
        if (job.kind === "tryon") navigate(`/tryon/${r.id}`);
        else setOutfit(r);
      } catch (e) {
        if (!e?.response) return;
        clearJob();
        toast.error(e.response.data?.detail || "Generazione non riuscita, riprova.");
      }
    };
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(t); };
  }, [job, navigate]);

  return (
    <>
      {job && !liveJobs.has(job.id) && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] bg-[#0A0A0A] text-white px-4 py-2.5 flex items-center gap-3 shadow-lg" data-testid="job-watcher-progress">
          <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-[#D4AF37] rounded-full animate-spin" />
          <span className="text-xs tracking-[0.12em]">Sto preparando la tua foto… puoi continuare a navigare</span>
        </div>
      )}
      {outfit && createPortal(
        <div className="fixed inset-0 z-[75] bg-black/70 overflow-y-auto" data-testid="job-watcher-result">
          <div className="max-w-md mx-auto my-6 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="label-caps">Il tuo outfit è pronto</span>
              <button onClick={() => setOutfit(null)} aria-label="Chiudi" data-testid="job-watcher-close"><X size={22} /></button>
            </div>
            <img src={fileUrl(outfit.result_path)} alt="" className="w-full h-auto" data-testid="job-watcher-image" />
            <ResultNote testid="job-watcher-note" />
            <SaveBookBar kind="outfit" refId={outfit.id} />
            <ShareLook path={outfit.result_path} />
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
