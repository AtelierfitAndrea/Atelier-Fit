import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { ArrowRight, Ruler, CaretDown } from "@phosphor-icons/react";
import WeightModal from "@/components/WeightModal";
import RefreshBanner from "@/components/RefreshBanner";
import TryonCounter from "@/components/TryonCounter";
import CalcolaTagliaBox from "@/components/CalcolaTagliaBox";
import AvatarBox from "@/components/AvatarBox";
import MeasuresForm from "@/components/MeasuresForm";
import { useSubscription } from "@/lib/subscription";
import { useAvatar } from "@/lib/avatar";

export default function Dashboard() {
  const { status: subStatus, openPaywall } = useSubscription();
  const { avatar, loading: avatarLoading, refresh: refreshAvatar } = useAvatar();
  const [tryons, setTryons] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => { api.get("/tryons").then(({ data }) => setTryons(data || [])).catch(() => {}); }, []);

  return (
    <div className="space-y-12" data-testid="dashboard-root">
      <RefreshBanner onWeight={() => setModalOpen(true)} />
      <FreeMonthLine status={subStatus} />
      {!avatarLoading && !avatar?.path && <AvatarBox />}
      <NewTryOnButton blocked={subStatus?.is_blocked} onBlocked={openPaywall} />
      <RecentTryons tryons={tryons} />
      <OptionalSizeSection />
      <WeightModal open={modalOpen} onClose={() => setModalOpen(false)} onSaved={refreshAvatar} />
    </div>
  );
}

function FreeMonthLine({ status }) {
  if (!status) return null;
  const free = status.honeymoon_active && !["SINGLE", "FAMILY"].includes(status.plan);
  if (!free) return <div className="flex justify-center"><TryonCounter /></div>;
  return (
    <p className="text-center text-xs md:text-sm font-semibold uppercase tracking-[0.22em] text-[#8C7355]" translate="no" data-testid="free-month-line">
      Primo mese gratuito · Illimitato
      {status.days_left_honeymoon ? <span className="block mt-1 text-[11px] font-normal normal-case tracking-normal text-neutral-500">{status.days_left_honeymoon} giorni rimasti</span> : null}
    </p>
  );
}

function NewTryOnButton({ blocked, onBlocked }) {
  const cls = "group w-full flex items-center justify-center gap-4 bg-[#0A0A0A] text-white py-8 md:py-10 font-serif text-3xl md:text-5xl tracking-tight hover:bg-[#8C7355] transition-colors duration-300";
  const body = <>NUOVA PROVA <ArrowRight size={36} weight="bold" className="transition-transform duration-300 group-hover:translate-x-2" /></>;
  return blocked
    ? <button onClick={onBlocked} className={cls} data-testid="dashboard-locked-tryon">{body}</button>
    : <Link to="/studio" className={cls} data-testid="dashboard-start-tryon">{body}</Link>;
}

function RecentTryons({ tryons }) {
  const { t } = useI18n();
  return (
    <section data-testid="recent-tryons">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="font-serif text-2xl md:text-3xl tracking-tight">Il tuo atelier</h2>
          <div className="label-caps mt-1">Prove recenti</div>
        </div>
        {tryons.length > 0 && <Link to="/wardrobe" className="label-caps hover:text-[#8C7355]" data-testid="see-all-wardrobe">{t("dashboard.seeAll")} →</Link>}
      </div>
      {tryons.length === 0 ? (
        <div className="border hairline p-10 text-center" data-testid="empty-tryons">
          <p className="text-neutral-600 max-w-md mx-auto">Qui appariranno le tue prove. Tocca NUOVA PROVA e divertiti con i tuoi brand preferiti.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:gap-6">
          {tryons.slice(0, 2).map((it) => (
            <Link key={it.id} to={`/tryon/${it.id}`} className="group block relative overflow-hidden border hairline fade-up" style={{ aspectRatio: "3/4" }} data-testid={`tryon-card-${it.id}`}>
              <img src={fileUrl(it.result_path)} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
              <div className="absolute left-3 bottom-3 right-3 bg-white/90 backdrop-blur-sm px-3 py-2 border hairline">
                <div className="font-serif text-sm md:text-base truncate">{it.garment_name || t("dashboard.untitled")}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function OptionalSizeSection() {
  const [open, setOpen] = useState(false);
  return (
    <section className="border-t hairline pt-12 space-y-6" data-testid="optional-size-section">
      <div>
        <h2 className="font-serif text-2xl md:text-3xl tracking-tight">Vuoi anche la taglia perfetta? <span className="text-neutral-400 text-lg md:text-xl">(Facoltativo)</span></h2>
        <p className="mt-3 text-sm md:text-base text-neutral-600 max-w-2xl leading-relaxed" data-testid="optional-size-text">
          Se gradisci, MyAtelier può consigliarti la taglia perfetta per ogni vestito. Inserisci una sola volta le tue misure, resteranno salvate. Altrimenti puoi continuare a divertirti a provare i brand senza inserirle. Puoi saltare.
        </p>
      </div>
      <div className="border hairline bg-white" data-testid="optional-measures-card">
        <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between gap-4 p-6 text-left" data-testid="optional-measures-toggle">
          <span className="flex items-center gap-3">
            <Ruler size={22} weight="duotone" className="text-[#8C7355]" />
            <span>
              <span className="block font-serif text-xl">Le tue misure</span>
              <span className="block text-xs text-neutral-500">Altezza, peso e misure · facoltativo</span>
            </span>
          </span>
          <CaretDown size={18} className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
        </button>
        {open && <div className="px-6 pb-6"><MeasuresForm onSaved={() => window.dispatchEvent(new Event("atelier-measures-updated"))} /></div>}
      </div>
      <CalcolaTagliaBox />
    </section>
  );
}
