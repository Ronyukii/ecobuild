import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GAMES, RESOLUTIONS, MIN_VIABLE_BUDGET } from "../constants";

export default function Optimize({ setBuild, setGame, setRes, backendUrl }) {
  const [budget, setBudget] = useState(3800);
  const [targetGame, setTargetGameLocal] = useState("Cyberpunk 2077");
  const [targetResolution, setTargetResolutionLocal] = useState("1080p");
  const [loading, setLoading] = useState(false);
  const [optimizedResult, setOptimizedResult] = useState(null);
  const navigate = useNavigate();

  const handleOptimize = async (e) => {
    e.preventDefault();
    setLoading(true);
    setOptimizedResult(null);

    const apiUrl = backendUrl || "http://localhost:8000";

    try {
      const res = await fetch(`${apiUrl}/optimize`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "Bypass-Tunnel-Reminder": "true"
          },
        body: JSON.stringify({
          budget: parseFloat(budget),
          game_name: targetGame,
          resolution: targetResolution,
          ambient_temp: 30.0,
        }),
      });

      if (!res.ok) {
        alert(`Could not find a valid build under this budget. Try entering at least RM ${MIN_VIABLE_BUDGET.toLocaleString()}.`);
        setLoading(false);
        return;
      }

      const data = await res.json();
      
      // If no unavailable components detected, load directly into builder
      if (!data.alternatives || data.alternatives.length === 0) {
        applyBuildAndNavigate(data, false);
      } else {
        // Show the In-Stock Alternative Advisory screen
        setOptimizedResult(data);
      }
    } catch (err) {
      console.error(err);
      alert("Failed to connect to backend optimization API.");
    } finally {
      setLoading(false);
    }
  };

  const applyBuildAndNavigate = (data, useAlternative = false) => {
    const gpuId = (useAlternative && data.alternatives?.[0]) 
      ? data.alternatives[0].recommended_alternative.id 
      : data.gpu.gpu_id;

    setBuild({
      cpu: data.cpu.cpu_id,
      mobo: data.mobo.mobo_id,
      gpu: gpuId,
      cooler: data.cooler.cooler_id,
      case: data.case.case_id,
      ram: data.ram.ram_id,
      storage: data.storage.storage_id,
      psu: data.psu.psu_id,
    });

    setGame(targetGame);
    setRes(targetResolution);
    navigate("/builder");
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 space-y-6">
      <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm space-y-6">
        <div>
          <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">
            Branch-and-Bound Heuristic Optimization
          </span>
          <h2 className="text-2xl font-extrabold text-slate-900 mt-1">Budget Optimization Wizard</h2>
          <p className="text-xs text-slate-500 mt-1">
            Specify your financial constraints. Our algorithm synthesizes the highest-performing,
            physically compatible PC build, cross-referenced with live local e-commerce stock.
          </p>
        </div>

        <form onSubmit={handleOptimize} className="space-y-4">
          <div>
            <label className="text-xs font-bold text-slate-600 block mb-1">
              Maximum Budget Ceiling (RM)
            </label>
            <div className="relative">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">
                RM
              </span>
              <input
                type="number"
                min={MIN_VIABLE_BUDGET}
                step="50"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-12 pr-4 py-2.5 text-sm font-bold outline-none focus:border-emerald-600"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Target Game</label>
              <select
                value={targetGame}
                onChange={(e) => setTargetGameLocal(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs font-bold outline-none"
              >
                {GAMES.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-bold text-slate-600 block mb-1">Resolution</label>
              <select
                value={targetResolution}
                onChange={(e) => setTargetResolutionLocal(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl p-2.5 text-xs font-bold outline-none"
              >
                {RESOLUTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-xl transition shadow-sm disabled:opacity-70 flex items-center justify-center gap-2"
          >
            {loading ? "Synthesizing Combinations..." : "⚡ Synthesize Best Build"}
          </button>
        </form>
      </div>

      {/* ========================================================================= */}
      {/* IN-STOCK ALTERNATIVE ADVISORY CARD                                        */}
      {/* ========================================================================= */}
      {optimizedResult && optimizedResult.alternatives?.length > 0 && (
        <div className="bg-white border-2 border-amber-300 rounded-2xl p-6 shadow-md space-y-5 animate-fade-in">
          <div className="flex items-center justify-between border-b border-amber-100 pb-3">
            <div>
              <span className="text-[10px] font-bold text-amber-700 uppercase tracking-wider bg-amber-100 px-2 py-0.5 rounded">
                Market Availability Advisory
              </span>
              <h3 className="font-extrabold text-slate-900 text-base mt-1">
                Out-of-Stock Component Detected in Optimized Build
              </h3>
            </div>
          </div>

          {optimizedResult.alternatives.map((alt, idx) => (
            <div key={idx} className="space-y-4">
              <p className="text-xs text-slate-600 leading-relaxed">
                The theoretical optimum graphics card for your budget ceiling is the{" "}
                <strong className="text-slate-900">{alt.unavailable_component.name}</strong> (MSRP RM {alt.unavailable_component.msrp.toFixed(2)}), 
                but it is currently <strong>out of stock / unavailable</strong> on Shopee and Lazada.
              </p>

              {/* Comparison Box */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Theoretical Pick (Out of Stock)</span>
                  <h4 className="text-xs font-bold text-slate-800">{alt.unavailable_component.name}</h4>
                  <p className="text-xs font-semibold text-slate-500">MSRP: RM {alt.unavailable_component.msrp.toFixed(2)}</p>
                  <span className="inline-block text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                    ○ Out of Stock
                  </span>
                </div>

                <div className="space-y-1 border-t md:border-t-0 md:border-l border-slate-200 pt-2 md:pt-0 md:pl-3">
                  <span className="text-[10px] font-bold text-emerald-600 uppercase">Recommended In-Stock Alternative</span>
                  <h4 className="text-xs font-bold text-emerald-900">{alt.recommended_alternative.name}</h4>
                  <p className="text-xs font-extrabold text-emerald-700">
                    RM {alt.recommended_alternative.price_rm.toFixed(2)}{" "}
                    <span className="text-[10px] font-normal text-slate-500">
                      ({alt.recommended_alternative.price_diff <= 0 ? `Saves RM ${Math.abs(alt.recommended_alternative.price_diff).toFixed(2)}` : `+RM ${alt.recommended_alternative.price_diff.toFixed(2)}`})
                    </span>
                  </p>
                  <span className="inline-block text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                    ● In Stock on {alt.recommended_alternative.platform} ({alt.recommended_alternative.fps_diff >= 0 ? `+${alt.recommended_alternative.fps_diff}` : alt.recommended_alternative.fps_diff} FPS)
                  </span>
                </div>
              </div>

              {/* Decision Action Buttons */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => applyBuildAndNavigate(optimizedResult, true)}
                  className="py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-sm transition flex items-center justify-center gap-2"
                >
                  <span>✓</span> Swap to In-Stock & Open Builder
                </button>
                <button
                  type="button"
                  onClick={() => applyBuildAndNavigate(optimizedResult, false)}
                  className="py-3 px-4 bg-white hover:bg-slate-100 text-slate-700 border border-slate-300 font-bold text-xs rounded-xl transition"
                >
                  Keep Theoretical (MSRP)
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}