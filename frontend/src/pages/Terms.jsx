import { Link } from "react-router-dom";
import { LockKey } from "@phosphor-icons/react";

export default function Terms() {
  return (
    <div className="min-h-screen bg-[#FDFDFD] flex flex-col" translate="no" data-testid="terms-page">
      <header className="px-6 md:px-12 py-5 border-b hairline">
        <Link to="/" className="flex items-center gap-2 w-fit" data-testid="terms-home-link">
          <div className="w-5 h-5 bg-[#0A0A0A]" />
          <span className="font-serif text-lg tracking-tight">Atelier Fit</span>
        </Link>
      </header>

      <main className="flex-1 max-w-3xl w-full mx-auto px-6 md:px-10 py-16">
        <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter" data-testid="terms-title">
          Termini e Condizioni
        </h1>

        <section className="mt-12" data-testid="terms-personal-account">
          <h2 className="font-bold text-lg">Account personale</h2>
          <p className="mt-2 text-sm md:text-base leading-relaxed text-neutral-700">
            L&apos;account Atelier Fit è strettamente personale e non cedibile a terzi.
          </p>
        </section>

        <section
          className="mt-16 border-2 border-[#0A0A0A] bg-white p-6 md:p-8 flex gap-5"
          data-testid="terms-proprietary-box"
        >
          <LockKey size={36} weight="duotone" className="shrink-0 text-[#8C7355]" aria-hidden="true" />
          <div>
            <h2 className="font-bold text-lg">Tecnologia e Metodo Proprietario My Atelier Fit®</h2>
            <p className="mt-3 text-sm md:text-base leading-relaxed text-neutral-700">
              L&apos;algoritmo di calcolo antropometrico, il sistema di adattamento virtuale, il metodo di stima delle misure tramite analisi fotografica, altezza e peso, e l&apos;interfaccia di vestizione virtuale costituiscono metodo proprietario, know-how esclusivo e segreto commerciale di My Atelier Fit di Andrea M., tutelato ai sensi degli artt. 98 e 99 del Codice della Proprietà Industriale. Ogni riproduzione, copia, reverse engineering o utilizzo non autorizzato, anche parziale, è espressamente vietato e sarà perseguito a norma di legge.
            </p>
          </div>
        </section>
      </main>

      <footer className="px-6 md:px-12 py-10 border-t hairline flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="label-caps">© Atelier Fit — Il tuo sarto digitale</div>
        <div className="label-caps">atelierfit.com</div>
      </footer>
    </div>
  );
}
