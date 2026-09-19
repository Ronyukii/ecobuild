import { useState } from "react";
import { Link } from "react-router-dom";

export default function Builder({ db, build, setBuild, result, game, setGame, res, setRes }) {
  const [activeDrawer, setActiveDrawer] = useState(null);

  const categories = [
    { key: "cpu", label: "Processor (CPU)" },
    { key: "mobo", label: "Motherboard" },
    { key: "gpu", label: "Graphics Card (GPU)" },
    { key: "cooler", label: "CPU Cooler" },
    { key: "case", label: "PC Case (Chassis)" },
    { key: "ram", label: "RAM Memory" },
    { key: "storage", label: "Primary Storage" },
    { key: "psu", label: "Power Supply Unit (PSU)" },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
      {/* Component List */}
      <section className="lg:col-span-7 space-y-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="font-bold text-slate-900 text-lg">System Configurator</h2>
              <p className="text-xs text-slate-500">Click any row to change components</p>
            </div>
            <Link
              to="/optimize"
              className="text-xs font-bold text-emerald-600 hover:text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200"
            >
              Need Auto-Pick? →
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {categories.map((cat) => {
              const currentId = build[cat.key];
              const item = db[cat.key]?.[currentId] || { name: "Select component...", price: 0 };

              return (
                <div
                  key={cat.key}
                  onClick={() => setActiveDrawer(cat.key)}
                  className="py-3.5 flex items-center justify-between cursor-pointer hover:bg-slate-50 px-2 rounded-xl transition"
                >
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      {cat.label}
                    </span>
                    <span className="font-bold text-slate-800 text-sm hover:text-emerald-600">
                      {item.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-600 bg-slate-100 px-2.5 py-1 rounded">
                      RM {parseFloat(item.price || 0).toFixed(2)}
                    </span>
                    <span className="text-slate-400 text-sm">→</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Right Dashboard */}
      <section className="lg:col-span-5 space-y-6">
        <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6 sticky top-24">
          <div className="border-b border-slate-100 pb-3 flex items-center justify-between">
            <h3 className="font-bold text-slate-900 text-base">Prediction Dashboard</h3>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
              FASTAPI CONNECTED
            </span>
          </div>

          {/* Pricing Box */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
              Estimated Total (Shopee / Lazada Scraped)
            </span>
            <div className="text-3xl font-extrabold text-slate-900 mt-1">
              RM {result?.total_price_rm?.toFixed(2) || "0.00"}
            </div>
          </div>

          {/* Game Controls */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                Game Title
              </label>
              <select
                value={game}
                onChange={(e) => setGame(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 text-xs font-bold rounded-lg p-2 outline-none"
              >
                <option value="Cyberpunk 2077">Cyberpunk 2077</option>
                <option value="Valorant">Valorant</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                Resolution
              </label>
              <select
                value={res}
                onChange={(e) => setRes(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 text-xs font-bold rounded-lg p-2 outline-none"
              >
                <option value="1080p">1080p (FHD)</option>
                <option value="1440p">1440p (QHD)</option>
                <option value="4K">4K (UHD)</option>
              </select>
            </div>
          </div>

          {/* FPS Gauge */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-400 font-semibold block">Predicted Framerate</span>
              <span className="text-3xl font-extrabold text-slate-900">
                {result?.predicted_fps ?? "--"} FPS
              </span>
            </div>
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                result?.bottleneck_status === "CPU Bottleneck"
                  ? "bg-red-100 text-red-700"
                  : "bg-emerald-100 text-emerald-700"
              }`}
            >
              {result?.bottleneck_status || "Checking..."}
            </span>
          </div>

          {/* Thermal Gauge */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-2">
            <div className="flex justify-between items-baseline">
              <div>
                <span className="text-xs text-slate-400 font-semibold block">CPU Equilibrium Temp</span>
                <span className="text-3xl font-extrabold text-slate-900">
                  {result?.predicted_temp_c ? `${result.predicted_temp_c}°C` : "--°C"}
                </span>
              </div>
              <span
                className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                  result?.thermal_status === "THROTTLING"
                    ? "bg-red-100 text-red-700"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {result?.thermal_status || "Checking..."}
              </span>
            </div>
            <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  result?.thermal_status === "THROTTLING" ? "bg-red-500" : "bg-emerald-500"
                }`}
                style={{ width: `${Math.min(result?.predicted_temp_c || 40, 100)}%` }}
              ></div>
            </div>
          </div>

          {/* Warnings Box */}
          {result?.warnings?.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-xs space-y-1">
              <span className="font-bold block">Compatibility & Thermal Conflicts:</span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <Link
            to="/diagnostics"
            className="block text-center w-full bg-slate-900 hover:bg-slate-800 text-white font-bold py-3 px-4 rounded-xl text-xs transition shadow-sm"
          >
            View Full Diagnostic Report →
          </Link>
        </div>
      </section>

      {/* Selection Modal (Drawer) */}
      {activeDrawer && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-lg rounded-2xl p-6 shadow-xl space-y-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base uppercase">
                Select {activeDrawer}
              </h3>
              <button
                onClick={() => setActiveDrawer(null)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold"
              >
                ✕ Close
              </button>
            </div>

            <div className="divide-y divide-slate-100 overflow-y-auto flex-grow pr-1">
              {Object.values(db[activeDrawer] || {}).map((item) => {
                const itemId =
                  item[`${activeDrawer}_id`] ||
                  item.mobo_id ||
                  item.cooler_id ||
                  item.case_id ||
                  item.ram_id ||
                  item.storage_id ||
                  item.psu_id;

                const isCurrent = build[activeDrawer] === itemId;

                return (
                  <div
                    key={itemId}
                    onClick={() => {
                      setBuild((prev) => ({ ...prev, [activeDrawer]: itemId }));
                      setActiveDrawer(null);
                    }}
                    className={`py-3 px-2 flex items-center justify-between cursor-pointer rounded-lg transition ${
                      isCurrent ? "bg-emerald-50 border border-emerald-200" : "hover:bg-slate-50"
                    }`}
                  >
                    <div>
                      <h4 className="font-bold text-slate-900 text-xs">{item.name}</h4>
                      <p className="text-[10px] text-slate-400 font-medium">
                        {item.socket ? `Socket: ${item.socket} | ` : ""}
                        {item.tdp_watts ? `TDP: ${item.tdp_watts}W | ` : ""}
                        {item.base_score ? `Score: ${item.base_score}` : ""}
                      </p>
                    </div>
                    <span className="text-xs font-bold text-emerald-700 bg-slate-100 px-2 py-0.5 rounded">
                      RM {parseFloat(item.price || 0).toFixed(2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}