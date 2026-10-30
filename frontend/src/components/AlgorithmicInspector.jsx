import { useState } from "react";

export default function AlgorithmicInspector({ telemetry }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!telemetry) return null;

  const { pipeline_latencies_ms, active_penalties, final_outputs, thermal_assumptions } = telemetry;

  return (
    <div className="mt-4 border border-zinc-800 rounded-xl bg-zinc-900/60 overflow-hidden text-xs">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex justify-between items-center px-4 py-3 bg-zinc-900/80 hover:bg-zinc-800 transition text-zinc-300 font-medium"
      >
        <span className="flex items-center gap-2">
          <span className="text-emerald-400 font-mono">ƒ(x)</span> Inspect Algorithmic Derivation
        </span>
        <span className="text-zinc-500">{isOpen ? "Hide ▲" : "Show Telemetry ▼"}</span>
      </button>

      {isOpen && (
        <div className="p-4 space-y-4 border-t border-zinc-800 text-zinc-400">
          {/* Pipeline Breakdown */}
          <div>
            <div className="text-zinc-200 font-semibold mb-1">1. Decoupled Frame Latencies (Pre-Penalty)</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <div className="text-[10px] text-zinc-500 font-sans">t_GPU</div>
                <div className="text-emerald-400 text-sm">{pipeline_latencies_ms.t_gpu} ms</div>
              </div>
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <div className="text-[10px] text-zinc-500 font-sans">t_CPU</div>
                <div className="text-sky-400 text-sm">{pipeline_latencies_ms.t_cpu} ms</div>
              </div>
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <div className="text-[10px] text-zinc-500 font-sans">t_sync</div>
                <div className="text-zinc-400 text-sm">{pipeline_latencies_ms.t_sync} ms</div>
              </div>
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <div className="text-[10px] text-zinc-500 font-sans">Bottleneck</div>
                <div className="text-amber-400 text-xs mt-0.5 font-sans font-medium">{pipeline_latencies_ms.dominant_stage}</div>
              </div>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Pre-Penalty Frame Time: <code>max(t_GPU, t_CPU) + 0.5ms = {pipeline_latencies_ms.t_pipeline_base} ms</code> ({telemetry.unconstrained_base_fps} FPS base)
            </p>
          </div>

          {/* Active Penalties */}
          <div>
            <div className="text-zinc-200 font-semibold mb-1">2. Applied Multipliers & Constraints</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <span className="text-[10px] text-zinc-500 block">VRAM Multiplier</span>
                <span className="font-mono text-zinc-200">{active_penalties.vram_avg_multiplier}x</span>
              </div>
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <span className="text-[10px] text-zinc-500 block">RAM Channel Multiplier</span>
                <span className="font-mono text-zinc-200">{active_penalties.ram_channel_multiplier}x</span>
              </div>
              <div className="p-2 bg-zinc-950 rounded border border-zinc-800">
                <span className="text-[10px] text-zinc-500 block">Thermal Multiplier</span>
                <span className="font-mono text-zinc-200">{active_penalties.thermal_clock_multiplier}x</span>
              </div>
            </div>
            <p className="text-[11px] text-zinc-500 mt-1">
              Effective Final Frame Time: <code>1000 / {final_outputs.predicted_avg_fps} FPS = {final_outputs.effective_frame_time_ms} ms</code>
            </p>
          </div>

          {/* Thermal Heuristic Disclaimer */}
          <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800 text-[11px] space-y-1">
            <div className="text-zinc-300 font-semibold">Thermal Calculation Assumptions (LETM)</div>
            <div className="text-zinc-500">
              Total Heat: {thermal_assumptions.total_watts_in_case}W | Internal Air ΔT: +{thermal_assumptions.internal_air_delta_c}°C over ambient.
            </div>
            <div className="text-amber-500/90 italic text-[10px]">
              Status: {thermal_assumptions.empirical_status}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}