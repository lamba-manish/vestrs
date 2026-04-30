import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusPill, type StepStatus } from "@/components/onboarding/status-pill";
import { Button } from "@/components/ui/button";

export interface StepRowProps {
  index: number;
  title: string;
  description: string;
  status: StepStatus;
  to: string;
  enabled: boolean;
  actionLabel: string;
}

export function StepRow({
  index,
  title,
  description,
  status,
  to,
  enabled,
  actionLabel,
}: StepRowProps) {
  return (
    <li className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="flex items-start gap-4">
        <span
          aria-hidden="true"
          className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-border text-xs text-muted-foreground"
        >
          {index}
        </span>
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-medium leading-snug">{title}</h3>
            <StatusPill status={status} />
          </div>
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        </div>
      </div>

      <div className="shrink-0 sm:pl-2">
        <Button
          asChild={enabled}
          disabled={!enabled}
          variant={status === "success" ? "outline" : "default"}
          size="sm"
        >
          {enabled ? (
            <Link to={to}>
              {actionLabel}
              <ArrowRight className="size-3.5" aria-hidden="true" />
            </Link>
          ) : (
            <span>Locked</span>
          )}
        </Button>
      </div>
    </li>
  );
}
