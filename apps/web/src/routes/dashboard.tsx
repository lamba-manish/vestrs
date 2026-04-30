import { useEffect } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { deriveOnboardingState, nextActionLabel } from "@/components/onboarding/onboarding-state";
import { StepRow } from "@/components/onboarding/step-row";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccreditationSummary } from "@/lib/accreditation";
import { useMe } from "@/lib/auth";
import { useBankSummary } from "@/lib/bank";
import { useInvestments } from "@/lib/investments";
import { useKycSummary } from "@/lib/kyc";
import { useProfile } from "@/lib/profile";

export function DashboardPage() {
  useEffect(() => {
    document.title = "Dashboard · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <DashboardContent />
    </AuthGuard>
  );
}

function DashboardContent() {
  const me = useMe();
  const profile = useProfile();
  const kyc = useKycSummary();
  const acc = useAccreditationSummary();
  const bank = useBankSummary();
  const investments = useInvestments();

  const state = deriveOnboardingState({
    profile: profile.data ?? undefined,
    kycStatus: kyc.data?.status,
    accreditationStatus: acc.data?.status,
    bankLinked: bank.data?.linked ?? false,
    hasInvestment: (investments.data?.total ?? 0) > 0,
  });

  const profileDone = state.profile === "success";
  const kycDone = state.kyc === "success";
  const accDone = state.accreditation === "success";
  const bankDone = state.bank === "success";

  const loading =
    profile.isLoading || kyc.isLoading || acc.isLoading || bank.isLoading || investments.isLoading;

  return (
    <div className="container py-10 sm:py-12">
      <header className="mb-8 max-w-2xl">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Onboarding</p>
        <h1 className="mt-2 font-serif-display text-3xl tracking-tight sm:text-4xl">
          Welcome{me.data ? `, ${me.data.email.split("@")[0]}` : ""}.
        </h1>
        <p className="mt-3 text-sm leading-7 text-muted-foreground sm:text-base">
          A short, paced sequence. Each step writes an audit entry; the entire flow is reviewable in
          your audit log.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Your steps</CardTitle>
          <CardDescription>
            Complete each in order. Steps unlock as the previous one finishes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : (
            <ol className="divide-y divide-border">
              <StepRow
                index={1}
                title="Complete your profile"
                description="Name, nationality, country of residence, contact phone."
                status={state.profile}
                to="/onboarding/profile"
                enabled
                actionLabel={nextActionLabel(state.profile)}
              />
              <StepRow
                index={2}
                title="Verify your identity (KYC)"
                description="Identity, liveness, and AML screening through our verification provider."
                status={state.kyc}
                to="/onboarding/kyc"
                enabled={profileDone}
                actionLabel={nextActionLabel(state.kyc)}
              />
              <StepRow
                index={3}
                title="Accreditation review"
                description="Asynchronous review against accredited-investor criteria."
                status={state.accreditation}
                to="/onboarding/accreditation"
                enabled={kycDone}
                actionLabel={nextActionLabel(state.accreditation)}
              />
              <StepRow
                index={4}
                title="Link a bank account"
                description="We persist masked details only — last four, currency, balance estimate."
                status={state.bank}
                to="/onboarding/bank"
                enabled={accDone}
                actionLabel={nextActionLabel(state.bank)}
              />
              <StepRow
                index={5}
                title="Place your first investment"
                description="Funds routed to a regulated escrow / law-firm pooling account."
                status={state.invest}
                to="/onboarding/invest"
                enabled={bankDone}
                actionLabel={nextActionLabel(state.invest)}
              />
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
