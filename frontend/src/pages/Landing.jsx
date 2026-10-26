import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Landing() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleEnter = () => {
    if (user) { navigate("/dashboard"); return; }
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen w-full bg-black text-white flex flex-col" translate="no" data-testid="landing-root">
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <h1 className="fade-up text-center leading-none text-[13vw] sm:text-7xl md:text-8xl tracking-[0.01em]"
          style={{ fontFamily: '"Bodoni Moda", "Playfair Display", Didot, serif', fontWeight: 400 }} data-testid="hero-logo">
          MY ATELIER
        </h1>
        <div className="fade-up mt-4 md:mt-6 text-[7vw] sm:text-4xl md:text-5xl text-white/95"
          style={{ fontFamily: '"Pinyon Script", cursive', animationDelay: "120ms" }} data-testid="hero-slogan-author">
          by Andrea M.
        </div>
        <button onClick={handleEnter} data-testid="landing-login-btn"
          className="fade-up mt-16 md:mt-20 w-[46vw] max-w-[220px] min-w-[180px] h-14 rounded-full border border-white/85 text-white text-base tracking-[0.18em] hover:bg-white hover:text-black transition-colors duration-500"
          style={{ fontFamily: '"Manrope", sans-serif', animationDelay: "240ms" }}>
          ENTRA
        </button>
      </main>
      <footer className="pb-5 text-center" style={{ fontSize: "9px", color: "#555555" }}>
        <a href="/termini" className="hover:underline" data-testid="landing-terms-link">Termini e Condizioni</a>
        <span className="mx-1.5">|</span>
        <a href="/termini#privacy" className="hover:underline" data-testid="landing-privacy-link">Privacy</a>
      </footer>
    </div>
  );
}
