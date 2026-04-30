import { Circle } from "lucide-react";
import { useEffect } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/lib/auth";

const STEPS = [
  { id: "profile", label: "Complete your profile" },
  { id: "kyc", label: "Verify your identity (KYC)" },
  { id: "accreditation", label: "Accreditation review" },
  { id: "bank", label: "Link a bank account" },
  { id: "invest", label: "Place your first investment" },
] as const;

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
  return (
    <div className="container py-12">
      <header className="mb-10 max-w-2xl">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Onboarding</p>
        <h1 className="mt-2 font-serif-display text-4xl tracking-tight">
          Welcome{me.data ? `, ${me.data.email.split("@")[0]}` : ""}.
        </h1>
        <p className="mt-3 text-base leading-7 text-muted-foreground">
          Your onboarding is a short, paced sequence. Each step is reviewable and reversible up to
          the point of investment.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Your next steps</CardTitle>
          <CardDescription>
            Slice 12 wires the actual flow screens — for now this is the shell.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="divide-y divide-border">
            {STEPS.map((step) => (
              <li key={step.id} className="flex items-center justify-between gap-4 py-4">
                <div className="flex items-center gap-3">
                  <Circle aria-hidden="true" className="size-5 text-muted-foreground" />
                  <span className="text-sm">{step.label}</span>
                </div>
                <Button size="sm" variant="outline" disabled>
                  Coming next
                </Button>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
