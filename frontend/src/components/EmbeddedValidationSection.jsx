import { useState } from "react";

// Ground truth 12-configuration calibration matrix with exact benchmark provenance
const CALIBRATION_DATASET = [
  { 
    id: "VAL-01", 
    hardware: "i5-12400F + RTX 4060", 
    game: "Cyberpunk 2077", 
    res: "1080p", 
    actual: 72, 
    pred: 71, 
    err: -1, 
    ape: 1.39, 
    source: "Hardware Unboxed", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "GeForce 551.86",
    test_method: "60-second repeatable manual run through Kabuki district",
    metric_type: "Mean Average FPS across 3 runs"
  },
  { 
    id: "VAL-02", 
    hardware: "i5-12400F + RTX 4060", 
    game: "Cyberpunk 2077", 
    res: "1440p", 
    actual: 48, 
    pred: 49, 
    err: 1, 
    ape: 2.08, 
    source: "Hardware Unboxed", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "GeForce 551.86",
    test_method: "60-second repeatable manual run through Kabuki district",
    metric_type: "Mean Average FPS across 3 runs"
  },
  { 
    id: "VAL-03", 
    hardware: "Ryzen 5 5600 + RX 6600", 
    game: "Cyberpunk 2077", 
    res: "1080p", 
    actual: 54, 
    pred: 57, 
    err: 3, 
    ape: 5.56, 
    source: "TechPowerUp", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "Adrenalin 24.3.1",
    test_method: "Integrated benchmark pass (v2.12)",
    metric_type: "Mean Average FPS"
  },
  { 
    id: "VAL-04", 
    hardware: "i3-12100F + RTX 3060 12G", 
    game: "Cyberpunk 2077", 
    res: "1080p", 
    actual: 58, 
    pred: 60, 
    err: 2, 
    ape: 3.45, 
    source: "TechPowerUp", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "GeForce 551.86",
    test_method: "Integrated benchmark pass (v2.12)",
    metric_type: "Mean Average FPS"
  },
  { 
    id: "VAL-08", 
    hardware: "i7-13700KF + RTX 4080S", 
    game: "Cyberpunk 2077", 
    res: "1440p", 
    actual: 132, 
    pred: 117, 
    err: -15, 
    ape: 11.36, 
    source: "Gamers Nexus", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "GeForce 552.12",
    test_method: "Repeatable scripted outdoor driving loop",
    metric_type: "Mean Average FPS across 4 runs"
  },
  { 
    id: "VAL-09", 
    hardware: "i7-13700KF + RTX 4080S", 
    game: "Cyberpunk 2077", 
    res: "4K", 
    actual: 68, 
    pred: 76, 
    err: 8, 
    ape: 11.76, 
    source: "Gamers Nexus", 
    preset: "Ultra Preset / RT Off / DX12", 
    driver: "GeForce 552.12",
    test_method: "Repeatable scripted outdoor driving loop",
    metric_type: "Mean Average FPS across 4 runs"
  },
  { 
    id: "VAL-10", 
    hardware: "i5-12400F + RTX 4060", 
    game: "Valorant", 
    res: "1080p", 
    actual: 380, 
    pred: 275, 
    err: -105, 
    ape: 27.63, 
    source: "Hardware Unboxed", 
    preset: "High Preset / Native / DX11", 
    driver: "GeForce 551.86",
    test_method: "Standardized deathmatch replay benchmark segment",
    metric_type: "Reported Average FPS"
  },
  { 
    id: "VAL-11", 
    hardware: "i3-12100F + RTX 4060", 
    game: "Valorant", 
    res: "1080p", 
    actual: 290, 
    pred: 221, 
    err: -69, 
    ape: 23.79, 
    source: "Hardware Unboxed", 
    preset: "High Preset / Native / DX11", 
    driver: "GeForce 551.86",
    test_method: "Standardized deathmatch replay benchmark segment",
    metric_type: "Reported Average FPS"
  },
  { 
    id: "VAL-12", 
    hardware: "Ryzen 5 5600 + RX 6600", 
    game: "Valorant", 
    res: "1080p", 
    actual: 340, 
    pred: 294, 
    err: -46, 
    ape: 13.53, 
    source: "TechPowerUp", 
    preset: "High Preset / Native / DX11", 
    driver: "Adrenalin 24.3.1",
    test_method: "Standardized deathmatch replay benchmark segment",
    metric_type: "Reported Average FPS"
  },
  { 
    id: "VAL-15", 
    hardware: "i5-12400F + RTX 4060", 
    game: "CS2", 
    res: "1080p", 
    actual: 240, 
    pred: 171, 
    err: -69, 
    ape: 28.75, 
    source: "Gamers Nexus", 
    preset: "Very High / CMAA2 / DX11", 
    driver: "GeForce 551.86",
    test_method: "Dust II competitive match demo replay",
    metric_type: "Mean Average FPS"
  },
  { 
    id: "VAL-17", 
    hardware: "i5-12400F + RTX 4060", 
    game: "Elden Ring", 
    res: "1080p", 
    actual: 95, 
    pred: 84, 
    err: -11, 
    ape: 11.58, 
    source: "Hardware Unboxed", 
    preset: "Maximum Preset / Uncapped / DX12", 
    driver: "GeForce 551.86",
    test_method: "Standardized outdoor riding run (Limgrave)",
    metric_type: "Reported Average FPS"
  },
  { 
    id: "VAL-18", 
    hardware: "i5-12400F + RTX 4060", 
    game: "Elden Ring", 
    res: "1440p", 
    actual: 68, 
    pred: 67, 
    err: -1, 
    ape: 1.47, 
    source: "Hardware Unboxed", 
    preset: "Maximum Preset / Uncapped / DX12", 
    driver: "GeForce 551.86",
    test_method: "Standardized outdoor riding run (Limgrave)",
    metric_type: "Reported Average FPS"
  }
];

export default function EmbeddedValidationSection() {
  const [selectedGame, setSelectedGame] = useState("ALL");
  const [selectedRow, setSelectedRow] = useState(null);

  const filtered = selectedGame === "ALL" 
    ? CALIBRATION_DATASET 
    : CALIBRATION_DATASET.filter((c) => c.game === selectedGame);

  // Parity Plot Coordinate Space (0 to 400 FPS)
  const maxPlotFps = 400;
  const plotWidth = 360;
  const plotHeight = 360;
  const padding = { top: 15, right: 15, bottom: 45, left: 50 };
  const innerWidth = plotWidth - padding.left - padding.right;
  const innerHeight = plotHeight - padding.top - padding.bottom;

  const scaleX = (val) => padding.left + (val / maxPlotFps) * innerWidth;
  const scaleY = (val) => padding.top + innerHeight - (val / maxPlotFps) * innerHeight;

  return (
    <div className="w-full bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6 mt-8">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-3 border-b border-slate-100 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
              CHAPTER 4 EVIDENCE
            </span>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded bg-slate-100 text-slate-700 border border-slate-200">
              IN-SAMPLE CALIBRATION (N = 12)
            </span>
          </div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight">
            Empirical Model Verification & Residual Analysis
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Predictive evaluation of EcoBuild&apos;s decoupled dual-pipeline frame-time engine against condition-matched reviewer hardware benchmarks.
          </p>
        </div>

        <div className="text-left md:text-right text-[11px] text-slate-400">
          <div>Engine Version: <strong className="text-slate-700 font-mono">v2.1-decoupled</strong></div>
          <div>Evaluation State: <strong className="text-slate-700">In-Sample Calibration</strong></div>
        </div>
      </div>

      {/* 4 Primary Statistical Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Mean Absolute Pct Error</div>
          <div className="text-2xl font-black text-emerald-600 mt-1">11.86%</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Baseline: <span className="line-through">28.79%</span> <span className="text-emerald-700 font-bold">(-58.8% rel.)</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Coefficient of Det. (R²)</div>
          <div className="text-2xl font-black text-emerald-600 mt-1">0.8622</div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Baseline: <span className="line-through">0.7635</span> <span className="text-emerald-700 font-bold">(+0.0987)</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Mean Absolute Error (MAE)</div>
          <div className="text-2xl font-black text-emerald-600 mt-1">
            27.58 <span className="text-xs font-bold text-slate-400">FPS</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            Baseline: <span className="line-through">41.92 FPS</span> <span className="text-emerald-700 font-bold">(-14.34 FPS)</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
          <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Residual Direction (Bias)</div>
          <div className="text-base font-black text-slate-800 mt-2">8 Under / 4 Over</div>
          <div className="text-[11px] text-slate-400 mt-0.5">Baseline was 100% negative (12/12)</div>
        </div>
      </div>

      {/* Parity Plot and Disaggregated Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Parity Plot (Square Aspect Ratio with Explicit Axes) */}
        <div className="lg:col-span-5 p-4 rounded-xl bg-slate-50 border border-slate-100 flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider">Parity Plot (y = x)</span>
              <span className="text-[10px] text-slate-400 font-mono">0 to 400 FPS</span>
            </div>
            <p className="text-[11px] text-slate-500 leading-tight mb-2">
              Points on the diagonal indicate perfect agreement. Points below the line indicate model underprediction.
            </p>
          </div>

          <div className="w-full flex justify-center py-1">
            <svg width={plotWidth} height={plotHeight} viewBox={`0 0 ${plotWidth} ${plotHeight}`} className="overflow-visible select-none">
              {/* Inner Plot Area */}
              <rect 
                x={padding.left} 
                y={padding.top} 
                width={innerWidth} 
                height={innerHeight} 
                fill="#ffffff" 
                rx="6" 
                stroke="#cbd5e1" 
              />

              {/* Grid Lines & Ticks */}
              {[100, 200, 300, 400].map((tick) => {
                const xPos = scaleX(tick);
                const yPos = scaleY(tick);
                return (
                  <g key={tick} className="text-[9px] font-mono">
                    <line x1={xPos} y1={padding.top} x2={xPos} y2={padding.top + innerHeight} stroke="#f1f5f9" strokeWidth="1" />
                    <line x1={padding.left} y1={yPos} x2={padding.left + innerWidth} y2={yPos} stroke="#f1f5f9" strokeWidth="1" />
                    <text x={xPos} y={padding.top + innerHeight + 14} textAnchor="middle" fill="#64748b">{tick}</text>
                    <text x={padding.left - 6} y={yPos + 3} textAnchor="end" fill="#64748b">{tick}</text>
                  </g>
                );
              })}

              {/* 0 Origin Label */}
              <text x={padding.left - 6} y={padding.top + innerHeight + 3} textAnchor="end" fill="#64748b" className="text-[9px] font-mono">0</text>
              <text x={padding.left} y={padding.top + innerHeight + 14} textAnchor="middle" fill="#64748b" className="text-[9px] font-mono">0</text>

              {/* Parity Diagonal Line (y = x) */}
              <line 
                x1={scaleX(0)} 
                y1={scaleY(0)} 
                x2={scaleX(maxPlotFps)} 
                y2={scaleY(maxPlotFps)} 
                stroke="#10b981" 
                strokeWidth="2" 
                strokeDasharray="4 4" 
              />

              {/* Plotted Benchmark Observations */}
              {CALIBRATION_DATASET.map((pt) => {
                const cx = scaleX(pt.actual);
                const cy = scaleY(pt.pred);
                const isEsports = pt.game === "Valorant" || pt.game === "CS2";
                const isSelected = selectedRow?.id === pt.id;

                return (
                  <g key={pt.id} className="cursor-pointer" onClick={() => setSelectedRow(pt)}>
                    {isSelected && (
                      <circle cx={cx} cy={cy} r={9} fill="none" stroke="#10b981" strokeWidth={2} className="animate-ping" />
                    )}
                    <circle
                      cx={cx}
                      cy={cy}
                      r={isSelected ? 6.5 : 4.5}
                      fill={isEsports ? "#f59e0b" : "#0284c7"}
                      stroke="#ffffff"
                      strokeWidth={1.5}
                      className="transition-all hover:scale-125"
                    >
                      <title>{`${pt.id}: ${pt.game} (${pt.res})\nRef: ${pt.actual} FPS | Pred: ${pt.pred} FPS\nError: ${pt.err > 0 ? "+" + pt.err : pt.err} FPS`}</title>
                    </circle>
                  </g>
                );
              })}

              {/* Explicit Axis Labels */}
              <text 
                x={padding.left + innerWidth / 2} 
                y={plotHeight - 6} 
                textAnchor="middle" 
                fill="#334155" 
                className="text-[10px] font-bold uppercase tracking-wider"
              >
                Reference FPS (Benchmark Ground Truth) →
              </text>
              <text 
                x={-(padding.top + innerHeight / 2)} 
                y={14} 
                transform="rotate(-90)" 
                textAnchor="middle" 
                fill="#334155" 
                className="text-[10px] font-bold uppercase tracking-wider"
              >
                Predicted FPS (EcoBuild Model) →
              </text>
            </svg>
          </div>

          <div className="flex justify-between items-center text-[10px] text-slate-500 pt-2 border-t border-slate-200">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-600 inline-block"></span> AAA Titles (Cyberpunk / Elden Ring)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span> Esports (Valorant / CS2)
            </span>
          </div>
        </div>

        {/* Right: Disaggregated Engine Breakdown Cards */}
        <div className="lg:col-span-7 flex flex-col justify-between space-y-3">
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
            <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block mb-1">
              Disaggregated Engine Accuracy
            </span>
            <p className="text-[11px] text-slate-500 mb-3 leading-relaxed">
              Predictive accuracy reflects distinct computational bounds between GPU compute-heavy and draw-call-heavy workloads:
            </p>

            <div className="grid grid-cols-2 gap-2.5">
              <div className="p-3 bg-white rounded-lg border border-slate-200">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">Cyberpunk 2077</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700">N=6</span>
                </div>
                <div className="mt-1.5 flex justify-between text-xs">
                  <span className="text-slate-400">MAE:</span>
                  <span className="text-emerald-600 font-bold">5.00 FPS</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAPE:</span>
                  <span className="text-emerald-600 font-bold">5.93%</span>
                </div>
              </div>

              <div className="p-3 bg-white rounded-lg border border-slate-200">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">Elden Ring</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700">N=2</span>
                </div>
                <div className="mt-1.5 flex justify-between text-xs">
                  <span className="text-slate-400">MAE:</span>
                  <span className="text-emerald-600 font-bold">6.00 FPS</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAPE:</span>
                  <span className="text-emerald-600 font-bold">6.53%</span>
                </div>
              </div>

              <div className="p-3 bg-white rounded-lg border border-slate-200">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">Valorant</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-50 text-amber-700">N=3</span>
                </div>
                <div className="mt-1.5 flex justify-between text-xs">
                  <span className="text-slate-400">MAE:</span>
                  <span className="text-amber-600 font-bold">73.33 FPS</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAPE:</span>
                  <span className="text-amber-600 font-bold">21.65%</span>
                </div>
              </div>

              <div className="p-3 bg-white rounded-lg border border-slate-200">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-slate-800">CS2 (Source 2)</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-50 text-amber-700">N=1</span>
                </div>
                <div className="mt-1.5 flex justify-between text-xs">
                  <span className="text-slate-400">MAE:</span>
                  <span className="text-amber-600 font-bold">69.00 FPS</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAPE:</span>
                  <span className="text-amber-600 font-bold">28.75%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Academically Defensible Narrative Callout */}
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100 text-[11px] text-slate-600 leading-relaxed">
            <strong className="text-slate-800 block mb-0.5">Empirical Discussion & Limitations (Chapter 4):</strong>
            The sampled AAA workloads demonstrate relatively low average percentage errors (approximately 5.9% to 6.5%). 
            In high-framerate esports workloads, hypothesized factors—such as single-thread draw-call dispatch and L3 cache sensitivity at 250+ FPS—are noted as plausible contributors requiring further investigation rather than established causes within this 12-configuration calibration set.
          </div>
        </div>
      </div>

      {/* Dataset Matrix Table with Bi-directional Selection */}
      <div className="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-3">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">Calibration Benchmark Matrix</h3>
            <p className="text-[11px] text-slate-400">Click any row or parity point to inspect reviewer source, test methodology, and driver version.</p>
          </div>

          <div className="flex gap-1">
            {["ALL", "Cyberpunk 2077", "Valorant", "Elden Ring", "CS2"].map((g) => (
              <button
                key={g}
                onClick={() => setSelectedGame(g)}
                className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition ${
                  selectedGame === g
                    ? "bg-slate-900 text-white shadow-sm"
                    : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto bg-white rounded-lg border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/70 text-slate-500 border-b border-slate-200">
              <tr>
                <th className="py-2.5 px-3 font-bold">ID</th>
                <th className="py-2.5 px-3 font-bold">Hardware Setup</th>
                <th className="py-2.5 px-3 font-bold">Workload Target</th>
                <th className="py-2.5 px-3 text-right font-bold">Ref FPS</th>
                <th className="py-2.5 px-3 text-right font-bold">Pred FPS</th>
                <th className="py-2.5 px-3 text-right font-bold">Error (Δ)</th>
                <th className="py-2.5 px-3 text-right font-bold">APE (%)</th>
                <th className="py-2.5 px-3 text-center font-bold">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filtered.map((row) => {
                const isSelected = selectedRow?.id === row.id;
                return (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedRow(isSelected ? null : row)}
                    className={`cursor-pointer transition ${
                      isSelected ? "bg-emerald-50 font-semibold" : "hover:bg-slate-50"
                    }`}
                  >
                    <td className="py-2 px-3 font-mono text-slate-400">{row.id}</td>
                    <td className="py-2 px-3">{row.hardware}</td>
                    <td className="py-2 px-3 font-medium">{row.game} ({row.res})</td>
                    <td className="py-2 px-3 text-right font-bold text-slate-900">{row.actual}</td>
                    <td className="py-2 px-3 text-right font-bold text-emerald-600">{row.pred}</td>
                    <td className={`py-2 px-3 text-right font-bold ${row.err < 0 ? "text-amber-600" : "text-sky-600"}`}>
                      {row.err > 0 ? `+${row.err}` : row.err}
                    </td>
                    <td className="py-2 px-3 text-right font-mono">{row.ape.toFixed(2)}%</td>
                    <td className="py-2 px-3 text-center text-[10px] text-slate-400 font-semibold">{row.source}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Selected Row Provenance & Audit Drawer */}
        {selectedRow && (
          <div className="p-3.5 rounded-lg bg-emerald-50/80 border border-emerald-200 text-xs space-y-2">
            <div className="flex justify-between items-center border-b border-emerald-200/60 pb-1.5">
              <div className="flex items-center gap-2">
                <span className="font-mono text-emerald-800 font-bold">[{selectedRow.id}]</span>
                <span className="font-bold text-slate-900">{selectedRow.game} ({selectedRow.res})</span>
                <span className="text-slate-500">— {selectedRow.hardware}</span>
              </div>
              <button onClick={() => setSelectedRow(null)} className="text-slate-400 hover:text-slate-700 text-xs font-bold">
                ✕ Dismiss
              </button>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2 text-[11px] text-slate-600">
              <div>Reviewer: <strong className="text-emerald-800">{selectedRow.source}</strong></div>
              <div>Preset: <strong className="text-slate-800">{selectedRow.preset}</strong></div>
              <div>Driver: <strong className="text-slate-800">{selectedRow.driver}</strong></div>
              <div>Metric: <strong className="text-slate-800">{selectedRow.metric_type}</strong></div>
            </div>
            <div className="text-[10px] text-slate-500 pt-1 border-t border-emerald-200/40">
              Test Protocol: {selectedRow.test_method}
            </div>
          </div>
        )}
      </div>

      {/* Explicit Academic Limitations & Disclaimers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 space-y-1">
          <div className="text-amber-900 font-bold flex items-center gap-1.5">
            <span>⚠️</span> Academic Note: Calibration vs. Generalization
          </div>
          <p className="text-amber-800 leading-relaxed text-[11px]">
            These 12 benchmark configurations were utilized as an in-sample calibration set to parameterize the dual-pipeline frame-time engine. 
            While these results demonstrate successful bias elimination (MAPE reduced from 28.79% to 11.86%), an independent, unseen holdout validation set is required to formally establish generalized out-of-sample accuracy.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-sky-50 border border-sky-200 space-y-1">
          <div className="text-sky-900 font-bold flex items-center gap-1.5">
            <span>ℹ️</span> Thermal Model Positioning
          </div>
          <p className="text-sky-800 leading-relaxed text-[11px]">
            Thermal metrics represent a theoretical first-principles Lumped-Element Thermal Model (LETM) at 30°C tropical ambient. 
            Unlike our FPS modeling, operating temperature calculations have NOT been empirically calibrated against physical laboratory thermocouples.
          </p>
        </div>
      </div>
    </div>
  );
}