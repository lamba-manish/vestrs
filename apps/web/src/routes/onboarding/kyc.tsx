import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StatusPill } from "@/components/onboarding/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { userMessage } from "@/lib/error-messages";
import { useKycSummary, useRetryKyc, useSubmitKyc } from "@/lib/kyc";

export function KycPage() {
  useEffect(() => {
    document.title = "Identity verification · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <KycContent />
    </AuthGuard>
  );
}

function KycContent() {
  const summary = useKycSummary();
  const submit = useSubmitKyc();
  const retry = useRetryKyc();

  async function handle(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      toast.success(success);
    } catch (e) {
      if (e instanceof ApiError) {
        console.error("kyc_action_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

  const status = summary.data?.status ?? "not_started";
  const remaining = summary.data?.attempts_remaining ?? 3;

  return (
    <div className="container max-w-2xl py-10 sm:py-12">
      <Link
        to="/dashboard"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to dashboard
      </Link>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Identity verification</CardTitle>
              <CardDescription>
                Real providers (Shufti Pro, Jumio, Plaid IDV) plug into the same adapter. The mock
                returns a deterministic outcome based on your email tag — see hint below.
              </CardDescription>
            </div>
            <StatusPill
              status={
                status === "not_started"
                  ? "not_started"
                  : status === "pending"
                    ? "pending"
                    : status === "success"
                      ? "success"
                      : "failed"
              }
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {summary.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <>
              <DemoHints />

              <div className="rounded-md border border-border bg-card/40 p-4 text-sm leading-6">
                {status === "not_started" && (
                  <p>
                    Submit your KYC check now. The mock provider will respond instantly. Up to{" "}
                    {remaining} attempts.
                  </p>
                )}
                {status === "pending" && <p>Your KYC check is pending review.</p>}
                {status === "success" && <p>Your identity has been verified.</p>}
                {status === "failed" && summary.data?.latest && (
                  <p>
                    Reason:{" "}
                    <span className="font-medium">
                      {summary.data.latest.failure_reason ?? "unknown"}
                    </span>
                    . Attempts remaining: {remaining}.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3">
                {status === "not_started" && (
                  <Button
                    onClick={() => handle(submit.mutateAsync, "KYC submitted.")}
                    disabled={submit.isPending}
                  >
                    {submit.isPending && <Loader2 className="size-4 animate-spin" />}
                    Submit KYC
                  </Button>
                )}
                {status === "failed" && remaining > 0 && (
                  <Button
                    onClick={() => handle(retry.mutateAsync, "Retried.")}
                    disabled={retry.isPending}
                  >
                    {retry.isPending && <Loader2 className="size-4 animate-spin" />}
                    Retry
                  </Button>
                )}
                {status === "success" && (
                  <Button asChild>
                    <Link to="/onboarding/accreditation">Continue to accreditation</Link>
                  </Button>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DemoHints() {
  return (
    <div className="rounded-md border border-dashed border-border p-4 text-xs leading-5 text-muted-foreground">
      <p className="mb-1 font-medium text-foreground">Demo controls</p>
      <ul className="list-disc space-y-0.5 pl-5">
        <li>
          Default email → <span className="text-foreground">success</span>.
        </li>
        <li>
          <code>+kyc_fail</code> tag in email → eventual failure with retry.
        </li>
        <li>
          <code>+kyc_pending</code> tag in email → returns pending.
        </li>
      </ul>
    </div>
  );
}
