import { useState, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

// Layout Components
import Navigation from "./components/Navigation";
import Footer from "./components/Footer";

// Page Views
import Home from "./pages/Home";
import Builder from "./pages/Builder";
import Optimize from "./pages/Optimize";
import Catalog from "./pages/Catalog";
import Diagnostics from "./pages/Diagnostics";

const BACKEND_URL = "http://localhost:8000";

function App() {
  // Global Shared States (Ensures data persists as the user navigates pages)
  const [dbComponents, setDbComponents] = useState({});
  const [currentBuild, setCurrentBuild] = useState({
    cpu: "i5_12400F",
    mobo: "b660m",
    gpu: "rtx_4060",
    cooler: "air_ag400",
    case: "atx_mesh",
    ram: "ddr4_16gb",
    psu: "psu_550w",
    storage: "ssd_500gb"
  });
  const [simulationResult, setSimulationResult] = useState(null);
  const [targetGame, setTargetGame] = useState("Cyberpunk 2077");
  const [targetResolution, setTargetResolution] = useState("1080p");
  const [isDbLoaded, setIsDbLoaded] = useState(false);

  // --- FETCH REPOSITORY DATA FROM POSTGRESQL ON LOAD ---
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
        console.error("Failed to connect to FastAPI PostgreSQL container:", err);
      }
    };
    fetchSpecs();
  }, []);

  // --- TRIGGER BACKEND SIMULATE ENDPOINT ---
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
            resolution: targetResolution
          })
        });
        const data = await response.json();
        setSimulationResult(data);
      } catch (err) {
        console.error("Simulation request failed:", err);
      }
    };

    runSimulation();
  }, [currentBuild, targetGame, targetResolution, isDbLoaded]);

  if (!isDbLoaded) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 border-4 border-slate-200 border-t-emerald-600 rounded-full animate-spin"></div>
        <h2 className="text-slate-600 font-bold tracking-widest text-sm uppercase animate-pulse">
          Initializing EcoBuild Engine...
        </h2>
      </div>
    );
  }

  return (
    <Router>
      <div className="bg-slate-50 text-slate-800 min-h-screen flex flex-col justify-between selection:bg-emerald-100 selection:text-emerald-900">
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
                />
              } 
            />
          </Routes>
        </div>

        <Footer />
      </div>
    </Router>
  );
}

export default App;