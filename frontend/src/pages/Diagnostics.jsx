import "react";
import { Link } from "react-router-dom";

export default function Diagnostics({ build, db, result, ambientTemp = 30 }) {
  const cpu = db.cpu?.[build.cpu] || {};
  const gpu = db.gpu?.[build.gpu] || {};
  const cooler = db.cooler?.[build.cooler] || {};
  const cs = db.case?.[build.case] || {};

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900">Explainable Hardware Diagnostics</h2>
          <p className="text-xs text-slate-500">
            MCDM Physics Feedback Loop • Ambient Baseline: {ambientTemp}°C
          </p>
        </div>
        <Link
          to="/builder"
          className="text-xs font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm"
        >
          ← Back to Builder
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* CPU-GPU Pipeline Synergy Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 hover:shadow-md transition">
          <div className="flex justify-between items-center border-b border-slate-100 pb-3">
            <h3 className="font-bold text-sm text-slate-900">
              CPU-GPU Pipeline Synergy
            </h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result?.bottleneck_percentage > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {result?.bottleneck_status || "Balanced"}
            </span>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs font-semibold text-slate-500">
              <span>GPU Pipeline Saturation</span>
              <span>{Math.round(100 - (result?.bottleneck_percentage || 0))}%</span>
            </div>
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
              <div 
                className={`h-full ${result?.bottleneck_percentage > 0 ? 'bg-red-500' : 'bg-emerald-500'} transition-all duration-700`} 
                style={{ width: `${Math.max(10, 100 - (result?.bottleneck_percentage || 0))}%` }}>
              </div>
            </div>
          </div>

          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-600 space-y-1">
            <p>
              <strong>Frametime Stability:</strong> {result?.frametime_stability_pct ?? 75}%
            </p>
            <p>
              {result?.bottleneck_percentage > 0
                ? `${cpu.name} creates a ${result.bottleneck_percentage}% bottleneck on ${gpu.name}. 1% low framerate drops to ${result?.fps_1pct_low || "--"} FPS, causing intermittent micro-stutters.`
                : `Balanced throughput: ${cpu.name} consistently feeds frame queues to ${gpu.name} without pipeline starving.`}
            </p>
          </div>
        </div>

        {/* Dual-Chamber Thermal Headroom Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4 hover:shadow-md transition">
          <div className="flex justify-between items-center border-b border-slate-100 pb-3">
            <h3 className="font-bold text-sm text-slate-900">
              Dual Thermal Headroom
            </h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result?.thermal_status?.includes("THROTTLING") ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
              {result?.thermal_status || "Stable"}
            </span>
          </div>

          <div className="space-y-1">
            <div className="flex justify-between text-xs font-semibold text-slate-500">
              <span>CPU Temp / Throttle Ceiling</span>
              <span>{Math.round(result?.cpu_temp_c || 45)}°C / 90°C</span>
            </div>
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden relative">
              <div 
                className={`h-full ${result?.cpu_temp_c > 90 ? 'bg-red-500' : 'bg-amber-500'} transition-all duration-700`} 
                style={{ width: `${Math.min(100, ((result?.cpu_temp_c || 45) / 100) * 100)}%` }}>
              </div>
            </div>
          </div>

          <div className="bg-slate-50 p-3 rounded-lg border border-slate-100 text-xs text-slate-600 space-y-1">
            <p>
              <strong>GPU Temp:</strong> {Math.round(result?.gpu_temp_c || 50)}°C • <strong>Internal Case Air:</strong> {Math.round(result?.case_internal_temp_c || 35)}°C
            </p>
            <p>
              {result?.cpu_temp_c > 90
                ? `Critical: The ${cooler.name} cannot dissipate the combined ${cpu.tdp_watts}W CPU and GPU exhaust in the ${cs.name} under ${ambientTemp}°C room conditions.`
                : `Thermal safety verified: Adequate convection headroom maintained inside ${cs.name}.`}
            </p>
          </div>
        </div>

        {/* VRAM Capacity & Texture Memory Card */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3 md:col-span-2">
          <div className="flex justify-between items-center border-b border-slate-100 pb-2">
            <h3 className="font-bold text-sm text-slate-900">
              Video Memory (VRAM) Assessment
            </h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result?.vram_status?.includes("Deficit") ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"}`}>
              {result?.vram_status || "Optimal"}
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            {result?.vram_status?.includes("Deficit")
              ? `Warning: This configuration exceeds your GPU's local video buffer. High-resolution texture paging over the PCIe bus will lower 1% low frame consistency.`
              : `Your GPU's VRAM buffer is adequate for rendering assets without PCIe texture thrashing.`}
          </p>
        </div>

      </div>
    </div>
  );
}