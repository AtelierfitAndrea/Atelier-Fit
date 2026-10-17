import { useEffect, useState } from "react";

const OWNER_KEY = "atelier_owner";
// Sab 24 → Dom 25 ottobre 2026, 00:00 ora italiana (CEST, UTC+2).
const LAUNCH_AT = new Date("2026-10-25T00:00:00+02:00").getTime();

function Countdown() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const left = Math.max(0, LAUNCH_AT - now);
  if (left === 0) {
    return <p style={{ marginTop: "40px", letterSpacing: "10px", fontSize: "28px", fontWeight: 300 }} data-testid="countdown-done">Ci siamo!</p>;
  }
  const s = Math.floor(left / 1000);
  const parts = [["GIORNI", Math.floor(s / 86400)], ["ORE", Math.floor((s % 86400) / 3600)], ["MINUTI", Math.floor((s % 3600) / 60)], ["SECONDI", s % 60]];
  return (
    <div style={{ marginTop: "40px", display: "flex", gap: "28px" }} data-testid="countdown">
      {parts.map(([l, v]) => (
        <div key={l} style={{ textAlign: "center", minWidth: "60px" }}>
          <div style={{ fontSize: "32px", fontWeight: 300, letterSpacing: "2px", fontVariantNumeric: "tabular-nums" }} data-testid={`countdown-${l.toLowerCase()}`}>
            {String(v).padStart(2, "0")}
          </div>
          <div style={{ marginTop: "6px", fontSize: "10px", letterSpacing: "3px", opacity: 0.5 }}>{l}</div>
        </div>
      ))}
    </div>
  );
}

// Soft gate (not security): the secret link only hides the site from casual visitors.
export function useOwnerAccess() {
  const params = new URLSearchParams(window.location.search);
  const viaLink = window.location.pathname.startsWith("/atelier") || params.get("atelier") === "2026";
  try {
    if (params.get("atelier") === "esci") { localStorage.removeItem(OWNER_KEY); return false; }
    if (viaLink) localStorage.setItem(OWNER_KEY, "true");
    return viaLink || ["true", "1"].includes(localStorage.getItem(OWNER_KEY));
  } catch {
    return viaLink;
  }
}

export default function ComingSoon() {
  return (
    <div
      style={{ backgroundColor: "#000", width: "100vw", height: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "#fff" }}
      translate="no"
      data-testid="coming-soon"
    >
      <h1 style={{ letterSpacing: "10px", fontSize: "36px", fontWeight: 300 }} data-testid="coming-soon-title">MY ATELIER</h1>
      <p style={{ marginTop: "20px", letterSpacing: "4px", fontSize: "12px", opacity: 0.6 }} data-testid="coming-soon-text">MY ATELIER .APP - COMING SOON</p>
      <Countdown />
    </div>
  );
}
