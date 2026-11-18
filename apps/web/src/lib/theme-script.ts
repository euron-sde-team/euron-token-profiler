/**
 * Runs before first paint (inlined in the root layout), so the page never flashes. The stored
 * choice is "light", "dark" or "system"; nothing stored means system.
 */
export const STORAGE_KEY = "tokenprofiler-theme";

export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${STORAGE_KEY}");var d=t==="dark"||(t!=="light"&&matchMedia("(prefers-color-scheme: dark)").matches);if(d){document.documentElement.classList.add("dark")}}catch(e){}})();`;
