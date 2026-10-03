import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fileUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ArrowRight, TShirt, Ruler, Sparkle } from "@phosphor-icons/react";

export default function Dashboard() {
  const { user } = useAuth();
  const [tryons, setTryons] = useState([]);
  const [measurements, setMeasurements] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [t, m] = await Promise.all([api.get("/tryons"), api.get("/profile/measurements")]);
        setTryons(t.data || []);
        setMeasurements(m.data || {});
      } catch (_e) { /* ignore */ }
    })();
  }, []);

  const hasMeasurements = measurements && Object.keys(measurements || {}).some((k) => k !== "updated_at" && measurements[k]);

  return (
    <div className="space-y-14" data-testid="dashboard-root">
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-end">
        <div className="lg:col-span-8">
          <div className="label-caps mb-4">Welcome back</div>
          <h1 className="font-serif text-4xl md:text-6xl tracking-tighter leading-[1]">
            Good to see you,<br />
            <em className="italic text-[#8C7355]">{user?.name?.split(" ")[0] || "friend"}</em>.
          </h1>
          <p className="mt-6 text-neutral-600 max-w-xl leading-relaxed">
            Your fitting room is ready. Start a new try-on or revisit a saved look from your atelier.
          </p>
        </div>
        <div className="lg:col-span-4 flex gap-3">
          <Link to="/studio" className="btn-primary flex-1" data-testid="dashboard-start-tryon">
            New fitting <ArrowRight size={16} weight="bold" />
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          Icon={Ruler}
          label="Measurements"
          value={hasMeasurements ? "Saved" : "Add yours"}
          to="/profile"
          cta={hasMeasurements ? "Update" : "Add measurements"}
          testid="stat-measurements"
        />
        <StatCard
          Icon={TShirt}
          label="Looks saved"
          value={String(tryons.length)}
          to="/wardrobe"
          cta="Open wardrobe"
          testid="stat-looks"
        />
        <StatCard
          Icon={Sparkle}
          label="Try-on Studio"
          value="Ready"
          to="/studio"
          cta="Enter studio"
          testid="stat-studio"
        />
      </section>

      <section>
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className="label-caps">Recent fittings</div>
            <h2 className="font-serif text-2xl md:text-3xl tracking-tight">Your atelier</h2>
          </div>
          <Link to="/wardrobe" className="label-caps hover:text-[#8C7355]" data-testid="see-all-wardrobe">
            See all →
          </Link>
        </div>
        {tryons.length === 0 ? (
          <div className="border hairline p-10 text-center" data-testid="empty-tryons">
            <div className="label-caps mb-2">Empty atelier</div>
            <p className="text-neutral-600 max-w-md mx-auto">No fittings yet. Head to the Studio to see how your next favourite piece will look on you.</p>
            <Link to="/studio" className="btn-primary mt-6">
              Open the Studio
            </Link>
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
                  <div className="label-caps">{t.garment_category || "piece"}</div>
                  <div className="font-serif text-base truncate">{t.garment_name || "Untitled"}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
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
