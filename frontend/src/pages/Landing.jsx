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
    <div className="theme-dark min-h-screen font-sans flex flex-col">
      <header className="flex items-center justify-between px-6 md:px-12 py-6 border-b hairline">
        <img src="/logo-white.png" alt="MY ATELIER" className="h-9 w-auto" data-testid="brand-logo" />
        <button data-testid="landing-login-btn" onClick={handleEnter} className="btn-ghost">Entra</button>
      </header>

      <section className="flex-1 flex items-center px-6 md:px-12 py-16 md:py-24" translate="no">
        <div className="max-w-5xl mx-auto text-center flex flex-col items-center">
          <img src="/logo-white.png" alt="MY ATELIER" className="w-full max-w-xl h-auto mb-14 fade-up" data-testid="hero-logo" />
          <h1 className="font-serif text-4xl sm:text-5xl lg:text-7xl leading-[1] tracking-tighter" data-testid="hero-slogan">
            <em className="italic text-[#8C7355]">&quot;Zero stress, solo puro shopping&quot;</em>
          </h1>
          <div className="mt-4 label-caps text-neutral-500" data-testid="hero-slogan-author">- by Andrea M.</div>
          <p className="mt-10 max-w-4xl font-serif text-2xl md:text-3xl lg:text-4xl leading-snug text-white" data-testid="hero-main-text">
            &quot;Siamo il tuo commesso di fiducia, basta stress da camerino, basta resi da shopping online. Ci bastano misure reali che rimarranno salvate sempre sul tuo account e una tua foto, noi di Atelier ti indichiamo la taglia perfetta per te!! Scegli i capi che vuoi dai brand che più ami e noi te li mettiamo addosso, nella comodità del tuo divano di casa. La promessa My Atelier.&quot;
          </p>
        </div>
      </section>

      <footer className="px-6 md:px-12 py-6 border-t hairline flex justify-center">
        <a href="/termini" className="label-caps text-neutral-500 hover:underline" data-testid="landing-terms-link">Termini e Condizioni</a>
      </footer>
    </div>
  );
}
