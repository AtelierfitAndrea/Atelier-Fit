import { useNavigate } from "react-router-dom";
import { ArrowRight, Ruler, Sparkle, TShirt } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Landing() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const handleLogin = () => {
    if (user) { navigate("/dashboard"); return; }
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="theme-dark min-h-screen font-sans">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 md:px-12 py-6 border-b hairline">
        <img src="/logo-white.png" alt="MY ATELIER" className="h-9 w-auto" data-testid="brand-logo" />
        <nav className="hidden md:flex items-center gap-10 label-caps">
          <a href="#method" className="hover:text-[#8C7355]">Metodo</a>
          <a href="#studio" className="hover:text-[#8C7355]">Il tuo armadio</a>
          <a href="#atelier" className="hover:text-[#8C7355]">Atelier</a>
        </nav>
        <button data-testid="landing-login-btn" onClick={handleLogin} className="btn-ghost">
          {user ? "Entra nell'app" : "Entra"}
        </button>
      </header>

      {/* Hero */}
      <section className="relative px-6 md:px-12 py-16 md:py-24" translate="no">
        <div className="max-w-5xl mx-auto text-center flex flex-col items-center">
          <img src="/logo-white.png" alt="MY ATELIER" className="w-full max-w-xl h-auto mb-14 fade-up" data-testid="hero-logo" />
          <div className="label-caps mb-6" data-testid="hero-eyebrow">N°01 — Il tuo sarto digitale</div>
          <h1 className="font-serif text-4xl sm:text-5xl lg:text-7xl leading-[1] tracking-tighter" data-testid="hero-slogan">
            <em className="italic text-[#8C7355]">&quot;Zero stress, solo puro shopping&quot;</em>
          </h1>
          <div className="mt-4 label-caps text-neutral-500" data-testid="hero-slogan-author">- by Andrea M.</div>
          <p className="mt-10 max-w-4xl font-serif text-2xl md:text-3xl lg:text-4xl leading-snug text-white" data-testid="hero-main-text">
            &quot;Siamo il tuo commesso di fiducia, basta stress da camerino, basta resi da shopping online. Ti basta caricare una foto, darci peso e altezza, noi di Atelier ti indichiamo la taglia perfetta per te!! Scegli i capi che vuoi dai brand che più ami e noi te li mettiamo addosso, nella comodità del tuo divano di casa. La promessa My Atelier.&quot;
          </p>
          <div className="mt-12 flex flex-wrap justify-center gap-4">
            <button data-testid="hero-cta-btn" onClick={handleLogin} className="btn-primary">
              {user ? "Entra nell'app" : "Inizia ora"} <ArrowRight size={16} weight="bold" />
            </button>
            <a href="#method" className="btn-ghost">Come funziona</a>
          </div>
          <div className="mt-12 flex items-center justify-center gap-8 label-caps">
            <span>— Misurato</span>
            <span>— Confrontato</span>
            <span>— Vestito</span>
          </div>

          <div className="mt-16 relative w-full max-w-md">
            <div className="relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img
                src="https://images.unsplash.com/photo-1611042553484-d61f84d22784?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200"
                alt="Fashion editorial"
                className="absolute inset-0 w-full h-full object-cover"
                data-testid="hero-image"
              />
              <div className="absolute left-4 bottom-4 bg-white/85 backdrop-blur-md px-4 py-3 border border-white text-left text-[#0A0A0A]">
                <div className="label-caps">Fit score</div>
                <div className="font-serif text-2xl">M · 98%</div>
              </div>
            </div>
            <div className="hidden lg:block absolute -top-6 -left-10 w-28 h-28 border hairline" />
          </div>
        </div>
      </section>

      {/* Method */}
      <section id="method" className="px-6 md:px-12 py-20 md:py-28 border-t hairline">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-10">
          <div className="md:col-span-4">
            <div className="label-caps mb-4">Il metodo</div>
            <h2 className="font-serif text-3xl md:text-5xl tracking-tight leading-tight">
              Tre passi semplici,<br/>zero resi.
            </h2>
          </div>
          <div className="md:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { n: "01", t: "Misure", d: "Inserisci le tue misure una volta sola. Restano private.", I: Ruler },
              { n: "02", t: "Link", d: "Incolla il link del prodotto da qualsiasi shop online.", I: TShirt },
              { n: "03", t: "Taglia", d: "Confrontiamo con la tabella del brand e ti diamo la taglia giusta.", I: Sparkle },
            ].map(({ n, t, d, I }) => (
              <div key={n} className="border hairline p-6 fade-up" data-testid={`method-${n}`}>
                <div className="flex items-center justify-between">
                  <span className="label-caps">{n}</span>
                  <I size={22} weight="duotone" />
                </div>
                <h3 className="font-serif text-2xl mt-6">{t}</h3>
                <p className="mt-3 text-sm text-neutral-600 leading-relaxed">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Studio preview */}
      <section id="studio" className="px-6 md:px-12 py-20 md:py-28 border-t hairline">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-end">
          <div className="lg:col-span-5">
            <div className="label-caps mb-4">Il tuo armadio</div>
            <h2 className="font-serif text-3xl md:text-5xl tracking-tight leading-tight">
              Un armadio che<br/>
              <em className="italic text-[#8C7355]">ricorda</em> ogni taglia.
            </h2>
            <p className="mt-6 text-base text-neutral-700 leading-relaxed max-w-md">
              Ogni capo analizzato resta salvato: taglia consigliata, misure del brand e, se vuoi,
              anche la foto di te con quel capo addosso.
            </p>
            <button onClick={handleLogin} data-testid="studio-cta-btn" className="mt-8 btn-primary">
              Apri l&apos;armadio <ArrowRight size={16} weight="bold" />
            </button>
          </div>
          <div className="lg:col-span-7 grid grid-cols-3 gap-3">
            <img src="https://images.unsplash.com/photo-1621198059871-0d5f9b449233?crop=entropy&cs=srgb&fm=jpg&q=85&w=600" alt="" className="w-full h-full object-cover" style={{ aspectRatio: "3/4" }} />
            <img src="https://images.unsplash.com/photo-1516257984-b1b4d707412e?crop=entropy&cs=srgb&fm=jpg&q=85&w=600" alt="" className="w-full h-full object-cover translate-y-6" style={{ aspectRatio: "3/4" }} />
            <img src="https://images.unsplash.com/photo-1608379743498-ac08f6d022ba?crop=entropy&cs=srgb&fm=jpg&q=85&w=600" alt="" className="w-full h-full object-cover" style={{ aspectRatio: "3/4" }} />
          </div>
        </div>
      </section>

      <footer id="atelier" className="px-6 md:px-12 py-10 border-t hairline flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="label-caps">© Atelier Fit — Il tuo sarto digitale</div>
        <a href="/termini" className="label-caps hover:underline" data-testid="landing-terms-link">Termini e Condizioni</a>
        <div className="label-caps">atelierfit.com</div>
      </footer>
    </div>
  );
}
