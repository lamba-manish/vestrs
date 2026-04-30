import { Route, Routes } from "react-router-dom";

import { Providers } from "@/components/providers";
import { TopNav } from "@/components/top-nav";
import { DashboardPage } from "@/routes/dashboard";
import { LandingPage } from "@/routes/landing";
import { LoginPage } from "@/routes/login";
import { NotFoundPage } from "@/routes/not-found";
import { SignupPage } from "@/routes/signup";

export function App() {
  return (
    <Providers>
      <div className="flex min-h-dvh flex-col">
        <TopNav />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
        <footer className="border-t border-border py-6">
          <div className="container flex flex-col items-start justify-between gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center">
            <span>© 2026 Vestrs · Investments are illustrative only.</span>
            <span>Built for high net-worth investors.</span>
          </div>
        </footer>
      </div>
    </Providers>
  );
}
