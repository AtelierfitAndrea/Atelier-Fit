import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ArrowRight, TShirt, Ruler, Sparkle, Scales, Warning } from "@phosphor-icons/react";
import AccuracyBadge from "@/components/AccuracyBadge";
import WeightModal from "@/components/WeightModal";

export default function Dashboard() {
  const { user } = useAuth();
  const [tryons, setTryons] = useState([]);
  const [measurements, setMeasurements] = useState(null);
  const [weightStatus, setWeightStatus] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [nonce, setNonce] = useState(0);
  // Demo Fitting Accuracy for FASE 1: 10% (NO) → 85% (SÌ) when weight is fresh
  const [justSaved, setJustSaved] = useState(false);

  const refresh = async () => {
    try {
      const [t, m, w] = await Promise.all([
        api.get("/tryons"),
        api.get("/profile/measurements"),
        api.get("/profile/weight-history"),
      ]);
      setTryons(t.data || []);
      setMeasurements(m.data || {});
      setWeightStatus(w.data?.status || null);
    } catch (_e) { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  const hasFreshWeight = justSaved || (weightStatus?.last_check_at && !weightStatus?.due);
  const demoAccuracy = hasFreshWeight ? 85 : 10;
  const demoReliable = hasFreshWeight;

  const hasMeasurements = measurements && Object.keys(measurements || {}).some((k) => k !== "updated_at" && measurements[k]);
  const stale = weightStatus?.last_check_at && weightStatus?.due;
  const bannerStyle = stale
    ? "bg-[#B91C1C] hover:bg-[#991818] border-[#B91C1C]"
    : "bg-[#0A0A0A] hover:bg-[#8C7355] border-[#0A0A0A]";

  const onWeightSaved = () => {
    // Instant optimistic jump 10% → 85% with CSS animation on the circle
    setJustSaved(true);
    setNonce((n) => n + 1);
    refresh();
  };

  return (
    <div className="space-y-14" data-testid="dashboard-root">
      {weightStatus?.due && (
        <button
          onClick={() => setModalOpen(true)}
          className={`w-full flex items-center justify-between gap-4 border hairline text-white px-5 py-4 transition-colors ${bannerStyle}`}
          data-testid="weight-reminder-banner"
        >
          <div className="flex items-center gap-3">
            <Warning size={18} weight="fill" />
            <div className="text-left" translate="no">
              <div className="label-caps !text-white/80">Controllo peso</div>
              <div className="font-serif text-lg leading-tight">
                {stale
                  ? "Attenzione: Fit non affidabile — Aggiorna peso"
                  : weightStatus.last_check_at
                    ? "Aggiorna il tuo peso per mantenere il fit perfetto"
                    : "Registra il tuo peso per iniziare — lo controlliamo ogni 2 mesi"}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 label-caps !text-white/90">
            <Scales size={16} weight="fill" /> Aggiorna ora →
          </div>
        </button>
      )}

      <div className="flex items-center gap-4 flex-wrap" data-testid="accuracy-row">
        <AccuracyBadge
          nonce={nonce}
          accuracyOverride={demoAccuracy}
          reliableOverride={demoReliable}
        />
        <button
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center justify-center gap-3 bg-[#0A0A0A] text-white px-6 py-3 text-xs font-semibold tracking-[0.2em] uppercase border border-[#0A0A0A] hover:bg-[#8C7355] hover:border-[#8C7355] transition-colors duration-200"
          data-testid="hero-update-weight-btn"
          translate="no"
        >
          Aggiorna ora <ArrowRight size={14} weight="bold" />
        </button>
      </div>

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
        <div className="lg:col-span-8" translate="no">
          <div className="label-caps mb-4">Bentornato</div>
          <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1]">
            Ciao di nuovo,<br />
            <em className="italic text-[#8C7355]">{user?.name?.split(" ")[0] || "amica"}</em>.
          </h1>
          <p className="mt-6 text-neutral-600 max-w-xl leading-relaxed">
            Il tuo camerino è pronto. Avvia una nuova prova o rivedi un look salvato nel tuo atelier.
          </p>
        </div>
        <div className="lg:col-span-4 flex gap-3">
          <Link to="/studio" className="btn-primary flex-1" data-testid="dashboard-start-tryon" translate="no">
            Nuova prova <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4" translate="no">
        <StatCard
          Icon={Ruler}
          label="Misurazioni"
          value="Le tue misure"
          to="/profile"
          cta={hasMeasurements ? "Aggiorna" : "Aggiungi"}
          testid="stat-measurements"
        />
        <StatCard
          Icon={TShirt}
          label="Armadio verificato"
          value={`${tryons.length} capi`}
          to="/wardrobe"
          cta="Apri armadio"
          testid="stat-looks"
        />
        <StatCard
          Icon={Sparkle}
          label="Studio di prova"
          value="Pronto"
          to="/studio"
          cta="Entra nello studio"
          testid="stat-studio"
        />
      </section>

      <section translate="no">
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className="label-caps">Prove recenti</div>
            <h2 className="font-serif text-2xl md:text-3xl tracking-tight">Il tuo atelier</h2>
          </div>
          <Link to="/wardrobe" className="label-caps hover:text-[#8C7355]" data-testid="see-all-wardrobe">
            Vedi tutto →
          </Link>
        </div>
        {tryons.length === 0 ? (
          <div className="border hairline p-10 text-center" data-testid="empty-tryons">
            <div className="label-caps mb-2">Atelier vuoto</div>
            <p className="text-neutral-600 max-w-md mx-auto">Nessuna prova ancora. Vai allo Studio per vedere come ti sta il tuo prossimo capo preferito.</p>
            <Link to="/studio" className="btn-primary mt-6">Apri lo Studio</Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {tryons.slice(0, 8).map((t) => (
              <Link
                key={t.id}
                to={`/tryon/${t.id}`}
                className="group block relative overflow-hidden border hairline fade-up"
                style={{ aspectRatio: "3/4" }}
                data-testid={`tryon-card-${t.id}`}
              >
                <img src={fileUrl(t.result_path)} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute left-3 bottom-3 right-3 bg-white/90 backdrop-blur-sm px-3 py-2 border hairline">
                  <div className="label-caps">{t.garment_category || "capo"}</div>
                  <div className="font-serif text-base truncate">{t.garment_name || "Senza titolo"}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <WeightModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={onWeightSaved}
      />
    </div>
  );
}

function StatCard({ Icon, label, value, to, cta, testid }) {
  return (
    <Link
      to={to}
      className="group border hairline p-6 flex flex-col justify-between hover:border-[#0A0A0A] transition-colors duration-200"
      data-testid={testid}
      translate="no"
    >
      <div className="flex items-center justify-between">
        <span className="label-caps">{label}</span>
        <Icon size={22} weight="duotone" />
      </div>
      <div>
        <div className="font-serif text-3xl mt-6">{value}</div>
        <div className="mt-3 label-caps text-neutral-500 group-hover:text-[#8C7355]">{cta} →</div>
      </div>
    </Link>
  );
}
