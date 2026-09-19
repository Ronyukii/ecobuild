import "react";
import { Link, useLocation } from "react-router-dom";

export default function Navigation({ result }) {
  const location = useLocation();

  const navLinks = [
    { name: "Overview", path: "/" },
    { name: "System Builder", path: "/builder" },
    { name: "Auto-Optimizer", path: "/optimize" },
    { name: "Hardware Catalog", path: "/catalog" },
    { name: "Diagnostics", path: "/diagnostics" },
  ];

  return (
    <header className="border-b border-slate-200 bg-white/95 backdrop-blur sticky top-0 z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3">
          <div className="bg-emerald-600 text-white w-9 h-9 rounded-xl flex items-center justify-center font-black text-lg shadow-sm">
            EB
          </div>
          <div>
            <h1 className="font-extrabold text-slate-900 leading-none tracking-tight">EcoBuild</h1>
            <span className="text-[11px] text-slate-500 font-medium">Predictive PC Architecture</span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200">
          {navLinks.map((link) => {
            const isActive = location.pathname === link.path;
            return (
              <Link
                key={link.path}
                to={link.path}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                  isActive
                    ? "bg-white text-emerald-700 shadow-sm border border-slate-200/60"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {link.name}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          {result && (
            <div className="hidden sm:flex items-baseline gap-1.5 bg-slate-100 border border-slate-200 px-3 py-1 rounded-lg">
              <span className="text-xs text-slate-500 font-semibold">Total:</span>
              <span className="text-sm font-extrabold text-slate-900">
                RM {result.total_price_rm?.toFixed(2) || "0.00"}
              </span>
            </div>
          )}
          <div className="flex items-center gap-2 text-[11px] text-slate-600 border border-slate-200 px-3 py-1.5 rounded-full bg-slate-50">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-bold text-emerald-700">API CONNECTED</span>
          </div>
        </div>
      </div>
    </header>
  );
}