import { useState } from "react";
import { Link } from "react-router-dom";
import { GAMES, RESOLUTIONS } from "../constants";

export default function Builder({ db, build, setBuild, result, game, setGame, res, setRes }) {
  const [activeDrawer, setActiveDrawer] = useState(null);
  const [bomData, setBomData] = useState(null);
  const [isBomLoading, setIsBomLoading] = useState(false);
  const [showBomModal, setShowBomModal] = useState(false);

  const handleExportBOM = async () => {
    setIsBomLoading(true);
    try {
      const response = await fetch("http://localhost:8000/export/bom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          cpu_id: build.cpu,
          mobo_id: build.mobo,
          gpu_id: build.gpu,
          cooler_id: build.cooler,
          case_id: build.case,
          ram_id: build.ram,
          psu_id: build.psu,
          storage_id: build.storage,
          game_name: game,
          resolution: res,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to generate Bill of Materials");
      }

      const data = await response.json();
      setBomData(data);
      setShowBomModal(true);
    } catch (err) {
      console.error("Failed to export BOM:", err);
      alert("Could not generate Bill of Materials. Make sure your FastAPI backend is running.");
    } finally {
      setIsBomLoading(false);
    }
  };

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
            <div className="flex justify-between items-center">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
                Estimated Total (Shopee / Lazada Scraped)
              </span>
              {result?.pricing_source && (
                <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                  {result.pricing_source}
                </span>
              )}
            </div>
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
                {GAMES.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
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
                {RESOLUTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
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

          {/* Action Links */}
          <div className="space-y-2">
            <Link
              to="/diagnostics"
              className="block text-center w-full bg-slate-900 hover:bg-slate-800 text-white font-bold py-3 px-4 rounded-xl text-xs transition shadow-sm"
            >
              View Full Diagnostic Report →
            </Link>
            <button
              onClick={handleExportBOM}
              disabled={isBomLoading}
              className="block text-center w-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-bold py-3 px-4 rounded-xl text-xs transition shadow-sm"
            >
              {isBomLoading ? "Generating Official Receipt..." : "📄 Export Bill of Materials (BOM) Receipt"}
            </button>
          </div>

          {/* E-Commerce Shortcuts */}
          <div className="pt-4 border-t border-slate-200 space-y-3">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block text-center">
              Quick Search Selected CPU & GPU
            </span>
            <div className="grid grid-cols-2 gap-3">
              <a 
                href={`https://shopee.com.my/search?keyword=${encodeURIComponent(db.cpu?.[build.cpu]?.name || "")}`} 
                target="_blank" rel="noreferrer"
                className="bg-[#ee4d2d] hover:bg-[#d74325] text-white text-xs font-bold py-2.5 rounded-lg flex items-center justify-center gap-2 transition shadow-sm"
              >
                Shopee Search
              </a>
              <a 
                href={`https://www.lazada.com.my/catalog/?q=${encodeURIComponent(db.gpu?.[build.gpu]?.name || "")}`} 
                target="_blank" rel="noreferrer"
                className="bg-[#0f146d] hover:bg-[#0b0f54] text-white text-xs font-bold py-2.5 rounded-lg flex items-center justify-center gap-2 transition shadow-sm"
              >
                Lazada Search
              </a>
            </div>
            <p className="text-[9px] text-slate-400 text-center leading-tight">
              Clicking these links will open a new tab to safely search your selected components from local vendors.
            </p>
          </div>
        </div>
      </section>

      {/* Selection Drawer (Modal for picking parts) */}
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

      {/* Bill of Materials (BOM) Receipt Modal                            */}
      {showBomModal && bomData && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 w-full max-w-2xl rounded-2xl p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-extrabold text-slate-900 text-lg">
                  {bomData.report_title}
                </h3>
                <p className="text-xs text-slate-500">
                  Target: {bomData.workload_target} • Est. Framerate: {bomData.system_telemetry.predicted_fps} FPS
                </p>
              </div>
              <button
                onClick={() => setShowBomModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold text-sm"
              >
                ✕ Close
              </button>
            </div>

            {/* Components Breakdown */}
            <div className="overflow-y-auto flex-grow divide-y divide-slate-100 pr-1">
              {bomData.components.map((item, idx) => (
                <div key={idx} className="py-2.5 flex items-center justify-between gap-4">
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                      {item.category}
                    </span>
                    <span className="font-bold text-slate-800 text-xs">{item.name}</span>
                    <span className="text-[10px] ml-2 text-emerald-600 font-semibold">
                      (Best: {item.best_platform})
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold text-slate-900">
                      RM {item.price_rm.toFixed(2)}
                    </span>
                    <a
                      href={item.shopee_link}
                      target="_blank"
                      rel="noreferrer"
                      className="bg-[#ee4d2d] text-white text-[10px] font-bold px-2 py-1 rounded hover:opacity-90"
                    >
                      Shopee
                    </a>
                    <a
                      href={item.lazada_link}
                      target="_blank"
                      rel="noreferrer"
                      className="bg-[#0f146d] text-white text-[10px] font-bold px-2 py-1 rounded hover:opacity-90"
                    >
                      Lazada
                    </a>
                  </div>
                </div>
              ))}
            </div>

            {/* Total Footer & Print Button */}
            <div className="border-t border-slate-200 pt-3 flex justify-between items-center bg-slate-50 p-4 rounded-xl">
              <div>
                <span className="text-[11px] font-bold text-slate-500 block uppercase">
                  Total Estimated Cost
                </span>
                <span className="text-2xl font-black text-slate-900">
                  RM {bomData.financials.total_cost_rm.toFixed(2)}
                </span>
              </div>
              <button
                onClick={() => window.print()}
                className="bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold px-4 py-2.5 rounded-lg shadow-sm"
              >
                Print / Save PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}