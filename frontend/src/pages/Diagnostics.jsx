import "react";
import { Link } from "react-router-dom";

export default function Diagnostics({ build, db, result }) {
  const cpu = db.cpu?.[build.cpu] || {};
  const gpu = db.gpu?.[build.gpu] || {};
  const cooler = db.cooler?.[build.cooler] || {};
  const cs = db.case?.[build.case] || {};

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900">Explainable Diagnostic Report</h2>
          <p className="text-xs text-slate-500">MCDM Analytical Feedback Loop Breakdown</p>
        </div>
        <Link
          to="/builder"
          className="text-xs font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1.5 rounded-lg shadow-sm"
        >
          ← Back to Builder
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="font-bold text-sm text-slate-900">CPU-GPU Bottleneck Index</h3>
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
              {result?.bottleneck_status || "Optimal"}
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            {result?.bottleneck_percentage > 0
              ? `Your chosen ${cpu.name || "CPU"} restricts the rendering pipeline of the ${gpu.name || "GPU"} by roughly ${result.bottleneck_percentage}%. Consider upgrading the processor to balance data throughput.`
              : `Optimal synergy detected! ${cpu.name || "CPU"} and ${gpu.name || "GPU"} feed data without queue delays.`}
          </p>
        </div>

        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="font-bold text-sm text-slate-900">Thermal Headroom & Equilibrium</h3>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                result?.thermal_status === "THROTTLING"
                  ? "bg-red-100 text-red-700"
                  : "bg-emerald-100 text-emerald-700"
              }`}
            >
              {result?.thermal_status || "Stable"}
            </span>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            {result?.predicted_temp_c > 90
              ? `Critical Risk: The ${cooler.name || "Cooler"} cannot dissipate the ${cpu.tdp_watts || 65}W TDP in this ${cs.name || "case"} enclosure. Thermal throttling triggers automatically to prevent hardware damage.`
              : `Stable operation: Cooler provides sufficient dissipation headroom under standard Malaysian room ambient temperatures (30°C).`}
          </p>
        </div>
      </div>
    </div>
  );
}