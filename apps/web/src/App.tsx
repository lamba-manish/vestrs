import { Route, Routes, useLocation } from "react-router-dom";

import { Providers } from "@/components/providers";
import { RouteTransitions } from "@/components/route-transitions";
import { TopNav } from "@/components/top-nav";
import { AuditPage } from "@/routes/audit";
import { DashboardPage } from "@/routes/dashboard";
import { LandingPage } from "@/routes/landing";
import { LoginPage } from "@/routes/login";
import { NotFoundPage } from "@/routes/not-found";
import { AccreditationPage } from "@/routes/onboarding/accreditation";
import { BankPage } from "@/routes/onboarding/bank";
import { InvestPage } from "@/routes/onboarding/invest";
import { KycPage } from "@/routes/onboarding/kyc";
import { ProfilePage } from "@/routes/onboarding/profile";
import { SignupPage } from "@/routes/signup";

export function App() {
  return (
    <Providers>
      <div className="flex min-h-dvh flex-col">
        <TopNav />
        <main className="flex-1">
          <AnimatedRoutes />
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

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <RouteTransitions>
      <Routes location={location}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/onboarding/profile" element={<ProfilePage />} />
        <Route path="/onboarding/kyc" element={<KycPage />} />
        <Route path="/onboarding/accreditation" element={<AccreditationPage />} />
        <Route path="/onboarding/bank" element={<BankPage />} />
        <Route path="/onboarding/invest" element={<InvestPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </RouteTransitions>
  );
}
