// Single source of truth for values the backend actually supports.
// Keep this in sync with backend/app/real_engine.py — GAME_REFERENCE and
// RESOLUTION_SCALE are the authoritative lists; this file just mirrors them
// for the UI so the two never drift apart again.

// Mirrors GAME_REFERENCE keys in real_engine.py
export const GAMES = ["Cyberpunk 2077", "CS2", "Valorant", "Elden Ring"];

// Mirrors RESOLUTION_SCALE keys in real_engine.py
export const RESOLUTIONS = [
  { value: "1080p", label: "1080p (FHD)" },
  { value: "1440p", label: "1440p (QHD)" },
  { value: "4K", label: "4K (UHD)" },
];

// Cheapest possible build using the seeded catalog in main.py's /seed route:
// i3-12100F (380) + H610M-K (320) + RTX 3050 (1050) + Stock Cooler (30)
// + InWin 301 Glass MATX (150) + Kingston Fury 16GB DDR4 (180)
// + Kingston NV2 500GB (150) + Corsair CV550 550W (220) = RM 2,480.
// Anything below this will always 404 from /optimize — the UI should not
// let the user set a budget the backend can never satisfy.
export const MIN_VIABLE_BUDGET = 2500;