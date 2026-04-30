import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StatusPill } from "@/components/onboarding/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccreditationSummary, useSubmitAccreditation } from "@/lib/accreditation";
import { ApiError } from "@/lib/api";
import { userMessage } from "@/lib/error-messages";

export function AccreditationPage() {
  useEffect(() => {
    document.title = "Accreditation · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <AccreditationContent />
    </AuthGuard>
  );
}

function AccreditationContent() {
  const summary = useAccreditationSummary();
  const submit = useSubmitAccreditation();

  async function onSubmit() {
    try {
      await submit.mutateAsync();
      toast.success("Accreditation submitted. We'll update this page when it resolves.");
    } catch (e) {
      if (e instanceof ApiError) {
        console.error("acc_submit_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

  const status = summary.data?.status ?? "not_started";

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
              <CardTitle>Accreditation review</CardTitle>
              <CardDescription>
                Real reviews take 12–48 hours. The mock resolves in roughly 5 seconds. This page
                polls for status while pending.
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
              <div className="rounded-md border border-dashed border-border p-4 text-xs leading-5 text-muted-foreground">
                <p className="mb-1 font-medium text-foreground">Demo controls</p>
                <ul className="list-disc space-y-0.5 pl-5">
                  <li>
                    Default email → eventual <span className="text-foreground">success</span>.
                  </li>
                  <li>
                    <code>+acc_fail</code> tag → eventual failure.
                  </li>
                </ul>
              </div>

              <div className="rounded-md border border-border bg-card/40 p-4 text-sm leading-6">
                {status === "not_started" && (
                  <p>Submit your accreditation review. We'll begin polling automatically.</p>
                )}
                {status === "pending" && (
                  <span className="inline-flex items-center gap-2">
                    <Loader2
                      className="size-3.5 animate-spin text-muted-foreground"
                      aria-hidden="true"
                    />
                    <span>Reviewing your accreditation…</span>
                  </span>
                )}
                {status === "success" && <p>You've been verified as an accredited investor.</p>}
                {status === "failed" && summary.data?.latest && (
                  <p>
                    Reason:{" "}
                    <span className="font-medium">
                      {summary.data.latest.failure_reason ?? "unknown"}
                    </span>
                    .
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-3">
                {status === "not_started" && (
                  <Button onClick={onSubmit} disabled={submit.isPending}>
                    {submit.isPending && <Loader2 className="size-4 animate-spin" />}
                    Submit accreditation
                  </Button>
                )}
                {status === "success" && (
                  <Button asChild>
                    <Link to="/onboarding/bank">Continue to bank link</Link>
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
