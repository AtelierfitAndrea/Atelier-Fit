const OWNER_KEY = "atelier_owner";

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
    </div>
  );
}
