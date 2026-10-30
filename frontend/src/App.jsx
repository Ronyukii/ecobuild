import { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

// Layout Components
import Navigation from "./components/Navigation";
import Footer from "./components/Footer";
import FeedbackModal from "./components/FeedbackModal";

// Page Views
import Home from "./pages/Home";
import Builder from "./pages/Builder";
import Optimize from "./pages/Optimize";
import Catalog from "./pages/Catalog";
import Diagnostics from "./pages/Diagnostics";
import AnnouncementBar from "./components/AnnouncementBar";
import Energy from "./pages/Energy";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function App() {
  const urlParams = new URLSearchParams(window.location.search);
  // Global Shared States (Using updated catalog IDs)
  const [dbComponents, setDbComponents] = useState({});
  const [currentBuild, setCurrentBuild] = useState({
    cpu: urlParams.get("cpu") || "i5_12400F",
    mobo: urlParams.get("mobo") || "b660m_ds3h",
    gpu: urlParams.get("gpu") || "rtx_4060_twin",
    cooler: urlParams.get("cooler") || "air_ag400",
    case: urlParams.get("case") || "atx_mesh",
    ram: urlParams.get("ram") || "ddr4_16gb",
    psu: urlParams.get("psu") || "psu_550w",
    storage: urlParams.get("storage") || "ssd_500gb"
  });
  const [simulationResult, setSimulationResult] = useState(null);
  const [targetGame, setTargetGame] = useState(urlParams.get("game") || "Cyberpunk 2077");
  const [targetResolution, setTargetResolution] = useState(urlParams.get("res") || "1080p");
  const [ambientTemp, setAmbientTemp] = useState(Number(urlParams.get("temp")) || 30.0);
  const [isDbLoaded, setIsDbLoaded] = useState(false);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);

  // --- FETCH CATALOG FROM RENDER BACKEND ---
  useEffect(() => {
    const fetchSpecs = async () => {
      try {
        const endpoints = {
          cpu: "/cpus",
          mobo: "/motherboards",
          gpu: "/gpus",
          cooler: "/coolers",
          case: "/cases",
          ram: "/rams",
          storage: "/storages",
          psu: "/psus"
        };

        let tempDb = {};
        for (let type in endpoints) {
          const res = await fetch(`${BACKEND_URL}${endpoints[type]}`);
          const data = await res.json();
          
          tempDb[type] = {};
          data.forEach(item => {
            const idKey = item[`${type}_id`] || item["mobo_id"] || item["cooler_id"] || item["case_id"] || item["ram_id"] || item["storage_id"] || item["psu_id"];
            tempDb[type][idKey] = item;
          });
        }
        setDbComponents(tempDb);
        setIsDbLoaded(true);
      } catch (err) {
        console.error("Failed to connect to backend:", err);
      }
    };
    fetchSpecs();

    // Silent analytics ping
    fetch(`${BACKEND_URL}/analytics/visit`, { method: "POST" }).catch(() => {});
  }, []);

  // --- TRIGGER SIMULATION ENGINE ---
  useEffect(() => {
    if (!isDbLoaded) return;

    const runSimulation = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/simulate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            cpu_id: currentBuild.cpu,
            mobo_id: currentBuild.mobo,
            gpu_id: currentBuild.gpu,
            cooler_id: currentBuild.cooler,
            case_id: currentBuild.case,
            ram_id: currentBuild.ram,
            psu_id: currentBuild.psu,
            storage_id: currentBuild.storage,
            game_name: targetGame,
            resolution: targetResolution,
            ambient_temp: ambientTemp
          })
        });
        if (response.ok) {
          const data = await response.json();
          setSimulationResult(data);
        }
      } catch (err) {
        console.error("Simulation request failed:", err);
      }
    };

    runSimulation();
  }, [currentBuild, targetGame, targetResolution, ambientTemp, isDbLoaded]);

  if (!isDbLoaded) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-slate-200 border-t-emerald-600 rounded-full animate-spin"></div>
        <h2 className="text-slate-600 font-bold tracking-widest text-sm uppercase animate-pulse">
          Initializing EcoBuild Cloud Engine...
        </h2>
        <h3 className="text-slate-400 text-xs tracking-wide text-center max-w-xs">
          This may take a few seconds. If it takes longer than 40 seconds, please check your internet connection or try refreshing the page.
        </h3>
      </div>
    );
  }

  return (
    <Router>
      <div className="bg-slate-50 text-slate-800 min-h-screen flex flex-col justify-between selection:bg-emerald-100 selection:text-emerald-900">
        {/* Top Status & Schedule Banner */}
        <AnnouncementBar />
        <Navigation currentBuild={currentBuild} result={simulationResult} />
        
        <div className="flex-grow">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route 
              path="/builder" 
              element={
                <Builder 
                  db={dbComponents} 
                  build={currentBuild} 
                  setBuild={setCurrentBuild} 
                  result={simulationResult}
                  game={targetGame}
                  setGame={setTargetGame}
                  res={targetResolution}
                  setRes={setTargetResolution}
                  ambientTemp={ambientTemp}
                  setAmbientTemp={setAmbientTemp}
                  backendUrl={BACKEND_URL}
                />
              } 
            />
            <Route 
              path="/optimize" 
              element={
                <Optimize 
                  setBuild={setCurrentBuild} 
                  setGame={setTargetGame}
                  setRes={setTargetResolution}
                  backendUrl={BACKEND_URL}   // Pass backend URL to Optimizer
                />
              } 
            />
            <Route path="/catalog" element={<Catalog db={dbComponents} />} />
            <Route 
              path="/diagnostics" 
              element={
                <Diagnostics 
                  build={currentBuild} 
                  db={dbComponents} 
                  result={simulationResult} 
                  ambientTemp={ambientTemp}
                />
              } 
            />
            <Route 
              path="/energy" 
              element={
                <Energy 
                  build={currentBuild} 
                  db={dbComponents} 
                  result={simulationResult} 
                />
              } 
            />
          </Routes>
        </div>

        {/* Floating Feedback Trigger */}
        <button
          onClick={() => setIsFeedbackOpen(true)}
          className="fixed bottom-5 right-5 z-40 bg-slate-900/90 hover:bg-slate-900 text-white text-xs font-semibold px-3.5 py-2 rounded-full shadow-lg backdrop-blur-md border border-slate-700/60 flex items-center gap-2 transition-all hover:scale-105"
        >
          <span className="text-sm">💬</span>
          <span>Feedback / Report</span>
        </button>

        <FeedbackModal
          isOpen={isFeedbackOpen}
          onClose={() => setIsFeedbackOpen(false)}
          currentBuild={currentBuild}
          backendUrl={BACKEND_URL}
        />

        <Footer />
      </div>
    </Router>
  );
}

export default App;