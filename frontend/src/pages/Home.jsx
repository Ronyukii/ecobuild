import "react";
import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="max-w-7xl mx-auto px-4 py-16 space-y-16">
      <section className="text-center max-w-3xl mx-auto space-y-6">
        <span className="inline-block px-3.5 py-1 text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full">
          Pre-Purchase Decision Support System
        </span>
        <h2 className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight leading-tight">
          Simulate PC Performance & Thermals <br />
          <span className="text-emerald-600">Before You Spend a Ringgit.</span>
        </h2>
        <p className="text-slate-600 text-sm sm:text-base leading-relaxed">
          EcoBuild eliminates custom PC guesswork. We combine real-time Malaysian market scraping 
          (Shopee & Lazada) with predictive FPS heuristics and thermal equilibrium modeling to 
          ensure maximum performance-per-Ringgit without overheating.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
          <Link
            to="/builder"
            className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-md transition"
          >
            Open System Builder →
          </Link>
          <Link
            to="/optimize"
            className="px-6 py-3 bg-white hover:bg-slate-50 text-slate-800 border border-slate-200 font-bold text-sm rounded-xl shadow-sm transition"
          >
            Auto-Optimize by Budget
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="text-2xl">⚡</div>
          <h3 className="font-bold text-slate-900 text-base">Heuristic FPS Prediction</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Calculates CPU-GPU synergy and resolution modifiers to estimate in-game frame rates before purchase.
          </p>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="text-2xl">🌡️</div>
          <h3 className="font-bold text-slate-900 text-base">TDP Thermal Balancing</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Estimates operating temperature under tropical Malaysian ambient conditions (30°C) to alert against throttling.
          </p>
        </div>
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-3">
          <div className="text-2xl">🎯</div>
          <h3 className="font-bold text-slate-900 text-base">0-1 Knapsack Optimization</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Input your budget ceiling and let the algorithm synthesize the highest-performing compatible parts list.
          </p>
        </div>
      </section>
    </div>
  );
}