import "react";

export default function Catalog({ db }) {
  const categories = Object.keys(db || {});

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h2 className="text-2xl font-extrabold text-slate-900">Hardware Specification Catalog</h2>
        <p className="text-xs text-slate-500">
          Component specifications and official Manufacturer Suggested Retail Prices (MSRP in MYR)
        </p>
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
                    <div>
                      <h4 className="font-bold text-slate-900 text-sm">{item.name}</h4>
                      <span className="text-[10px] text-slate-400 font-medium">Reference Model</span>
                    </div>
                    <div className="text-right">
                      {item.data_status === "LIVE" ? (
                        <>
                          <span className="text-xs font-black text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded block">
                            RM {parseFloat(item.market_price).toFixed(2)}
                          </span>
                          <span className="text-[9px] font-bold text-emerald-600 block mt-0.5">
                            ● Live on {item.platform} ({item.sample_count} samples)
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="text-xs font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded block">
                            RM {parseFloat(item.msrp || item.price).toFixed(2)}
                          </span>
                          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block mt-0.5">
                            MSRP Baseline
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="text-[11px] text-slate-500 space-y-0.5 pt-1 border-t border-slate-100">
                    {item.socket && <p>Socket: <span className="font-semibold text-slate-700">{item.socket}</span></p>}
                    {item.tdp_watts && <p>TDP: <span className="font-semibold text-slate-700">{item.tdp_watts}W</span></p>}
                    {item.base_score && <p>TimeSpy Graphics: <span className="font-semibold text-slate-700">{item.base_score}</span></p>}
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