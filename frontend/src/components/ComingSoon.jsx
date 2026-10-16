const OWNER_KEY = "atelier_owner";

// Soft gate (not security): the secret link only hides the site from casual visitors.
export function useOwnerAccess() {
  const params = new URLSearchParams(window.location.search);
  const viaLink = window.location.pathname.startsWith("/atelier") || params.get("atelier") === "2026";
  try {
    if (viaLink) localStorage.setItem(OWNER_KEY, "1");
    return viaLink || localStorage.getItem(OWNER_KEY) === "1";
  } catch {
    return viaLink;
  }
}

export default function ComingSoon() {
  return (
    <div
      style={{ background: "#000", height: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "white" }}
      translate="no"
      data-testid="coming-soon"
    >
      <h1 style={{ letterSpacing: "8px", fontSize: "32px", fontWeight: 300 }} data-testid="coming-soon-title">MY ATELIER</h1>
      <p style={{ marginTop: "20px", letterSpacing: "3px", opacity: 0.8 }} data-testid="coming-soon-text">MY ATELIER .APP - COMING SOON</p>
    </div>
  );
}
