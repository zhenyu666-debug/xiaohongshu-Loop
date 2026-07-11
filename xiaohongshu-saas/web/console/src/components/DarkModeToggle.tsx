import { useUIStore } from "@/hooks/useUIStore";

export function DarkModeToggle() {
  const { darkMode, setDarkMode } = useUIStore();

  return (
    <button
      onClick={() => setDarkMode(!darkMode)}
      className={`p-2 rounded-lg transition-colors ${
        darkMode
          ? "bg-slate-800 text-yellow-400 hover:bg-slate-700"
          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
      }`}
      title={darkMode ? "切换到亮色模式" : "切换到暗色模式"}
    >
      {darkMode ? (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ) : (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
    </button>
  );
}
