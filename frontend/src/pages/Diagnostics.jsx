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

      {/* Diagnostics Cards with Visual Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Bottleneck Panel */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-5 hover:shadow-md transition">
          <div className="flex justify-between items-center border-b border-slate-100 pb-3">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <i className="fa-solid fa-compress-arrows-alt text-brand-600"></i> CPU-GPU Synergy Index
            </h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result?.bottleneck_percentage > 0 ? 'bg-red-100 text-red-700' : 'bg-brand-100 text-brand-700'}`}>
              {result?.bottleneck_status || "Optimal"}
            </span>
          </div>
          
          {/* Visual Gauge */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-semibold text-slate-500">
              <span>GPU Utilization</span>
              <span>{100 - (result?.bottleneck_percentage || 0)}%</span>
            </div>
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
              <div 
                className={`h-full ${result?.bottleneck_percentage > 0 ? 'bg-red-500' : 'bg-brand-500'} transition-all duration-1000`} 
                style={{ width: `${100 - (result?.bottleneck_percentage || 0)}%` }}>
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">
            {result?.bottleneck_percentage > 0
              ? `Your chosen ${cpu.name || "CPU"} restricts the rendering pipeline of the ${gpu.name || "GPU"} by roughly ${result.bottleneck_percentage}%. Consider upgrading the processor to balance data throughput.`
              : `Optimal synergy detected! ${cpu.name || "CPU"} and ${gpu.name || "GPU"} feed data without queue delays.`}
          </p>
        </div>

        {/* Thermal Headroom Panel */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-5 hover:shadow-md transition">
          <div className="flex justify-between items-center border-b border-slate-100 pb-3">
            <h3 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <i className="fa-solid fa-temperature-half text-brand-600"></i> Thermal Headroom
            </h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${result?.thermal_status === "THROTTLING" ? 'bg-red-100 text-red-700' : 'bg-brand-100 text-brand-700'}`}>
              {result?.thermal_status || "Stable"}
            </span>
          </div>

          {/* Visual Gauge */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-semibold text-slate-500">
              <span>Predicted Load Temp</span>
              <span>{result?.predicted_temp_c ? `${Math.round(result.predicted_temp_c)}°C` : "--°C"}</span>
            </div>
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden relative">
              <div className="absolute right-[10%] top-0 bottom-0 w-0.5 bg-red-500 z-10"></div> {/* 90C Throttle Line */}
              <div 
                className={`h-full ${result?.thermal_status === "THROTTLING" ? 'bg-red-500' : 'bg-amber-500'} transition-all duration-1000`} 
                style={{ width: `${Math.min(result?.predicted_temp_c || 40, 100)}%` }}>
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">
            {result?.predicted_temp_c > 90
              ? `Critical Risk: The ${cooler.name || "Cooler"} cannot dissipate the ${cpu.tdp_watts || 65}W TDP in this ${cs.name || "case"}. Thermal throttling triggers automatically to prevent hardware damage.`
              : `Stable operation: Cooler provides sufficient dissipation headroom under standard Malaysian room ambient temperatures (30°C).`}
          </p>
        </div>
      </div>
    </div>
  );
}