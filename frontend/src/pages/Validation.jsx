import { useEffect, useState } from "react";

export default function Validation({ backendUrl = "" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedGame, setSelectedGame] = useState("ALL");

  useEffect(() => {
    fetch(`${backendUrl}/evaluation/metrics`)
      .then((res) => {
        if (!res.ok) throw new Error("Could not load validation metrics.");
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [backendUrl]);

  if (loading) return <div className="p-8 text-center text-zinc-400">Loading benchmark evidence...</div>;
  if (error || !data) return <div className="p-8 text-center text-red-400">Error: {error || "No data available"}</div>;

  const { metadata, metrics, historical_baseline_reference, by_game_engine, cases, disclosures } = data;
  const filteredCases = selectedGame === "ALL" ? cases : cases.filter((c) => c.game === selectedGame);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2.5 py-1 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
            Chapter 4 Performance Evaluation
          </span>
          <span className="px-2.5 py-1 text-xs font-semibold rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
            N = {metadata.sample_size} Reference Configurations
          </span>
        </div>
        <h1 className="text-3xl font-bold text-white">Empirical Model Verification & Residual Analysis</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Predictive performance of EcoBuild's decoupled dual-pipeline frame-time engine evaluated against condition-matched reviewer hardware benchmarks.
        </p>
      </div>

      {/* Key Metrics vs Baseline */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="text-xs text-zinc-400">Mean Absolute Pct Error (MAPE)</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{metrics.mape}%</div>
          <div className="text-xs text-zinc-500 mt-1">
            Baseline: <span className="line-through">{historical_baseline_reference.mape}%</span>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="text-xs text-zinc-400">Explanatory Power (R²)</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">{metrics.r2}</div>
          <div className="text-xs text-zinc-500 mt-1">
            Baseline: {historical_baseline_reference.r2}
          </div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="text-xs text-zinc-400">Mean Absolute Error (MAE)</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1">
            {metrics.mae} <span className="text-sm font-normal text-zinc-400">FPS</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            Baseline: {historical_baseline_reference.mae} FPS
          </div>
        </div>

        <div className="p-4 rounded-xl bg-zinc-900 border border-zinc-800">
          <div className="text-xs text-zinc-400">Residual Direction</div>
          <div className="text-sm font-semibold text-zinc-200 mt-2">
            {metrics.residual_distribution.balanced_status}
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            Baseline had 100% negative bias
          </div>
        </div>
      </div>

      {/* Disaggregated Breakdown by Game */}
      <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
        <h2 className="text-lg font-semibold text-white">Disaggregated Engine Performance</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(by_game_engine).map(([gameName, stats]) => (
            <div key={gameName} className="p-3 bg-zinc-950 rounded-lg border border-zinc-800/80">
              <div className="font-semibold text-zinc-200 text-sm truncate">{gameName}</div>
              <div className="text-[11px] text-zinc-500">{stats.engine_type} (N={stats.count})</div>
              <div className="mt-2 text-xs flex justify-between">
                <span className="text-zinc-400">MAE:</span>
                <span className="text-emerald-400 font-medium">{stats.mae} FPS</span>
              </div>
              <div className="text-xs flex justify-between">
                <span className="text-zinc-400">MAPE:</span>
                <span className="text-emerald-400 font-medium">{stats.mape}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Benchmark Matrix Table */}
      <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800 space-y-4">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
          <div>
            <h2 className="text-lg font-semibold text-white">Empirical Benchmark Dataset Matrix</h2>
            <p className="text-xs text-zinc-400">Evaluated on desktop hardware with native resolution under Ultra presets</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {["ALL", ...Object.keys(by_game_engine)].map((g) => (
              <button
                key={g}
                onClick={() => setSelectedGame(g)}
                className={`px-2.5 py-1 text-xs rounded transition ${
                  selectedGame === g ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
              <tr>
                <th className="py-2.5 px-3">ID</th>
                <th className="py-2.5 px-3">Hardware Setup</th>
                <th className="py-2.5 px-3">Workload</th>
                <th className="py-2.5 px-3 text-right">Reference FPS</th>
                <th className="py-2.5 px-3 text-right">Predicted FPS</th>
                <th className="py-2.5 px-3 text-right">Error (Diff)</th>
                <th className="py-2.5 px-3 text-right">APE (%)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
              {filteredCases.map((row) => (
                <tr key={row.id} className="hover:bg-zinc-800/30">
                  <td className="py-2 px-3 font-mono text-zinc-500">{row.id}</td>
                  <td className="py-2 px-3">{row.hardware}</td>
                  <td className="py-2 px-3">{row.game} ({row.res})</td>
                  <td className="py-2 px-3 text-right font-medium text-white">{row.actual.toFixed(0)}</td>
                  <td className="py-2 px-3 text-right font-medium text-emerald-400">{row.pred.toFixed(0)}</td>
                  <td className={`py-2 px-3 text-right font-medium ${row.error_fps < 0 ? "text-amber-400" : "text-sky-400"}`}>
                    {row.error_fps > 0 ? `+${row.error_fps}` : row.error_fps}
                  </td>
                  <td className="py-2 px-3 text-right font-medium">{row.ape_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Academic Disclosures */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-900/50 space-y-1">
          <div className="text-amber-400 font-semibold">⚠️ Academic Note: Calibration vs. Generalization</div>
          <p className="text-zinc-400 leading-relaxed">{disclosures.calibration_scope}</p>
        </div>
        <div className="p-4 rounded-xl bg-blue-950/20 border border-blue-900/50 space-y-1">
          <div className="text-blue-400 font-semibold">ℹ️ Thermal Model Positioning</div>
          <p className="text-zinc-400 leading-relaxed">{disclosures.thermal_status}</p>
        </div>
      </div>
    </div>
  );
}