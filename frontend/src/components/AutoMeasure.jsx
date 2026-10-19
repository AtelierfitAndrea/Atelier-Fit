export default function MeasureResult({ data }) {
  return (
    <div className="border hairline bg-white p-6" translate="no" data-testid="brand-sizes-result">
      <div className="label-caps">La tua taglia per brand</div>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {data.brand_sizes.map((b) => (
          <div key={b.brand} className="border hairline p-3" data-testid={`brand-size-${b.brand}`}>
            <div className="label-caps">{b.brand}</div>
            <div className="font-serif text-2xl mt-1">{b.top}</div>
            <div className="text-xs text-neutral-500">Sopra {b.top} · Sotto {b.bottom}</div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-neutral-500">
        Calcolata dalle tue misure reali sulle tabelle taglie standard dei brand. Per un capo preciso usa "Calcola taglia dal link".
      </p>
    </div>
  );
}
