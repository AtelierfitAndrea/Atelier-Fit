import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Ruler, Sparkle, TShirt } from "@phosphor-icons/react";
import { useAuth } from "@/lib/auth";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Landing() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && user) navigate("/dashboard", { replace: true });
  }, [user, loading, navigate]);

  const handleLogin = () => {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#FDFDFD] text-[#0A0A0A] font-sans">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 md:px-12 py-6 border-b hairline">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-[#0A0A0A]" />
          <span className="font-serif text-xl tracking-tight" data-testid="brand-logo">Atelier Fit</span>
        </div>
        <nav className="hidden md:flex items-center gap-10 label-caps">
          <a href="#method" className="hover:text-[#8C7355]">Method</a>
          <a href="#studio" className="hover:text-[#8C7355]">Studio</a>
          <a href="#atelier" className="hover:text-[#8C7355]">Atelier</a>
        </nav>
        <button data-testid="landing-login-btn" onClick={handleLogin} className="btn-ghost">
          Enter
        </button>
      </header>

      {/* Hero */}
      <section className="relative px-6 md:px-12 py-16 md:py-24">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-start">
          <div className="lg:col-span-7 relative">
            <div className="label-caps mb-6" data-testid="hero-eyebrow">N°01 — Virtual Fitting</div>
            <h1 className="font-serif text-5xl md:text-7xl lg:text-8xl leading-[0.95] tracking-tighter">
              See it on you<br/>
              <em className="italic text-[#8C7355]">before</em> you buy it.
            </h1>
            <p className="mt-8 max-w-xl text-base md:text-lg leading-relaxed text-neutral-700">
              An editorial fitting room, powered by your real measurements. Upload a photo,
              drop any garment, and watch an AI atelier dress a precise avatar of you — with
              size guidance you can actually trust.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <button data-testid="hero-cta-btn" onClick={handleLogin} className="btn-primary">
                Begin the fitting <ArrowRight size={16} weight="bold" />
              </button>
              <a href="#method" className="btn-ghost">How it works</a>
            </div>
            <div className="mt-16 flex items-center gap-8 label-caps">
              <span>— Measured</span>
              <span>— Generated</span>
              <span>— Styled</span>
            </div>
          </div>

          <div className="lg:col-span-5 relative">
            <div className="relative overflow-hidden" style={{ aspectRatio: "4/5" }}>
              <img
                src="https://images.unsplash.com/photo-1611042553484-d61f84d22784?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200"
                alt="Fashion editorial"
                className="absolute inset-0 w-full h-full object-cover"
                data-testid="hero-image"
              />
              <div className="absolute left-4 bottom-4 bg-white/85 backdrop-blur-md px-4 py-3 border hairline">
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
            <div className="label-caps mb-4">The Method</div>
            <h2 className="font-serif text-3xl md:text-5xl tracking-tight leading-tight">
              Three deliberate steps,<br/>no guesswork.
            </h2>
          </div>
          <div className="md:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { n: "01", t: "Measure", d: "Enter your body measurements once. We keep them private.", I: Ruler },
              { n: "02", t: "Upload", d: "Add your photo and any garment image you fancy from any shop.", I: TShirt },
              { n: "03", t: "Preview", d: "An AI atelier dresses you in seconds, with size recommendation.", I: Sparkle },
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
            <div className="label-caps mb-4">The Studio</div>
            <h2 className="font-serif text-3xl md:text-5xl tracking-tight leading-tight">
              A fitting room that<br/>
              <em className="italic text-[#8C7355]">remembers</em> you.
            </h2>
            <p className="mt-6 text-base text-neutral-700 leading-relaxed max-w-md">
              Every item you try is saved to your atelier — a private wardrobe of
              generated looks, with size notes and the exact outfits that made the cut.
            </p>
            <button onClick={handleLogin} data-testid="studio-cta-btn" className="mt-8 btn-primary">
              Open my atelier <ArrowRight size={16} weight="bold" />
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
        <div className="label-caps">© Atelier Fit — Milan / Paris</div>
        <div className="label-caps">Powered by Gemini · Nano Banana</div>
      </footer>
    </div>
  );
}
