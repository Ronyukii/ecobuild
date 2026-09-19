import "react";

export default function Catalog({ db }) {
  const categories = Object.keys(db || {});

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h2 className="text-2xl font-extrabold text-slate-900">Hardware Specification Catalog</h2>
        <p className="text-xs text-slate-500">Live PostgreSQL registry and scraped pricing</p>
      </div>

      {categories.map((catKey) => {
        const items = Object.values(db[catKey] || {});
        return (
          <div key={catKey} className="space-y-3">
            <h3 className="font-bold text-sm text-slate-700 uppercase tracking-wider">
              {catKey.toUpperCase()} Registry ({items.length} models)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {items.map((item, idx) => (
                <div key={idx} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-2">
                  <div className="flex justify-between items-start">
                    <h4 className="font-bold text-slate-900 text-sm">{item.name}</h4>
                    <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                      RM {parseFloat(item.price || 0).toFixed(2)}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 space-y-0.5">
                    {item.socket && <p>Socket: <span className="font-semibold text-slate-700">{item.socket}</span></p>}
                    {item.tdp_watts && <p>TDP: <span className="font-semibold text-slate-700">{item.tdp_watts}W</span></p>}
                    {item.base_score && <p>Benchmark: <span className="font-semibold text-slate-700">{item.base_score}</span></p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}