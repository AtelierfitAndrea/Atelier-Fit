import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// CAPI TRASPARENTI: checkbox per garment; sheer name / PNG alpha = auto ON; lace/mesh name = ask the user, never guess.
export const TransparentToggle = ({ path, testid = "transparent-toggle" }) => {
  const [on, setOn] = useState(false);
  const save = (v) => { setOn(v); api.post("/garments/transparent", { path, transparent: v }).catch(() => {}); };
  useEffect(() => {
    if (!path) return;
    api.get("/garments/transparent", { params: { path } }).then(({ data }) => {
      if (data.maybe) save(window.confirm("Sembra trasparente, confermi?"));
      else setOn(!!data.transparent);
    }).catch(() => {});
  }, [path]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!path) return null;
  return (
    <label className="flex items-center gap-2 text-xs mt-2 cursor-pointer select-none" data-testid={testid}>
      <input type="checkbox" checked={on} onChange={(e) => save(e.target.checked)} data-testid={`${testid}-checkbox`} />
      Questo capo è trasparente / velato / pizzo / tulle
    </label>
  );
};
