// frontend/src/pages/Optimize.jsx
import { useState } from "react";
import { Link } from "react-router-dom";

export default function Optimize({ setBuild, backendUrl }) {
  const [prompt, setPrompt] = useState("");
  const [budget, setBudget] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [loading, setLoading] = useState(false);
  const [optimizedResult, setOptimizedResult] = useState(null);
  const [error, setError] = useState(null);
  const [showLiveAudit, setShowLiveAudit] = useState(true);
  const [showArchitectureExplainer, setShowArchitectureExplainer] = useState(false);

  const handleOptimize = async (e) => {
    e.preventDefault();
    if (!prompt.trim() && !budget) {
      setError("Please enter a budget target (e.g. 3500) or describe your build (e.g. 'i5 12400f with RTX 4060').");
      return;
    }

    setLoading(true);
    setError(null);

    const targetUrl = backendUrl || "http://localhost:8000";

    try {
      const res = await fetch(`${targetUrl}/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim() || null,
          budget: budget ? parseFloat(budget) : null,
          resolution: resolution,
          ambient_temp: 30.0
        })
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
      }

      const data = await res.json();
      setOptimizedResult(data);
    } catch (err) {
      console.error("Optimize Error:", err);
      setError(
        err.message.includes("Failed to fetch")
          ? "Unable to reach EcoBuild API. If Render is waking up from sleep, please wait ~20 seconds and click Optimize again."
          : err.message
      );
    } finally {
      setLoading(false);
    }
  };

  const handleApplyToBuilder = () => {
    if (!optimizedResult) return;
    setBuild({
      cpu: optimizedResult.cpu.cpu_id,
      mobo: optimizedResult.mobo.mobo_id,
      gpu: optimizedResult.gpu.gpu_id,
      cooler: optimizedResult.cooler.cooler_id,
      case: optimizedResult.case.case_id,
      ram: optimizedResult.ram.ram_id,
      psu: optimizedResult.psu.psu_id,
      storage: optimizedResult.storage.storage_id
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8 text-slate-800">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            Decision Support System (DSS)
          </span>
          <span className="px-2.5 py-0.5 text-xs font-bold rounded bg-slate-100 text-slate-700 border border-slate-200">
            Multi-Choice Knapsack &amp; NLP Intent
          </span>
        </div>
        <h1 className="text-3xl font-black text-slate-900 tracking-tight">
          Intelligent System Auto-Optimizer
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Specify a budget ceiling, describe desired components in natural language, or combine both.
          Our Branch-and-Bound solver resolves physical compatibility and maximizes multi-game performance across the entire catalog.
        </p>
      </div>

      {/* Input Formulation Card */}
      <form onSubmit={handleOptimize} className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
          {/* Natural Language Prompt */}
          <div className="md:col-span-8 space-y-1.5">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              Describe Your Desired Build (Natural Language Prompt)
            </label>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder='e.g., "Build me an i5 12400f with RTX 4060 and 16GB RAM"'
              className="w-full bg-slate-50 border border-slate-200 text-sm font-medium rounded-xl p-3 outline-none focus:border-emerald-500 transition"
            />
            <p className="text-[11px] text-slate-400">
              Mention any specific chip, memory size, or form-factor. Sockets, clearance, and PSU sizing are handled automatically.
            </p>
          </div>

          {/* Budget Target */}
          <div className="md:col-span-4 space-y-1.5">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              Budget Target (Optional)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-3 text-sm font-bold text-slate-400">RM</span>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="e.g., 3500"
                className="w-full bg-slate-50 border border-slate-200 text-sm font-bold rounded-xl p-3 pl-11 outline-none focus:border-emerald-500 transition"
              />
            </div>
            <p className="text-[11px] text-slate-400">
              Leave blank to find the most cost-effective build for your prompt.
            </p>
          </div>
        </div>

        {/* Resolution Selector & Submit */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-slate-500 uppercase">Target Resolution:</span>
            {["1080p", "1440p", "4K"].map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setResolution(r)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition ${
                  resolution === r
                    ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full sm:w-auto px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl shadow-sm transition disabled:opacity-50"
          >
            {loading ? "Synthesizing Combinations..." : "🚀 Run Heuristic Optimizer"}
          </button>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl font-medium leading-relaxed">
            ⚠️ {error}
          </div>
        )}
      </form>

      {/* Results View (Renders once optimized) */}
      {optimizedResult && (
        <div className="space-y-6">
          {/* Summary Banner */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  OPTIMAL CONFIGURATION FOUND
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  Composite Score: {optimizedResult.composite_gaming_score} pts
                </span>
              </div>
              <h2 className="text-2xl font-black text-slate-900">
                {optimizedResult.cpu.name} + {optimizedResult.gpu.name}
              </h2>
              <p className="text-xs text-slate-500">
                Full 8-part build resolved with 100% physical clearance and verified VRM thermal headroom.
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                  Scraped Total
                </span>
                <span className="text-3xl font-black text-slate-900">
                  RM {optimizedResult.total_price_rm.toFixed(2)}
                </span>
              </div>
              <Link
                to="/builder"
                onClick={handleApplyToBuilder}
                className="px-5 py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl shadow-sm transition"
              >
                Apply to System Builder →
              </Link>
            </div>
          </div>

          {/* Catalog Performance Grid */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Multi-Game Predicted Performance ({resolution})
                </h3>
                <p className="text-xs text-slate-500">
                  Evaluated using a geometric mean index across all catalog workloads to prevent single-game optimization bias.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {Object.entries(optimizedResult.catalog_game_fps || {}).map(([gameName, fps]) => (
                <div key={gameName} className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="text-xs font-bold text-slate-700 block truncate">{gameName}</span>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-2xl font-black text-emerald-600">{fps}</span>
                    <span className="text-xs font-bold text-slate-400">FPS</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Component BOM List */}
          <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-3">
            <h3 className="text-base font-bold text-slate-900 mb-2">Synthesized Bill of Materials</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
              {[
                { label: "Processor", item: optimizedResult.cpu },
                { label: "Motherboard", item: optimizedResult.mobo },
                { label: "Graphics Card", item: optimizedResult.gpu },
                { label: "Memory (RAM)", item: optimizedResult.ram },
                { label: "CPU Cooler", item: optimizedResult.cooler },
                { label: "Chassis", item: optimizedResult.case },
                { label: "Power Supply", item: optimizedResult.psu },
                { label: "Storage", item: optimizedResult.storage },
              ].map(({ label, item }) => (
                <div key={label} className="p-3 bg-slate-50 rounded-xl border border-slate-100 flex justify-between items-center">
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">{label}</span>
                    <span className="font-bold text-slate-800">{item.name}</span>
                  </div>
                  <span className="font-extrabold text-slate-900 font-mono">
                    RM {parseFloat(item.price || 0).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Live Execution & Decision Audit Drawer */}
          <div className="border border-slate-200 rounded-2xl bg-white overflow-hidden shadow-sm">
            <button
              onClick={() => setShowLiveAudit(!showLiveAudit)}
              className="w-full flex justify-between items-center p-4 bg-slate-50 hover:bg-slate-100 transition text-slate-800 text-xs font-bold"
            >
              <span className="flex items-center gap-2">
                <span className="text-emerald-600 font-mono">🔍</span>
                <span>How the Optimizer Chose These Parts (Live Decision Audit)</span>
              </span>
              <span className="text-slate-400">{showLiveAudit ? "Hide Details ▲" : "Inspect Audit ▼"}</span>
            </button>

            {showLiveAudit && (
              <div className="p-5 space-y-4 border-t border-slate-200 text-xs text-slate-600 bg-white">
                {/* Intent Parsing */}
                <div>
                  <h4 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] mb-1">
                    1. Natural Language Intent Extraction
                  </h4>
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                    {optimizedResult.optimizer_telemetry?.natural_language_audit?.parsing_notes?.length > 0 ? (
                      optimizedResult.optimizer_telemetry.natural_language_audit.parsing_notes.map((note, i) => (
                        <div key={i} className="text-emerald-700 flex items-center gap-1.5 font-medium">
                          <span>✓</span> {note}
                        </div>
                      ))
                    ) : (
                      <div className="text-slate-400 italic">No specific prompt constraints detected; pure budget ceiling optimization applied.</div>
                    )}
                  </div>
                </div>

                {/* Combinatorial Pruning Funnel */}
                <div>
                  <h4 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] mb-1">
                    2. Combinatorial Search Space Pruning
                  </h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-bold">Search Space</span>
                      <span className="text-sm font-black text-slate-800 font-mono">
                        {optimizedResult.optimizer_telemetry?.search_space_pruning?.primary_combinations} Pairs
                      </span>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-bold">Pruned by Budget</span>
                      <span className="text-sm font-black text-amber-600 font-mono">
                        {optimizedResult.optimizer_telemetry?.search_space_pruning?.pruned_by_budget_limit}
                      </span>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-bold">Clearance Conflicts</span>
                      <span className="text-sm font-black text-red-600 font-mono">
                        {optimizedResult.optimizer_telemetry?.search_space_pruning?.pruned_by_physical_clearance}
                      </span>
                    </div>
                    <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-100">
                      <span className="text-[10px] text-slate-400 block font-bold">Simulated Builds</span>
                      <span className="text-sm font-black text-emerald-600 font-mono">
                        {optimizedResult.optimizer_telemetry?.search_space_pruning?.feasible_candidates_simulated}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Component Selection Rationales */}
                <div>
                  <h4 className="font-bold text-slate-800 uppercase tracking-wider text-[11px] mb-1">
                    3. Component Selection Rationales
                  </h4>
                  <ul className="space-y-1.5 p-3 bg-slate-50 rounded-xl border border-slate-100 text-[11px]">
                    {Object.entries(optimizedResult.optimizer_telemetry?.selection_rationales || {}).map(([comp, text]) => (
                      <li key={comp} className="flex items-start gap-2">
                        <span className="text-emerald-600 font-bold">→</span>
                        <span>{text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Permanently Visible Underlying Optimizer Architecture Explainer */}
      <div className="border border-slate-200 rounded-2xl bg-white overflow-hidden shadow-sm">
        <button
          onClick={() => setShowArchitectureExplainer(!showArchitectureExplainer)}
          className="w-full flex justify-between items-center p-4 bg-slate-50 hover:bg-slate-100 transition text-slate-800 text-xs font-bold"
        >
          <span className="flex items-center gap-2">
            <span className="text-slate-500 font-mono">⚙️</span>
            <span>Underlying Engine Architecture: Branch-and-Bound &amp; 10 Tolerance Rules</span>
          </span>
          <span className="text-slate-400">{showArchitectureExplainer ? "Hide Architecture ▲" : "View Engine Architecture ▼"}</span>
        </button>

        {showArchitectureExplainer && (
          <div className="p-6 space-y-5 border-t border-slate-200 text-xs text-slate-600 leading-relaxed bg-white">
            <div>
              <h4 className="font-bold text-slate-900 text-sm mb-1">
                Combinatorial 0–1 Multiple-Choice Knapsack Formulation (MCKP)
              </h4>
              <p className="text-slate-500 text-xs leading-relaxed">
                Rather than evaluating all 9.5 million theoretical combinations via brute force, the optimizer formulates PC configuration as a Multiple-Choice Knapsack problem solved via Branch-and-Bound:
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-emerald-700 font-bold block text-xs">1. Budget Envelope Bound</span>
                <p className="text-[11px] text-slate-500">
                  Computes an analytical minimum ancillary floor (~RM 820). If <code>CPU_cost + GPU_cost + Floor &gt; Budget</code>, the entire branch is culled immediately.
                </p>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-emerald-700 font-bold block text-xs">2. Geometric Mean FPS Index</span>
                <p className="text-[11px] text-slate-500">
                  Computes a scale-independent geometric mean normalized against baseline anchors across Cyberpunk 2077, Elden Ring, CS2, and Valorant.
                </p>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-1">
                <span className="text-emerald-700 font-bold block text-xs">3. 10 Physical Constraints</span>
                <p className="text-[11px] text-slate-500">
                  Enforces GPU length, cooler height, PSU depth, RAM clearance, VRM thermal limits, and PCIe lane saturation deterministically.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}