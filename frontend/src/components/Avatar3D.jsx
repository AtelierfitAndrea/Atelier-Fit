// Measurement-driven stylised silhouette.
// Scales body parts based on height, chest, waist, hips, shoulders.
export default function Avatar3D({ measurements = {} }) {
  const h = clamp(measurements.height_cm || 170, 140, 210);
  const chest = clamp(measurements.chest_cm || 90, 70, 130);
  const waist = clamp(measurements.waist_cm || 74, 55, 120);
  const hips = clamp(measurements.hips_cm || 94, 70, 140);
  const shoulder = clamp(measurements.shoulder_cm || 42, 32, 55);

  // Normalise widths to SVG units
  const sw = shoulder * 2.4;        // shoulder width
  const cw = chest * 1.4;           // chest width
  const ww = waist * 1.5;           // waist width
  const hw = hips * 1.45;           // hip width
  const totalH = 420 * (h / 170);
  const scale = 420 / totalH;

  // Center x
  const cx = 180;

  return (
    <div className="relative w-full flex justify-center">
      <svg viewBox="0 0 360 460" className="w-full max-w-[320px]" data-testid="avatar-svg">
        <defs>
          <linearGradient id="sk" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0" stopColor="#1a1a1a" />
            <stop offset="1" stopColor="#3a3a3a" />
          </linearGradient>
        </defs>
        {/* subtle grid */}
        {[80, 160, 240, 320].map((y) => (
          <line key={y} x1="0" y1={y} x2="360" y2={y} stroke="#EEE" />
        ))}
        {/* height marker */}
        <line x1="20" y1="40" x2="20" y2="420" stroke="#CCC" />
        <text x="26" y="46" fontSize="10" fill="#999" fontFamily="Manrope">{Math.round(h)} cm</text>

        <g transform={`translate(0, 20) scale(1, ${scale})`}>
          {/* head */}
          <ellipse cx={cx} cy={55} rx={28} ry={34} fill="url(#sk)" />
          {/* neck */}
          <rect x={cx - 10} y={85} width={20} height={16} fill="url(#sk)" />
          {/* torso */}
          <path
            d={`
              M ${cx - sw/2} 100
              Q ${cx - sw/2 - 6} 130, ${cx - cw/2} 150
              Q ${cx - ww/2 - 4} 200, ${cx - ww/2} 230
              Q ${cx - hw/2 - 2} 250, ${cx - hw/2} 280
              L ${cx + hw/2} 280
              Q ${cx + ww/2 + 2} 250, ${cx + ww/2} 230
              Q ${cx + cw/2 + 4} 200, ${cx + cw/2} 150
              Q ${cx + sw/2 + 6} 130, ${cx + sw/2} 100
              Z
            `}
            fill="url(#sk)"
          />
          {/* arms */}
          <path d={`M ${cx - sw/2} 100 Q ${cx - sw/2 - 20} 180, ${cx - sw/2 - 10} 260 L ${cx - sw/2 + 4} 260 Q ${cx - sw/2 - 6} 180, ${cx - sw/2 + 12} 110 Z`} fill="url(#sk)" />
          <path d={`M ${cx + sw/2} 100 Q ${cx + sw/2 + 20} 180, ${cx + sw/2 + 10} 260 L ${cx + sw/2 - 4} 260 Q ${cx + sw/2 + 6} 180, ${cx + sw/2 - 12} 110 Z`} fill="url(#sk)" />
          {/* legs */}
          <path d={`M ${cx - hw/2 + 4} 280 L ${cx - 6} 280 L ${cx - 10} 420 L ${cx - hw/2} 420 Z`} fill="url(#sk)" />
          <path d={`M ${cx + hw/2 - 4} 280 L ${cx + 6} 280 L ${cx + 10} 420 L ${cx + hw/2} 420 Z`} fill="url(#sk)" />
        </g>

        {/* measurement callouts */}
        <g fontFamily="Manrope" fontSize="9" fill="#8C7355">
          <text x="300" y="170">chest {Math.round(chest)}</text>
          <line x1="260" y1="167" x2="295" y2="167" stroke="#8C7355" />
          <text x="300" y="230">waist {Math.round(waist)}</text>
          <line x1="260" y1="227" x2="295" y2="227" stroke="#8C7355" />
          <text x="300" y="285">hips {Math.round(hips)}</text>
          <line x1="260" y1="282" x2="295" y2="282" stroke="#8C7355" />
        </g>
      </svg>
    </div>
  );
}

function clamp(v, min, max) { return Math.max(min, Math.min(max, Number(v) || min)); }
