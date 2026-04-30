import { Lock, ScrollText, ShieldCheck } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

const POINTS = [
  {
    icon: ShieldCheck,
    title: "KYC & accreditation built-in",
    body: "Identity, liveness, and accredited-investor verification through audited providers.",
  },
  {
    icon: Lock,
    title: "Masked-only banking",
    body: "We store last-4, bank name, and currency. Plaintext credentials never touch our database.",
  },
  {
    icon: ScrollText,
    title: "Audit trail for counsel",
    body: "Every action — auth, retries, links, investments — recorded immutably with a request ID.",
  },
];

export function AuthSideInfo() {
  return (
    <Card className="hidden h-full bg-card/40 md:block">
      <CardContent className="flex h-full flex-col justify-center gap-6 p-8">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            Why Vestrs
          </p>
          <h2 className="mt-2 font-serif-display text-2xl tracking-tight">
            A short, accountable onboarding.
          </h2>
        </div>
        <ul className="space-y-5">
          {POINTS.map(({ icon: Icon, title, body }) => (
            <li key={title} className="flex items-start gap-3">
              <span className="mt-1 inline-flex size-7 items-center justify-center rounded-full border border-border text-primary">
                <Icon className="size-3.5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-medium">{title}</p>
                <p className="text-xs leading-5 text-muted-foreground">{body}</p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
