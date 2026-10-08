import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { ArrowRight, TShirt, Ruler, Sparkle, Scales, Warning } from "@phosphor-icons/react";
import AccuracyBadge from "@/components/AccuracyBadge";
import WeightModal from "@/components/WeightModal";
import HoneymoonBanner from "@/components/HoneymoonBanner";
import TryonCounter from "@/components/TryonCounter";
import PricingCards from "@/components/PricingCards";
import CalcolaTagliaBox from "@/components/CalcolaTagliaBox";
import { useSubscription } from "@/lib/subscription";

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { status: subStatus, openPaywall } = useSubscription();
  const [tryons, setTryons] = useState([]);
  const [measurements, setMeasurements] = useState(null);
  const [weightStatus, setWeightStatus] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [nonce, setNonce] = useState(0);

  const refresh = async () => {
    try {
      const [t2, m, w] = await Promise.all([
        api.get("/tryons"),
        api.get("/profile/measurements"),
        api.get("/profile/weight-history"),
      ]);
      setTryons(t2.data || []);
      setMeasurements(m.data || {});
      setWeightStatus(w.data?.status || null);
    } catch (_e) { /* ignore */ }
  };

  useEffect(() => { refresh(); }, []);

  const hasMeasurements = measurements && Object.keys(measurements || {}).some((k) => k !== "updated_at" && measurements[k]);
  const stale = weightStatus?.last_check_at && weightStatus?.due;
  const bannerStyle = stale
    ? "bg-[#B91C1C] hover:bg-[#991818] border-[#B91C1C]"
    : "bg-[#0A0A0A] hover:bg-[#8C7355] border-[#0A0A0A]";

  const onWeightSaved = () => {
    // Server has recomputed the score — just ask the badge to re-fetch.
    setNonce((n) => n + 1);
    refresh();
  };

  return (
    <div className="space-y-14" data-testid="dashboard-root">
      <HoneymoonBanner />
      {weightStatus?.due && (
        <button
          onClick={() => setModalOpen(true)}
          className={`w-full flex items-center justify-between gap-4 border hairline text-white px-5 py-4 transition-colors ${bannerStyle}`}
          data-testid="weight-reminder-banner"
        >
          <div className="flex items-center gap-3">
            <Warning size={18} weight="fill" />
            <div className="text-left">
              <div className="label-caps !text-white/80">{t("weight.banner")}</div>
              <div className="font-serif text-lg leading-tight">
                {stale ? t("weight.stale") : (weightStatus.last_check_at ? t("weight.due") : t("weight.start"))}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 label-caps !text-white/90">
            <Scales size={16} weight="fill" /> {t("accuracy.updateNow")} →
          </div>
        </button>
      )}

      <div className="flex items-center gap-4 flex-wrap" data-testid="accuracy-row">
        <AccuracyBadge nonce={nonce} />
        <TryonCounter />
        <button
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center justify-center gap-3 bg-[#0A0A0A] text-white px-6 py-3 text-xs font-semibold tracking-[0.2em] uppercase border border-[#0A0A0A] hover:bg-[#8C7355] hover:border-[#8C7355] transition-colors duration-200"
          data-testid="hero-update-weight-btn"
        >
          {t("accuracy.updateNow")} <ArrowRight size={14} weight="bold" />
        </button>
      </div>

      <PricingCards />

      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
        <div className="lg:col-span-8">
          <div className="label-caps mb-4">{t("dashboard.welcome")}</div>
          <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1]">
            {t("dashboard.hiAgain")}<br />
            <em className="italic text-[#8C7355]">{user?.name?.split(" ")[0] || t("dashboard.fallbackName")}</em>.
          </h1>
          <p className="mt-6 text-neutral-600 max-w-xl leading-relaxed">{t("dashboard.heroCopy")}</p>
        </div>
        <div className="lg:col-span-4 flex gap-3">
          {subStatus?.is_blocked ? (
            <button onClick={openPaywall} className="btn-primary flex-1" data-testid="dashboard-locked-tryon">
              {t("dashboard.newTryOn")} <ArrowRight size={16} weight="bold" />
            </button>
          ) : (
            <Link to="/studio" className="btn-primary flex-1" data-testid="dashboard-start-tryon">
              {t("dashboard.newTryOn")} <ArrowRight size={16} weight="bold" />
            </Link>
          )}
        </div>
      </section>

      <CalcolaTagliaBox />

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          Icon={Ruler}
          label={t("dashboard.cards.measurementsLabel")}
          value={t("dashboard.cards.measurementsValue")}
          to="/profile"
          cta={hasMeasurements ? t("dashboard.cards.measurementsCtaUpdate") : t("dashboard.cards.measurementsCtaAdd")}
          testid="stat-measurements"
        />
        <StatCard
          Icon={TShirt}
          label={t("dashboard.cards.wardrobeLabel")}
          value={`${tryons.length} ${t("dashboard.cards.wardrobeUnit")}`}
          to="/wardrobe"
          cta={t("dashboard.cards.wardrobeCta")}
          testid="stat-looks"
        />
        <StatCard
          Icon={Sparkle}
          label={t("dashboard.cards.studioLabel")}
          value={t("dashboard.cards.studioValue")}
          to="/studio"
          cta={t("dashboard.cards.studioCta")}
          testid="stat-studio"
        />
      </section>

      <section>
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className="label-caps">{t("dashboard.recent")}</div>
            <h2 className="font-serif text-2xl md:text-3xl tracking-tight">{t("dashboard.atelier")}</h2>
          </div>
          <Link to="/wardrobe" className="label-caps hover:text-[#8C7355]" data-testid="see-all-wardrobe">
            {t("dashboard.seeAll")} →
          </Link>
        </div>
        {tryons.length === 0 ? (
          <div className="border hairline p-10 text-center" data-testid="empty-tryons">
            <div className="label-caps mb-2">{t("dashboard.emptyTitle")}</div>
            <p className="text-neutral-600 max-w-md mx-auto">{t("dashboard.emptyBody")}</p>
            <Link to="/studio" className="btn-primary mt-6">{t("dashboard.openStudio")}</Link>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {tryons.slice(0, 8).map((it) => (
              <Link
                key={it.id}
                to={`/tryon/${it.id}`}
                className="group block relative overflow-hidden border hairline fade-up"
                style={{ aspectRatio: "3/4" }}
                data-testid={`tryon-card-${it.id}`}
              >
                <img src={fileUrl(it.result_path)} alt="" className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                <div className="absolute left-3 bottom-3 right-3 bg-white/90 backdrop-blur-sm px-3 py-2 border hairline">
                  <div className="label-caps">{it.garment_category || t("dashboard.piece")}</div>
                  <div className="font-serif text-base truncate">{it.garment_name || t("dashboard.untitled")}</div>
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
