import { api } from "@/lib/api";

const POLL_MS = 2500;
const MAX_MS = 8 * 60 * 1000;

// Starts a background AI render and polls until it finishes; resolves like api.post ({ data }).
export async function postRender(url, body) {
  const { data } = await api.post(url, body);
  if (!data?.job_id) return { data };
  const start = Date.now();
  while (Date.now() - start < MAX_MS) {
    await new Promise((r) => setTimeout(r, POLL_MS));
    try {
      const res = await api.get(`/render-jobs/${data.job_id}`);
      if (res.data.status === "done") return { data: res.data.result };
    } catch (e) {
      if (e?.response) throw e;
    }
  }
  const err = new Error("timeout");
  err.response = { status: 504, data: { detail: "La generazione sta richiedendo troppo tempo, riprova." } };
  throw err;
}
