import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Owner only: USA_SERVER_ESTERNO_TRASPARENZE (OFF by default, max 2 external generations then OFF by itself).
// One global switch: every copy on the page (single garment + multi-brand) stays in sync.
export const TransparentSwitch = ({ testid = "transparent-ext" }) => {
  const [s, setS] = useState(null);
  const load = () => api.get("/admin/transparent-ext").then((r) => setS(r.data)).catch(() => {});
  useEffect(() => {
    load();
    window.addEventListener("transparent-ext-changed", load);
    return () => window.removeEventListener("transparent-ext-changed", load);
  }, []);
  if (!s) return null;
  const toggle = () => api.post("/admin/transparent-ext", { on: !s.on })
    .then((r) => { setS(r.data); window.dispatchEvent(new Event("transparent-ext-changed")); }).catch(() => {});
  return (
    <div className="flex items-center gap-3 text-xs border hairline px-3 py-2 w-fit" data-testid={`${testid}-switch`}>
      <span className="label-caps">Server esterno trasparenze</span>
      <button onClick={toggle} data-testid={`${testid}-toggle`}
        className={`px-3 py-1 border transition-colors ${s.on ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "hairline"}`}>
        {s.on ? "ON" : "OFF"}
      </button>
      {s.on && <span className="text-neutral-500" data-testid={`${testid}-left`}>{s.max - s.used} prove rimaste</span>}
    </div>
  );
};
