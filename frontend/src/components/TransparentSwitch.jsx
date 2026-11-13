import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Owner only: USA_SERVER_ESTERNO_TRASPARENZE (OFF by default, max 2 external generations then OFF by itself).
export const TransparentSwitch = () => {
  const [s, setS] = useState(null);
  const load = () => api.get("/admin/transparent-ext").then((r) => setS(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!s) return null;
  const toggle = () => api.post("/admin/transparent-ext", { on: !s.on }).then((r) => setS(r.data)).catch(() => {});
  return (
    <div className="flex items-center gap-3 text-xs border hairline px-3 py-2 w-fit" data-testid="transparent-ext-switch">
      <span className="label-caps">Server esterno trasparenze</span>
      <button onClick={toggle} data-testid="transparent-ext-toggle"
        className={`px-3 py-1 border transition-colors ${s.on ? "bg-[#0A0A0A] text-white border-[#0A0A0A]" : "hairline"}`}>
        {s.on ? "ON" : "OFF"}
      </button>
      {s.on && <span className="text-neutral-500" data-testid="transparent-ext-left">{s.max - s.used} prove rimaste</span>}
    </div>
  );
};
