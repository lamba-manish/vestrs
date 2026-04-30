import { type ComponentType, lazy, Suspense } from "react";
import { Route, Routes, useLocation } from "react-router-dom";

import { Providers } from "@/components/providers";
import { RouteTransitions } from "@/components/route-transitions";
import { TopNav } from "@/components/top-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { LandingPage } from "@/routes/landing";
import { LoginPage } from "@/routes/login";
import { NotFoundPage } from "@/routes/not-found";
import { SignupPage } from "@/routes/signup";

// Auth-gated routes are split out of the entry bundle so the cold
// landing-page paint doesn't pay for code only authenticated users
// hit. The pages export named functions; React.lazy() expects a
// default export, so we wrap each import with a tiny adapter.
const lazyNamed = <K extends string>(loader: () => Promise<Record<K, ComponentType>>, key: K) =>
  lazy(() => loader().then((m) => ({ default: m[key] })));

const DashboardPage = lazyNamed(() => import("@/routes/dashboard"), "DashboardPage");
const ProfilePage = lazyNamed(() => import("@/routes/onboarding/profile"), "ProfilePage");
const KycPage = lazyNamed(() => import("@/routes/onboarding/kyc"), "KycPage");
const AccreditationPage = lazyNamed(
  () => import("@/routes/onboarding/accreditation"),
  "AccreditationPage",
);
const BankPage = lazyNamed(() => import("@/routes/onboarding/bank"), "BankPage");
const InvestPage = lazyNamed(() => import("@/routes/onboarding/invest"), "InvestPage");
const AuditPage = lazyNamed(() => import("@/routes/audit"), "AuditPage");

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

function RouteFallback() {
  return (
    <div className="container max-w-2xl py-10 sm:py-12">
      <Skeleton className="mb-4 h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <RouteTransitions>
      <Suspense fallback={<RouteFallback />}>
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
      </Suspense>
    </RouteTransitions>
  );
}
