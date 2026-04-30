/**
 * Hand-rolled theme provider — light/dark/system, persisted to localStorage.
 *
 * We intentionally avoid `next-themes`: with Next 15 + React 19 + standalone
 * output it injects an inline script via React that trips the legacy
 * Pages Router prerender for /404 (`<Html>` import error). This module is
 * a small, dependency-free replacement.
 */

import * as React from "react";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "vestrs:theme";

interface ThemeContextValue {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  setPreference: (p: ThemePreference) => void;
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null);

function readSystem(): ResolvedTheme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyClass(theme: ResolvedTheme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

export function ThemeProvider({
  children,
  defaultPreference = "dark",
}: {
  children: React.ReactNode;
  defaultPreference?: ThemePreference;
}) {
  const [preference, setPreferenceState] = React.useState<ThemePreference>(defaultPreference);
  const [resolved, setResolved] = React.useState<ResolvedTheme>("dark");
  const [mounted, setMounted] = React.useState(false);

  // First-paint: read storage + apply class before reflow.
  React.useLayoutEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(STORAGE_KEY) as ThemePreference | null;
    const initial: ThemePreference = stored ?? defaultPreference;
    const resolvedInitial: ResolvedTheme = initial === "system" ? readSystem() : initial;
    setPreferenceState(initial);
    setResolved(resolvedInitial);
    applyClass(resolvedInitial);
    setMounted(true);
  }, [defaultPreference]);

  // Watch system changes when in "system" mode.
  React.useEffect(() => {
    if (!mounted || preference !== "system") return;
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const next: ResolvedTheme = m.matches ? "dark" : "light";
      setResolved(next);
      applyClass(next);
    };
    m.addEventListener("change", handler);
    return () => m.removeEventListener("change", handler);
  }, [preference, mounted]);

  const setPreference = React.useCallback((p: ThemePreference) => {
    window.localStorage.setItem(STORAGE_KEY, p);
    const next: ResolvedTheme = p === "system" ? readSystem() : p;
    setPreferenceState(p);
    setResolved(next);
    applyClass(next);
  }, []);

  const value = React.useMemo(
    () => ({ preference, resolved, setPreference }),
    [preference, resolved, setPreference],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = React.useContext(ThemeContext);
  if (!ctx) {
    // Outside the provider (e.g., during initial server render of the 404
    // fallback) — return a neutral default rather than throwing.
    return {
      preference: "dark",
      resolved: "dark",
      setPreference: () => {},
    };
  }
  return ctx;
}
