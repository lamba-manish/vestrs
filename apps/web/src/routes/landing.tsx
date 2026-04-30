import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const PILLARS = [
  {
    title: "KYC & accreditation, handled.",
    body: "Identity, liveness, and accredited-investor verification through best-in-class providers — never on a spreadsheet.",
  },
  {
    title: "Bank linking with restraint.",
    body: "We store the masked details, route capital through a regulated escrow, and audit every state change.",
  },
  {
    title: "An audit trail you'd show counsel.",
    body: "Every signup, retry, refresh, link, and investment is recorded with a request ID, timestamp, and immutable status.",
  },
];

export function LandingPage() {
  return (
    <div className="container">
      <section className="relative overflow-hidden py-20 sm:py-28">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-secondary/40 px-3 py-1 text-xs uppercase tracking-[0.18em] text-muted-foreground">
            <ShieldCheck className="size-3" />
            Private placement onboarding
          </p>
          <h1 className="font-serif-display text-4xl leading-tight tracking-tight sm:text-6xl">
            Capital onboarding for <span className="text-primary">discerning investors.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
            Sign up, complete KYC and accreditation, link a bank, and place an investment — all in
            one quiet, accountable flow.
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link to="/signup">
                Open an account
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link to="/login">Sign in</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 pb-20 sm:grid-cols-3">
        {PILLARS.map((p) => (
          <Card key={p.title}>
            <CardContent className="space-y-2 p-6">
              <h3 className="font-serif-display text-xl tracking-tight">{p.title}</h3>
              <p className="text-sm leading-6 text-muted-foreground">{p.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>
    </div>
  );
}
