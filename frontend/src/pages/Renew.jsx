import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

export default function Renew() {
  const [error, setError] = useState(null);
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api.post("/subscription/checkout", { option: "single", origin_url: window.location.origin })
      .then(({ data }) => { window.location.href = data.checkout_url; })
      .catch((e) => setError(e?.response?.data?.detail || "Pagamento non disponibile, riprova."));
  }, []);
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-6" data-testid="renew-page">
      {error ? (
        <>
          <p className="font-serif text-2xl" data-testid="renew-error">{error}</p>
          <Link to="/dashboard" className="btn-primary mt-8" data-testid="renew-back-btn">Torna all&apos;app</Link>
        </>
      ) : (
        <p className="label-caps" data-testid="renew-loading">Ti porto al pagamento PRO…</p>
      )}
    </div>
  );
}
