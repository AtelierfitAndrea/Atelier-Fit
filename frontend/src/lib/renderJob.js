import { api } from "@/lib/api";
import { clearPending } from "@/lib/pendingOutfit";

const POLL_MS = 2500;
const MAX_MS = 8 * 60 * 1000;
export const JOB_KEY = "atelier_render_job";
export const JOB_EVENT = "atelier-render-job";
// ANTEPRIMA SUBITO: the first intermediate photo of a running job, shown while the final checks finish.
export const PREVIEW_EVENT = "atelier-render-preview";
const preview = (p) => window.dispatchEvent(new CustomEvent(PREVIEW_EVENT, { detail: p || null }));
// Jobs whose page is still open and polling: the global JobWatcher leaves those alone.
export const liveJobs = new Set();
// Owner-only until approved: other users keep the classic in-page polling.
let resumeEnabled = false;
export const setJobResume = (on) => { resumeEnabled = on; };

export const loadJob = () => {
  try { return JSON.parse(localStorage.getItem(JOB_KEY) || "null"); } catch { return null; }
};
export const clearJob = () => { localStorage.removeItem(JOB_KEY); window.dispatchEvent(new Event(JOB_EVENT)); };

async function pollClassic(id) {
  const start = Date.now();
  while (Date.now() - start < MAX_MS) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    try {
      const res = await api.get(`/render-jobs/${id}`);
      if (res.data.status === "done") { preview(null); return { data: res.data.result }; }
      if (res.data.preview_path) preview(res.data.preview_path);
    } catch (e) {
      if (e?.response) { preview(null); throw e; }
    }
  }
  const err = new Error("timeout");
  err.response = { status: 504, data: { detail: "La generazione sta richiedendo troppo tempo, riprova." } };
  throw err;
}

// Starts a background AI render and polls until it finishes; resolves like api.post ({ data }).
// The job keeps running on the server if the user leaves: its id is kept in localStorage and JobWatcher shows it on return.
export async function postRender(url, body) {
  const { data } = await api.post(url, body);
  if (!data?.job_id) return { data };
  const id = data.job_id;
  if (!resumeEnabled) return pollClassic(id);
  const path = window.location.pathname;
  localStorage.setItem(JOB_KEY, JSON.stringify({ id, kind: /tryon|copylook/.test(url) ? "tryon" : "outfit", t: Date.now() }));
  clearPending(); // a running job is not an "outfit in sospeso"
  window.dispatchEvent(new Event(JOB_EVENT));
  liveJobs.add(id);
  const start = Date.now();
  try {
    while (Date.now() - start < MAX_MS) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      if (window.location.pathname !== path) {
        // User left the page: hand the job over to JobWatcher, this caller never resolves (no surprise navigation).
        liveJobs.delete(id);
        window.dispatchEvent(new Event(JOB_EVENT));
        return new Promise(() => {});
      }
      try {
        const res = await api.get(`/render-jobs/${id}`);
        if (res.data.status === "done") { preview(null); clearJob(); return { data: res.data.result }; }
        if (res.data.preview_path) preview(res.data.preview_path);
      } catch (e) {
        if (e?.response) { preview(null); clearJob(); throw e; }
      }
    }
  } finally {
    liveJobs.delete(id);
    preview(null);
  }
  clearJob();
  const err = new Error("timeout");
  err.response = { status: 504, data: { detail: "La generazione sta richiedendo troppo tempo, riprova." } };
  throw err;
}
