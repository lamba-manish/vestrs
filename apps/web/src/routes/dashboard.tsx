import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { AuthGuard } from "@/components/auth/auth-guard";
import { deriveOnboardingState, nextActionLabel } from "@/components/onboarding/onboarding-state";
import { StepRow } from "@/components/onboarding/step-row";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AuditRow } from "@/routes/audit";
import { useAccreditationSummary } from "@/lib/accreditation";
import { useAuditFeed } from "@/lib/audit";
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

  const audit = useAuditFeed();
  const recent = audit.data?.pages[0]?.items.slice(0, 5) ?? [];

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

      {/*
        Desktop layout (slice 31): two columns above lg — steps on the
        left at 7/12, recent activity on the right at 5/12. Mobile and
        tablet stay stacked. Items-start so the sidebar doesn't stretch
        when the steps card is taller.
      */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
        <Card className="lg:col-span-7">
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

        <Card className="lg:col-span-5 lg:sticky lg:top-6">
          <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
            <div>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>Last few audit entries from your onboarding flow.</CardDescription>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link to="/audit">
                Full log
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {audit.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : recent.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">No activity yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {recent.map((entry) => (
                  <AuditRow key={entry.id} entry={entry} />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
