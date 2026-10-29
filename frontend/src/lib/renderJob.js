import { api } from "@/lib/api";
import { clearPending } from "@/lib/pendingOutfit";

const POLL_MS = 2500;
const MAX_MS = 8 * 60 * 1000;
export const JOB_KEY = "atelier_render_job";
export const JOB_EVENT = "atelier-render-job";
// Jobs whose page is still open and polling: the global JobWatcher leaves those alone.
export const liveJobs = new Set();

export const loadJob = () => {
  try { return JSON.parse(localStorage.getItem(JOB_KEY) || "null"); } catch { return null; }
};
export const clearJob = () => { localStorage.removeItem(JOB_KEY); window.dispatchEvent(new Event(JOB_EVENT)); };

// Starts a background AI render and polls until it finishes; resolves like api.post ({ data }).
// The job keeps running on the server if the user leaves: its id is kept in localStorage and JobWatcher shows it on return.
export async function postRender(url, body) {
  const { data } = await api.post(url, body);
  if (!data?.job_id) return { data };
  const id = data.job_id;
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
        if (res.data.status === "done") { clearJob(); return { data: res.data.result }; }
      } catch (e) {
        if (e?.response) { clearJob(); throw e; }
      }
    }
  } finally {
    liveJobs.delete(id);
  }
  clearJob();
  const err = new Error("timeout");
  err.response = { status: 504, data: { detail: "La generazione sta richiedendo troppo tempo, riprova." } };
  throw err;
}
