import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { GAMES, RESOLUTIONS, MIN_VIABLE_BUDGET } from "../constants";

export default function Optimize({ setBuild, setGame, setRes }) {
  const [budget, setBudget] = useState(3500);
  const [targetGame, setTargetGameLocal] = useState("Cyberpunk 2077");
  const [targetResolution, setTargetResolutionLocal] = useState("1080p");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleOptimize = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch("http://localhost:8000/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          budget: parseFloat(budget),
          game_name: targetGame,
          resolution: targetResolution,
        }),
      });

      if (!res.ok) {
        alert(`Could not find a valid build under this budget. Try entering at least RM ${MIN_VIABLE_BUDGET.toLocaleString()}.`);
        setLoading(false);
        return;
      }

      const data = await res.json();

      setBuild({
        cpu: data.cpu.cpu_id,
        mobo: data.mobo.mobo_id,
        gpu: data.gpu.gpu_id,
        cooler: data.cooler.cooler_id,
        case: data.case.case_id,
        ram: data.ram.ram_id,
        storage: data.storage.storage_id,
        psu: data.psu.psu_id,
      });

      setGame(targetGame);
      setRes(targetResolution);
      navigate("/builder");
    } catch (err) {
      console.error(err);
      alert("Failed to connect to backend optimization API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-16">
      <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm space-y-6">
        <div>
          <span className="text-xs font-bold text-emerald-600 uppercase tracking-wider">
            0-1 Knapsack Algorithm
          </span>
          <h2 className="text-2xl font-extrabold text-slate-900 mt-1">Budget Optimization Wizard</h2>
          <p className="text-xs text-slate-500 mt-1">
            Specify your financial constraints. Our backend algorithm synthesizes the highest-performing,
            compatible PC build dynamically.
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
            className="w-full py-4 bg-slate-900 hover:bg-slate-800 text-brand-500 font-bold text-sm rounded-xl transition shadow-xl shadow-slate-900/10 disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-3"
          >
            {loading ? (
              <>
                <i className="fa-solid fa-circle-notch fa-spin"></i>
                Synthesizing Combinations...
              </>
            ) : (
              <>
                <i className="fa-solid fa-microchip"></i>
                Synthesize Best Build
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}