import { useEffect } from "react";
import { Link } from "react-router-dom";
import { LockKey } from "@phosphor-icons/react";

const SECTIONS = [
  ["1. Titolare del servizio", [
    "Il servizio Atelier Fit (di seguito \"Servizio\"), accessibile dal sito atelierfit.com e dalle relative applicazioni, è fornito da My Atelier Fit di Andrea M. (di seguito \"Atelier Fit\" o \"noi\").",
    "Utilizzando il Servizio dichiari di aver letto e accettato i presenti Termini e Condizioni. Se non li accetti, non puoi utilizzare il Servizio.",
  ]],
  ["2. Il Servizio", [
    "Atelier Fit consente di salvare le proprie misure, di ricevere un suggerimento di taglia per capi venduti da negozi online di terzi e di visualizzare un'anteprima virtuale dei capi indossati, generata con sistemi di intelligenza artificiale a partire dalle foto caricate dall'utente.",
    "Atelier Fit non vende capi di abbigliamento. Gli acquisti avvengono esclusivamente sui siti dei rispettivi venditori, alle loro condizioni. Atelier Fit non è parte del contratto di acquisto e non risponde di prezzi, disponibilità, spedizioni, resi o qualità dei prodotti.",
  ]],
  ["3. Registrazione e requisiti", [
    "Per usare il Servizio è necessario accedere con un account Google valido. Devi avere almeno 18 anni oppure usare il Servizio con il consenso e sotto la supervisione di chi esercita la responsabilità genitoriale.",
    "Sei responsabile della correttezza dei dati inseriti (misure, altezza, peso) e della custodia del tuo accesso.",
  ]],
  ["4. Account personale", [
    "L'account Atelier Fit è strettamente personale e non cedibile a terzi.",
    "Per proteggere l'accuratezza dei suggerimenti, l'account può essere attivo su un solo dispositivo alla volta (fino a 4 con il piano Family): un nuovo accesso disconnette il dispositivo precedente. Con il piano Family ogni membro deve usare il proprio profilo.",
  ]],
  ["5. Abbonamenti, prova gratuita e pagamenti", [
    "I primi 30 giorni dalla registrazione sono gratuiti e senza limiti. In seguito il piano FREE include 3 prove virtuali al giorno, che si azzerano ogni giorno a mezzanotte (ora di Roma) e non sono cumulabili; le foto generate con il piano FREE riportano la scritta \"Creato con My Atelier\". I bonus ottenuti invitando amiche non scadono.",
    "Piani attuali: BOOST 0,99 € (3 prove extra valide solo nel giorno di acquisto); PRO 2,99 € per 30 giorni (prove illimitate, firma discreta myatelierapp.it). I piani Family già attivi restano validi fino alla loro scadenza. I prezzi sono comprensivi di IVA, se dovuta, e sono sempre indicati prima del pagamento.",
    "Il PRO è un pagamento unico per 30 giorni, senza rinnovo automatico: alla scadenza torni al piano FREE e puoi riattivarlo quando vuoi. Alla scadenza di un piano Family, i profili aggiuntivi restano salvati ma non sono accessibili.",
  ]],
  ["6. Diritto di recesso", [
    "Se sei un consumatore hai diritto di recedere entro 14 giorni dall'acquisto ai sensi degli artt. 52 e ss. del Codice del Consumo (D.Lgs. 206/2005).",
    "Trattandosi di contenuti e servizi digitali forniti immediatamente, chiedendo l'attivazione del servizio durante il periodo di recesso accetti che l'esecuzione inizi subito: in tal caso il diritto di recesso si perde per le prove già utilizzate (art. 59, lett. o) e, per gli abbonamenti, si applica quanto previsto dall'art. 57 del Codice del Consumo.",
  ]],
  ["7. Foto e contenuti dell'utente", [
    "Le foto che carichi restano tue. Ci concedi soltanto il permesso, limitato e revocabile, di trattarle per fornirti il Servizio (generare le anteprime e i suggerimenti di taglia). Non vendiamo e non cediamo le tue foto a terzi e non le usiamo per pubblicità.",
    "Per generare le anteprime, le immagini vengono elaborate da fornitori tecnologici di intelligenza artificiale e archiviazione che agiscono per nostro conto. Le foto sono visibili solo a te (e ai profili del tuo piano Family). Puoi cancellarle in ogni momento dalle Impostazioni con \"Cancella tutte le mie foto\".",
    "Puoi caricare solo foto di te stesso o di persone che ti hanno dato il consenso (per i minori, chi esercita la responsabilità genitoriale). È vietato caricare contenuti illeciti, offensivi, di nudo o che violino diritti di terzi.",
  ]],
  ["8. Natura dei risultati", [
    "Le anteprime virtuali e i suggerimenti di taglia sono stime indicative generate automaticamente: possono differire dalla vestibilità reale del capo, che dipende anche da modello, materiale e tabelle taglie del venditore. L'affidabilità dipende dalla correttezza e dall'aggiornamento delle misure inserite.",
    "Prima di acquistare verifica sempre le informazioni sul sito del venditore. Atelier Fit non garantisce che il capo suggerito calzi perfettamente.",
  ]],
  ["9. Uso consentito", [
    "È vietato usare il Servizio per scopi illeciti, tentare di accedere ai dati di altri utenti, aggirare i limiti tecnici, estrarre dati in modo automatizzato o rivendere il Servizio. In caso di violazione possiamo sospendere o chiudere l'account.",
  ]],
  ["10. Proprietà intellettuale", [
    "Marchi, nomi, grafica, testi e software di Atelier Fit sono di nostra proprietà o in licenza e sono protetti dalla legge. I marchi dei brand e dei negozi citati appartengono ai rispettivi titolari.",
  ]],
  ["11. Limitazione di responsabilità", [
    "Il Servizio è fornito \"così com'è\". Nei limiti consentiti dalla legge, Atelier Fit non risponde di danni indiretti, di acquisti effettuati presso terzi, né di interruzioni temporanee dovute a manutenzione o a fornitori esterni. Restano salvi i diritti inderogabili del consumatore e la responsabilità per dolo o colpa grave.",
  ]],
  ["12. Privacy", [
    "Il trattamento dei dati personali avviene nel rispetto del Regolamento (UE) 2016/679 (GDPR). Puoi chiedere in qualsiasi momento l'accesso, la rettifica o la cancellazione dei tuoi dati.",
    "La tua email e la tua foto sono usate SOLO per il funzionamento del tuo account e per il calcolo della taglia: l'email identifica il tuo account (anche se cambi telefono) e collega il tuo abbonamento; la foto serve solo per la prova vestiti. È vietato l'invio di newsletter o pubblicità senza il tuo consenso esplicito. Zero spam, zero pubblicità, zero vendita a terzi.",
  ]],
  ["13. Modifiche ai Termini", [
    "Possiamo aggiornare questi Termini. In caso di modifiche ti chiederemo di accettare la nuova versione al successivo accesso. Se non la accetti puoi smettere di usare il Servizio e disdire l'abbonamento.",
  ]],
  ["14. Legge applicabile e foro", [
    "I presenti Termini sono regolati dalla legge italiana. Per le controversie con i consumatori è competente il foro del luogo di residenza o domicilio del consumatore. Puoi ricorrere anche alla piattaforma europea di risoluzione online delle controversie (ODR).",
  ]],
];

export default function Terms() {
  useEffect(() => {
    if (window.location.hash === "#privacy") setTimeout(() => document.getElementById("privacy")?.scrollIntoView(), 50);
  }, []);
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
        <div className="mt-3 label-caps text-neutral-500" data-testid="terms-version">Versione 1.0 — giugno 2026</div>

        {SECTIONS.map(([title, paragraphs], i) => (
          <section key={title} id={title.startsWith("12.") ? "privacy" : undefined} className="mt-10 scroll-mt-6" data-testid={i === 3 ? "terms-personal-account" : `terms-section-${i + 1}`}>
            <h2 className="font-bold text-lg">{title}</h2>
            {paragraphs.map((p) => (
              <p key={p.slice(0, 24)} className="mt-2 text-sm md:text-base leading-relaxed text-neutral-700">{p}</p>
            ))}
          </section>
        ))}

        <section
          className="mt-16 border-2 border-[#0A0A0A] bg-white p-6 md:p-8 flex gap-5"
          data-testid="terms-proprietary-box"
        >
          <LockKey size={36} weight="duotone" className="shrink-0 text-[#8C7355]" aria-hidden="true" />
          <div>
            <h2 className="font-bold text-lg">Tecnologia e Metodo Proprietario My Atelier Fit®</h2>
            <p className="mt-3 text-sm md:text-base leading-relaxed text-neutral-700">
              L&apos;algoritmo di calcolo antropometrico, il sistema di adattamento virtuale, il metodo di calcolo delle taglie dalle misure reali, e l&apos;interfaccia di vestizione virtuale costituiscono metodo proprietario, know-how esclusivo e segreto commerciale di My Atelier Fit di Andrea M., tutelato ai sensi degli artt. 98 e 99 del Codice della Proprietà Industriale. Ogni riproduzione, copia, reverse engineering o utilizzo non autorizzato, anche parziale, è espressamente vietato e sarà perseguito a norma di legge.
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
