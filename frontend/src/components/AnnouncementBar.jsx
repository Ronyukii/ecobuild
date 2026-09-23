import { useState } from "react";

export default function AnnouncementBar() {
  const [isVisible, setIsVisible] = useState(() => {
    return sessionStorage.getItem("ecobuild_announcement_closed") !== "true";
  });

  if (!isVisible) return null;

  const handleDismiss = () => {
    setIsVisible(false);
    sessionStorage.setItem("ecobuild_announcement_closed", "true");
  };

  return (
    <div className="bg-slate-900 text-slate-200 border-b border-slate-800 text-[11px] py-2 px-4 relative z-50">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 pr-6 text-center sm:text-left">
        <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
          <span className="inline-flex items-center gap-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-bold text-[10px]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            LIVE SYSTEM
          </span>
          <span>
            <strong>Active High-Speed Hours:</strong> 08:00 – 23:30 MYT (GMT+8) • Off-peak visits (00:00 – 07:59) may experience a ~30s cloud warm-up.
          </span>
        </div>

        <div className="flex items-center gap-3 text-slate-400 text-[10px]">
          <span>🔄 <strong>Daily Price Sync:</strong> 02:00 AM MYT (Shopee & Lazada)</span>
        </div>
      </div>

      <button
        onClick={handleDismiss}
        title="Dismiss announcement"
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs font-bold px-1.5 py-0.5 rounded transition"
      >
        ✕
      </button>
    </div>
  );
}