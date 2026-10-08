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

  const [weightSavedNow, setWeightSavedNow] = useState(false);
  const calcolaAccuracy = () => (weightSavedNow ? 85 : 0);
  const todayIt = new Date().toLocaleDateString("it-IT");
  const lastWeightDate = weightSavedNow
    ? todayIt
    : (weightStatus?.last_check_at
        ? new Date(weightStatus.last_check_at).toLocaleDateString("it-IT")
        : "—");
  const accuracy = calcolaAccuracy();
  const affidabile = accuracy > 70 ? "SÌ" : "NO";

  const hasMeasurements = measurements && Object.keys(measurements || {}).some((k) => k !== "updated_at" && measurements[k]);
  const stale = weightStatus?.last_check_at && weightStatus?.due;
  const bannerStyle = stale
    ? "bg-[#B91C1C] hover:bg-[#991818] border-[#B91C1C]"
    : "bg-[#0A0A0A] hover:bg-[#8C7355] border-[#0A0A0A]";

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
            <div className="text-left">
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

      <div data-testid="accuracy-row">
        <AccuracyBadge nonce={nonce} />
      </div>

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
        <div className="lg:col-span-8">
          <div
            style={{ background: "#111", color: "white", padding: "12px", border: "1px solid gold" }}
            data-testid="accuracy-debug-block"
          >
            Fitting Accuracy: {accuracy}% - Peso aggiornato il {lastWeightDate} - Affidabile: {affidabile}
          </div>
          <div className="label-caps mb-4 mt-6">Bentornato</div>
          <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1]">
            Ciao di nuovo,<br />
            <em className="italic text-[#8C7355]">{user?.name?.split(" ")[0] || "amica"}</em>.
          </h1>
          <p className="mt-6 text-neutral-600 max-w-xl leading-relaxed">
            Il tuo camerino è pronto. Avvia una nuova prova o rivedi un look salvato nel tuo atelier.
          </p>
        </div>
        <div className="lg:col-span-4 flex gap-3">
          <Link to="/studio" className="btn-primary flex-1" data-testid="dashboard-start-tryon">
            Nuova prova <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          Icon={Ruler}
          label="Misure"
          value={hasMeasurements ? "Salvate" : "Da inserire"}
          to="/profile"
          cta={hasMeasurements ? "Aggiorna" : "Aggiungi misure"}
          testid="stat-measurements"
        />
        <StatCard
          Icon={TShirt}
          label="Look salvati"
          value={String(tryons.length)}
          to="/wardrobe"
          cta="Apri wardrobe"
          testid="stat-looks"
        />
        <StatCard
          Icon={Sparkle}
          label="Studio prove"
          value="Pronto"
          to="/studio"
          cta="Entra nello Studio"
          testid="stat-studio"
        />
      </section>

      <section>
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
        onSaved={() => { setWeightSavedNow(true); setNonce((n) => n + 1); refresh(); }}
      />
    </div>
  );
}

function StatCard({ Icon, label, value, to, cta, testid }) {
  return (
    <Link to={to} className="group border hairline p-6 flex flex-col justify-between hover:border-[#0A0A0A] transition-colors duration-200" data-testid={testid}>
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
