import { create } from "zustand";
import { persist } from "zustand/middleware";

interface UIState {
  darkMode: boolean;
  logFilter: string | null;
  setDarkMode: (dark: boolean) => void;
  setLogFilter: (filter: string | null) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      darkMode: true,
      logFilter: null,
      setDarkMode: (dark) => set({ darkMode: dark }),
      setLogFilter: (filter) => set({ logFilter: filter }),
    }),
    { name: "xhs-console-ui" }
  )
);
