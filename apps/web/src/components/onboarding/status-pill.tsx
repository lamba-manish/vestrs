import { CheckCircle2, Circle, Clock, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

export type StepStatus = "not_started" | "in_progress" | "pending" | "success" | "failed";

const COPY: Record<StepStatus, { label: string; tone: string; Icon: typeof Circle }> = {
  not_started: {
    label: "Not started",
    tone: "border-border text-muted-foreground",
    Icon: Circle,
  },
  in_progress: {
    label: "In progress",
    tone: "border-border text-foreground",
    Icon: Circle,
  },
  pending: {
    label: "Under review",
    tone: "border-border text-foreground",
    Icon: Clock,
  },
  success: {
    label: "Complete",
    tone: "border-success/40 text-success",
    Icon: CheckCircle2,
  },
  failed: {
    label: "Failed",
    tone: "border-destructive/40 text-destructive",
    Icon: XCircle,
  },
};

export function StatusPill({ status, className }: { status: StepStatus; className?: string }) {
  const { label, tone, Icon } = COPY[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border bg-card/40 px-2.5 py-0.5 text-xs",
        tone,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}
