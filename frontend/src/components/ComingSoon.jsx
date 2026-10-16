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
    <div className="theme-dark min-h-screen flex flex-col items-center justify-center px-6" translate="no" data-testid="coming-soon">
      <img src="/logo-white.png" alt="MY ATELIER" className="w-full max-w-2xl h-auto fade-up" data-testid="coming-soon-logo" />
      <p className="mt-12 label-caps tracking-[0.4em] !text-white/80 fade-up" data-testid="coming-soon-text">Stiamo arrivando</p>
    </div>
  );
}
