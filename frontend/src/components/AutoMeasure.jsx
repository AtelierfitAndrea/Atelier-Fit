export default function MeasureResult({ data }) {
  const m = data.measurements;
  const rows = [["Torace", m.chest_cm], ["Vita", m.waist_cm], ["Fianchi", m.hips_cm], ["Spalle", m.shoulder_cm], ["Lunghezza gamba", m.inseam_cm]];
  return (
    <div className="mt-10 border hairline bg-white p-6" translate="no" data-testid="auto-measure-result">
      <div className="flex items-baseline justify-between flex-wrap gap-2">
        <div className="label-caps">La tua taglia per brand</div>
        <div className="text-xs text-neutral-500" data-testid="auto-measure-precision">
          Precisione stimata fino al {data.precision}% · stima AI
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {data.brand_sizes.map((b) => (
          <div key={b.brand} className="border hairline p-3" data-testid={`brand-size-${b.brand}`}>
            <div className="label-caps">{b.brand}</div>
            <div className="font-serif text-2xl mt-1">{b.top}</div>
            <div className="text-xs text-neutral-500">Sopra {b.top} · Sotto {b.bottom}</div>
          </div>
        ))}
      </div>
      <div className="mt-6 label-caps">Misure stimate</div>
      <ul className="mt-2 divide-y hairline">
        {rows.map(([l, v]) => (
          <li key={l} className="flex justify-between py-2 text-sm">
            <span>{l}</span>
            <span><span className="font-serif text-lg">{v} cm</span> {m.tape_calibrated_at && ((l === "Torace" && v === Math.round(m.tape_chest)) || (l === "Vita" && v === Math.round(m.tape_waist)))
              ? <span className="text-xs text-emerald-700" data-testid={`measure-tape-badge-${l.toLowerCase()}`}>tarata col metro</span>
              : <span className="text-xs text-neutral-500">{m.tape_calibrated_at ? "allineata al metro" : "±2cm stima AI"}</span>}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-neutral-500">
        Tabelle taglie standard indicative dei brand. Per un capo preciso usa "Calcola taglia dal link".
      </p>
    </div>
  );
}

