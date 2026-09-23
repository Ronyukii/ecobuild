import { useState, useMemo } from "react";
import { Link } from "react-router-dom";

export default function Energy({ build, db }) {
  // Usage Habit Sliders
  const [gamingHours, setGamingHours] = useState(3.5);
  const [idleHours, setIdleHours] = useState(4.5);
  // Default to TNB Tier 3 (301 - 600 kWh) as the standard marginal rate for Malaysian urban households
  const [tnbRateTier, setTnbRateTier] = useState(0.516);

  // Hardware specs extraction
  const cpu = db.cpu?.[build.cpu] || {};
  const gpu = db.gpu?.[build.gpu] || {};
  const psu = db.psu?.[build.psu] || {};

  // 1. Calculate Internal Power vs Wall Power (PSU Efficiency Factor)
  // Bronze ~85%, Gold ~90%, Platinum ~92%, White ~80%
  const psuEfficiency = useMemo(() => {
    const eff = (psu.efficiency || "").toLowerCase();
    if (eff.includes("platinum")) return 0.92;
    if (eff.includes("gold")) return 0.90;
    if (eff.includes("bronze")) return 0.85;
    return 0.82;
  }, [psu.efficiency]);

  // Load Draw: CPU TDP + GPU TDP + 50W (Motherboard, RAM, SSD, fans)
  const componentLoadWatts = (cpu.tdp_watts || 65) + (gpu.tdp_watts || 115) + 50;
  const wallLoadWatts = Math.round(componentLoadWatts / psuEfficiency);

  // Idle Draw: Modern systems consume ~45W at idle
  const componentIdleWatts = 45;
  const wallIdleWatts = Math.round(componentIdleWatts / psuEfficiency);

  // 2. Energy Consumption Calculations (kWh)
  const calculations = useMemo(() => {
    // Daily kWh = [(Load_Watts * Gaming_Hours) + (Idle_Watts * Idle_Hours)] / 1000
    const dailyKwh = ((wallLoadWatts * gamingHours) + (wallIdleWatts * idleHours)) / 1000;
    const monthlyKwh = dailyKwh * 30.5;
    const annualKwh = dailyKwh * 365;

    // Monthly & Annual Electricity Cost in MYR
    const monthlyCostRm = monthlyKwh * tnbRateTier;
    const annualCostRm = annualKwh * tnbRateTier;

    // Carbon Footprint: Peninsular Malaysia Grid Factor ≈ 0.758 kg CO2 / kWh (Suruhanjaya Tenaga)
    const annualCo2Kg = annualKwh * 0.758;
    // An average mature tree absorbs ~21.8 kg CO2 per year
    const treesRequired = Math.ceil(annualCo2Kg / 21.8);

    return {
      dailyKwh: dailyKwh.toFixed(2),
      monthlyKwh: monthlyKwh.toFixed(1),
      annualKwh: annualKwh.toFixed(0),
      monthlyCostRm: monthlyCostRm.toFixed(2),
      annualCostRm: annualCostRm.toFixed(2),
      annualCo2Kg: annualCo2Kg.toFixed(1),
      treesRequired,
    };
  }, [wallLoadWatts, wallIdleWatts, gamingHours, idleHours, tnbRateTier]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full uppercase tracking-wider">
            TNB Domestic Tariff A Model
          </span>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 mt-2">
            Energy Consumption & Carbon Telemetry
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Simulates electrical grid draw and operating electricity costs under Tenaga Nasional Berhad residential rates.
          </p>
        </div>
        <Link
          to="/builder"
          className="text-xs font-bold text-slate-700 hover:text-slate-900 bg-white border border-slate-200 px-3.5 py-2 rounded-xl shadow-sm transition"
        >
          ← Back to System Builder
        </Link>
      </div>

      {/* Primary KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
            Estimated Monthly Bill
          </span>
          <div className="text-3xl font-black text-slate-900">
            RM {calculations.monthlyCostRm}
          </div>
          <span className="text-[11px] text-slate-500 block">
            ~RM {calculations.annualCostRm} / year
          </span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
            Monthly Grid Consumption
          </span>
          <div className="text-3xl font-black text-slate-900">
            {calculations.monthlyKwh} <span className="text-sm font-semibold text-slate-400">kWh</span>
          </div>
          <span className="text-[11px] text-slate-500 block">
            {calculations.dailyKwh} kWh per day
          </span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
            Wall Power Draw (Load)
          </span>
          <div className="text-3xl font-black text-emerald-700">
            {wallLoadWatts} <span className="text-sm font-semibold text-slate-400">Watts</span>
          </div>
          <span className="text-[11px] text-slate-500 block">
            Idle: ~{wallIdleWatts}W ({psu.efficiency || "80+"} Efficiency: {Math.round(psuEfficiency * 100)}%)
          </span>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-1">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
            Annual Carbon Footprint
          </span>
          <div className="text-3xl font-black text-slate-900">
            {calculations.annualCo2Kg} <span className="text-sm font-semibold text-slate-400">kg CO₂</span>
          </div>
          <span className="text-[11px] text-emerald-600 font-semibold block">
            🌲 Requires ~{calculations.treesRequired} trees to offset
          </span>
        </div>
      </div>

      {/* Interactive Controls & Hardware Breakdown Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Interactive Usage Habit Sliders */}
        <section className="lg:col-span-6 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-6">
          <div className="border-b border-slate-100 pb-3">
            <h2 className="font-extrabold text-slate-900 text-base">Usage Habit Customization</h2>
            <p className="text-xs text-slate-500">Adjust parameters to reflect your personal routine</p>
          </div>

          {/* Gaming / Heavy Workload Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-bold text-slate-700">
                Gaming / Heavy GPU Load:
              </label>
              <span className="font-extrabold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                {gamingHours} hours / day
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="16"
              step="0.5"
              value={gamingHours}
              onChange={(e) => setGamingHours(parseFloat(e.target.value))}
              className="w-full accent-emerald-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0h (Casual)</span>
              <span>4h (Average Gamer)</span>
              <span>12h+ (Hardcore / Streamer)</span>
            </div>
          </div>

          {/* Idle / Browsing / Workload Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs">
              <label className="font-bold text-slate-700">
                Idle / Video Streaming / Office Work:
              </label>
              <span className="font-extrabold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                {idleHours} hours / day
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="16"
              step="0.5"
              value={idleHours}
              onChange={(e) => setIdleHours(parseFloat(e.target.value))}
              className="w-full accent-slate-800 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0h</span>
              <span>8h (Full Workday)</span>
              <span>16h</span>
            </div>
          </div>

          {/* TNB Tariff Tier Selector */}
          <div className="space-y-2 pt-2 border-t border-slate-100">
            <label className="text-xs font-bold text-slate-700 block">
              Household TNB Baseline Tier (Marginal Rate):
            </label>
            <select
              value={tnbRateTier}
              onChange={(e) => setTnbRateTier(parseFloat(e.target.value))}
              className="w-full bg-slate-50 border border-slate-200 text-xs font-bold rounded-xl p-3 outline-none focus:border-emerald-600"
            >
              <option value={0.516}>Tier 3: 301 - 600 kWh (RM 0.516/kWh - Standard Urban Home)</option>
              <option value={0.218}>Tier 1: 1 - 200 kWh (RM 0.218/kWh - Minimum Lifeline)</option>
              <option value={0.334}>Tier 2: 201 - 300 kWh (RM 0.334/kWh - Low Consumption)</option>
              <option value={0.546}>Tier 4: 601 - 900 kWh (RM 0.546/kWh - High Consumption)</option>
              <option value={0.571}>Tier 5: 901+ kWh (RM 0.571/kWh - Ultra-High / Multi-AC)</option>
            </select>
            <p className="text-[10px] text-slate-400 leading-tight">
              TNB uses a progressive stepped tariff. Because a gaming PC is added on top of an existing household's refrigerator, lights, and air conditioning, the <strong>Tier 3 marginal rate (RM 0.516)</strong> represents the truest cost added to your monthly bill.
            </p>
          </div>
        </section>

        {/* Right Column: Active System Wattage Breakdown */}
        <section className="lg:col-span-6 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="border-b border-slate-100 pb-3">
            <h2 className="font-extrabold text-slate-900 text-base">Active Build Power Consumption</h2>
            <p className="text-xs text-slate-500">Component electrical load distribution</p>
          </div>

          <div className="divide-y divide-slate-100 text-xs">
            <div className="py-2.5 flex justify-between items-center">
              <div>
                <span className="font-bold text-slate-800 block">{cpu.name || "Processor"}</span>
                <span className="text-[10px] text-slate-400">Rated TDP Wattage</span>
              </div>
              <span className="font-extrabold text-slate-900">{cpu.tdp_watts || 65}W</span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <div>
                <span className="font-bold text-slate-800 block">{gpu.name || "Graphics Card"}</span>
                <span className="text-[10px] text-slate-400">Total Board Power (TBP)</span>
              </div>
              <span className="font-extrabold text-slate-900">{gpu.tdp_watts || 115}W</span>
            </div>

            <div className="py-2.5 flex justify-between items-center">
              <div>
                <span className="font-bold text-slate-800 block">Auxiliary Motherboard, RAM & Fans</span>
                <span className="text-[10px] text-slate-400">Chassis lighting, pumps, M.2 SSDs</span>
              </div>
              <span className="font-extrabold text-slate-900">50W</span>
            </div>

            <div className="py-2.5 flex justify-between items-center bg-slate-50 px-2 rounded-lg">
              <div>
                <span className="font-bold text-slate-800 block">Power Supply Efficiency Curve</span>
                <span className="text-[10px] text-slate-400">{psu.name || "PSU"} ({psu.efficiency || "80+"})</span>
              </div>
              <span className="font-extrabold text-emerald-700">~{Math.round(psuEfficiency * 100)}% Conversion</span>
            </div>
          </div>

          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 text-xs space-y-1">
            <span className="font-bold block">💡 Energy Efficiency Tip:</span>
            <p className="text-[11px] leading-relaxed">
              Upgrading from an 80+ Bronze (~85%) to an 80+ Gold (~90%) power supply saves approximately <strong>~{Math.round(componentLoadWatts * 0.05)}W</strong> from being wasted as pure heat inside your room, reducing both electricity bills and room ambient temperatures!
            </p>
          </div>
        </section>
      </div>

      {/* Comprehensive Educational & Academic Reference Section */}
      <section className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-sm space-y-6">
        <div>
          <h2 className="text-xl font-black text-slate-900">
            Mathematical Methodology & Malaysian Grid Physics
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Reference framework for academic defense, thesis Chapter 3/4 citations, and consumer transparency.
          </p>
        </div>

        {/* TNB Tariff Table */}
        <div className="space-y-2">
          <h3 className="font-bold text-slate-800 text-xs uppercase tracking-wider">
            Official Tenaga Nasional Berhad (TNB) Tariff A – Domestic
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border border-slate-200 rounded-xl overflow-hidden">
              <thead className="bg-slate-50 text-slate-600 font-bold border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-3">Tariff Block</th>
                  <th className="py-2.5 px-3">Consumption Range (kWh)</th>
                  <th className="py-2.5 px-3">Rate (sen / kWh)</th>
                  <th className="py-2.5 px-3">Rate (MYR / kWh)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                <tr>
                  <td className="py-2 px-3 font-semibold">Block 1</td>
                  <td className="py-2 px-3">First 200 kWh (1 - 200 kWh)</td>
                  <td className="py-2 px-3">21.80 sen</td>
                  <td className="py-2 px-3 font-bold text-slate-900">RM 0.218</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-semibold">Block 2</td>
                  <td className="py-2 px-3">Next 100 kWh (201 - 300 kWh)</td>
                  <td className="py-2 px-3">33.40 sen</td>
                  <td className="py-2 px-3 font-bold text-slate-900">RM 0.334</td>
                </tr>
                <tr className="bg-emerald-50/50">
                  <td className="py-2 px-3 font-bold text-emerald-800">Block 3 (Standard)</td>
                  <td className="py-2 px-3 text-emerald-800">Next 300 kWh (301 - 600 kWh)</td>
                  <td className="py-2 px-3 text-emerald-800">51.60 sen</td>
                  <td className="py-2 px-3 font-extrabold text-emerald-700">RM 0.516</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-semibold">Block 4</td>
                  <td className="py-2 px-3">Next 300 kWh (601 - 900 kWh)</td>
                  <td className="py-2 px-3">54.60 sen</td>
                  <td className="py-2 px-3 font-bold text-slate-900">RM 0.546</td>
                </tr>
                <tr>
                  <td className="py-2 px-3 font-semibold">Block 5</td>
                  <td className="py-2 px-3">Above 900 kWh (&gt;900 kWh)</td>
                  <td className="py-2 px-3">57.10 sen</td>
                  <td className="py-2 px-3 font-bold text-slate-900">RM 0.571</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Formulas Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs space-y-2">
            <h4 className="font-bold text-slate-900">Formula: Monthly Electrical Duty Cycle</h4>
            <div className="bg-white p-2.5 rounded border border-slate-200 font-mono text-[11px] text-slate-700">
              kWh_monthly = [ (P_wall_load × t_game) + (P_wall_idle × t_idle) ] / 1000 × 30.5
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Where <code>P_wall_load</code> accounts for PSU conversion loss, <code>t_game</code> is daily high-performance load hours, and <code>30.5</code> represents the average days per Gregorian calendar month.
            </p>
          </div>

          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs space-y-2">
            <h4 className="font-bold text-slate-900">Formula: Malaysian Carbon Emission Factor</h4>
            <div className="bg-white p-2.5 rounded border border-slate-200 font-mono text-[11px] text-slate-700">
              CO₂_annual = kWh_annual × 0.758 kg CO₂ / kWh
            </div>
            <p className="text-[11px] text-slate-500 leading-relaxed">
              Derived from the Energy Commission of Malaysia (Suruhanjaya Tenaga) Grid Emission Factor report for the Peninsular Malaysia interconnected electrical transmission network.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}