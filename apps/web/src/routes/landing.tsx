import { ArrowRight, LayoutDashboard, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useMe } from "@/lib/auth";

const PILLARS = [
  {
    title: "KYC & accreditation, handled.",
    body: "Identity, liveness, and accredited-investor verification through best-in-class providers.",
  },
  {
    title: "Bank linking with restraint.",
    body: "Masked details only. Capital routed through a regulated escrow with every state change audited.",
  },
  {
    title: "Audit trail for counsel.",
    body: "Every signup, retry, refresh, link, and investment recorded — immutable.",
  },
];

export function LandingPage() {
  const me = useMe();
  const authed = !me.isLoading && me.data;

  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] flex-col justify-center gap-8 py-6 sm:py-10">
      <section className="mx-auto max-w-3xl text-center">
        <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-secondary/40 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          <ShieldCheck className="size-3" />
          Private placement onboarding
        </p>
        <h1 className="font-serif-display text-3xl leading-tight tracking-tight sm:text-5xl">
          {authed ? (
            <>
              Welcome back, <span className="text-primary">{me.data!.email.split("@")[0]}.</span>
            </>
          ) : (
            <>
              Capital onboarding for <span className="text-primary">discerning investors.</span>
            </>
          )}
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground sm:text-base sm:leading-7">
          {authed
            ? "Pick up where you left off. Each step writes an audit entry; the entire flow is reviewable in your audit log."
            : "Sign up, complete KYC and accreditation, link a bank, and place an investment — all in one quiet, accountable flow."}
        </p>
        <div className="mt-5 flex flex-col items-center justify-center gap-3 sm:flex-row">
          {authed ? (
            <Button asChild size="lg">
              <Link to="/dashboard">
                <LayoutDashboard className="size-4" />
                Continue to dashboard
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          ) : (
            <>
              <Button asChild size="lg">
                <Link to="/signup">
                  Open an account
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link to="/login">Sign in</Link>
              </Button>
            </>
          )}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {PILLARS.map((p) => (
          <Card key={p.title}>
            <CardContent className="space-y-1.5 p-5">
              <h3 className="font-serif-display text-lg tracking-tight">{p.title}</h3>
              <p className="text-sm leading-6 text-muted-foreground">{p.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
