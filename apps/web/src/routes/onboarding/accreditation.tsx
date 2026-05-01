import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StatusPill } from "@/components/onboarding/status-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccreditationSummary, useSubmitAccreditation } from "@/lib/accreditation";
import { ApiError } from "@/lib/api";
import { formatAccreditationPath, formatFailureReason } from "@/lib/audit-format";
import { userMessage } from "@/lib/error-messages";
import {
  type AccreditationSubmitValues,
  type IncomeAccreditationValues,
  type NetWorthAccreditationValues,
  type ProfessionalCertAccreditationValues,
  incomeAccreditationSchema,
  netWorthAccreditationSchema,
  professionalCertAccreditationSchema,
} from "@/lib/schemas/accreditation";
import { cn } from "@/lib/utils";

type PathKey = "income" | "net_worth" | "professional_certification";

const PATHS: { key: PathKey; eyebrow: string; title: string; blurb: string }[] = [
  {
    key: "income",
    eyebrow: "Income test",
    title: "$200k+ income (or $300k joint)",
    blurb:
      "Earned at this level for the past two years, with a reasonable expectation of the same in the current year.",
  },
  {
    key: "net_worth",
    eyebrow: "Net-worth test",
    title: "$1M+ net worth",
    blurb: "Excluding the value of your primary residence — individually or jointly with a spouse.",
  },
  {
    key: "professional_certification",
    eyebrow: "Professional credential",
    title: "Series 7, 65, or 82 in good standing",
    blurb: "FINRA-issued license recognised under the 2020 Reg D amendment.",
  },
];

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
                Pick the SEC criterion you qualify under. Real reviews take 12–48 hours; the mock
                resolves in ~5 seconds. This page polls for status while pending.
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
          ) : status === "not_started" || status === "failed" ? (
            <PathPicker
              previousFailure={status === "failed" ? summary.data?.latest?.failure_reason : null}
            />
          ) : (
            <StatusBlock
              status={status}
              failureReason={summary.data?.latest?.failure_reason ?? null}
              path={summary.data?.latest?.path ?? null}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PathPicker({ previousFailure }: { previousFailure?: string | null }) {
  const [selected, setSelected] = useState<PathKey | null>(null);
  return (
    <div className="space-y-4">
      {previousFailure && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
          Previous attempt failed:{" "}
          <span className="font-medium">{formatFailureReason(previousFailure)}</span>. Try another
          path or correct the data and resubmit.
        </div>
      )}
      <div role="radiogroup" aria-label="Accreditation path" className="grid gap-3">
        {PATHS.map((path) => {
          const active = selected === path.key;
          return (
            <button
              key={path.key}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => setSelected(path.key)}
              className={cn(
                "rounded-md border p-4 text-left transition-colors",
                active
                  ? "border-primary bg-primary/5"
                  : "border-border bg-card/40 hover:border-foreground/30",
              )}
            >
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                {path.eyebrow}
              </p>
              <p className="mt-1 text-sm font-medium">{path.title}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{path.blurb}</p>
            </button>
          );
        })}
      </div>

      {selected === "income" && <IncomeForm />}
      {selected === "net_worth" && <NetWorthForm />}
      {selected === "professional_certification" && <ProfessionalCertForm />}
    </div>
  );
}

function StatusBlock({
  status,
  failureReason,
  path,
}: {
  status: "pending" | "success";
  failureReason: string | null;
  path: string | null;
}) {
  return (
    <div className="rounded-md border border-border bg-card/40 p-4 text-sm leading-6">
      {status === "pending" && (
        <span className="inline-flex items-center gap-2">
          <Loader2 className="size-3.5 animate-spin text-muted-foreground" aria-hidden="true" />
          <span>
            Reviewing your accreditation
            {path ? ` (${formatAccreditationPath(path)})` : ""}…
          </span>
        </span>
      )}
      {status === "success" && (
        <div className="flex items-center justify-between gap-4">
          <div>
            <p>You've been verified as an accredited investor.</p>
            {path && (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Verified via the {formatAccreditationPath(path).toLowerCase()}.
              </p>
            )}
            {failureReason && (
              <p className="mt-1 text-xs text-muted-foreground">
                Notes: {formatFailureReason(failureReason)}
              </p>
            )}
          </div>
          <Button asChild>
            <Link to="/onboarding/bank">Continue to bank link</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

// ---- per-path forms ----

function useSubmitForm() {
  const submit = useSubmitAccreditation();
  return async (body: AccreditationSubmitValues) => {
    try {
      await submit.mutateAsync(body);
      toast.success("Accreditation submitted. We'll update this page when it resolves.");
    } catch (e) {
      if (e instanceof ApiError) {
        console.error("acc_submit_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  };
}

function IncomeForm() {
  const submitForm = useSubmitForm();
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<IncomeAccreditationValues>({
    resolver: zodResolver(incomeAccreditationSchema),
    defaultValues: {
      path: "income",
      annual_income_usd: "",
      joint_with_spouse: false,
      years_at_or_above: 2,
      expects_same_current_year: true,
    },
    mode: "onBlur",
  });
  const joint = watch("joint_with_spouse");

  return (
    <form
      onSubmit={handleSubmit((v) => submitForm(v))}
      className="space-y-4 rounded-md border border-border bg-card/40 p-4"
    >
      <div className="space-y-2">
        <Label htmlFor="annual_income_usd">
          Annual income (USD) — past two years, expected this year
        </Label>
        <Input
          id="annual_income_usd"
          inputMode="decimal"
          placeholder={joint ? "300000.00" : "200000.00"}
          aria-invalid={errors.annual_income_usd ? "true" : "false"}
          {...register("annual_income_usd")}
        />
        {errors.annual_income_usd && (
          <p role="alert" className="text-xs text-destructive">
            {errors.annual_income_usd.message}
          </p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("joint_with_spouse")} className="size-4" />
        Jointly with spouse / spousal-equivalent
      </label>

      <div className="space-y-2">
        <Label htmlFor="years_at_or_above">Years at or above this income</Label>
        <Input
          id="years_at_or_above"
          type="number"
          min={1}
          max={10}
          aria-invalid={errors.years_at_or_above ? "true" : "false"}
          {...register("years_at_or_above", { valueAsNumber: true })}
        />
        {errors.years_at_or_above && (
          <p role="alert" className="text-xs text-destructive">
            {errors.years_at_or_above.message}
          </p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          defaultChecked
          {...register("expects_same_current_year")}
          className="size-4"
        />
        I have a reasonable expectation of the same income this year
      </label>
      {errors.expects_same_current_year && (
        <p role="alert" className="text-xs text-destructive">
          {errors.expects_same_current_year.message}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting && <Loader2 className="size-4 animate-spin" />}
        Submit income attestation
      </Button>
    </form>
  );
}

function NetWorthForm() {
  const submitForm = useSubmitForm();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<NetWorthAccreditationValues>({
    resolver: zodResolver(netWorthAccreditationSchema),
    defaultValues: {
      path: "net_worth",
      net_worth_usd: "",
      joint_with_spouse: false,
      excludes_primary_residence: true,
    },
    mode: "onBlur",
  });

  return (
    <form
      onSubmit={handleSubmit((v) => submitForm(v))}
      className="space-y-4 rounded-md border border-border bg-card/40 p-4"
    >
      <div className="space-y-2">
        <Label htmlFor="net_worth_usd">Net worth (USD)</Label>
        <Input
          id="net_worth_usd"
          inputMode="decimal"
          placeholder="1000000.00"
          aria-invalid={errors.net_worth_usd ? "true" : "false"}
          {...register("net_worth_usd")}
        />
        {errors.net_worth_usd && (
          <p role="alert" className="text-xs text-destructive">
            {errors.net_worth_usd.message}
          </p>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("joint_with_spouse")} className="size-4" />
        Jointly with spouse / spousal-equivalent
      </label>

      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          defaultChecked
          {...register("excludes_primary_residence")}
          className="mt-0.5 size-4"
        />
        <span>
          I confirm this number <strong>excludes</strong> the value of my primary residence (per SEC
          Reg D 506(c)).
        </span>
      </label>
      {errors.excludes_primary_residence && (
        <p role="alert" className="text-xs text-destructive">
          {errors.excludes_primary_residence.message}
        </p>
      )}

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting && <Loader2 className="size-4 animate-spin" />}
        Submit net-worth attestation
      </Button>
    </form>
  );
}

function ProfessionalCertForm() {
  const submitForm = useSubmitForm();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ProfessionalCertAccreditationValues>({
    resolver: zodResolver(professionalCertAccreditationSchema),
    defaultValues: {
      path: "professional_certification",
      license_kind: "series_7",
      license_number: "",
    },
    mode: "onBlur",
  });

  return (
    <form
      onSubmit={handleSubmit((v) => submitForm(v))}
      className="space-y-4 rounded-md border border-border bg-card/40 p-4"
    >
      <div className="space-y-2">
        <Label htmlFor="license_kind">License</Label>
        <select
          id="license_kind"
          aria-invalid={errors.license_kind ? "true" : "false"}
          {...register("license_kind")}
          className="flex h-10 w-full rounded-md border border-border bg-card/40 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="series_7">Series 7 — General Securities Representative</option>
          <option value="series_65">Series 65 — Investment Adviser Representative</option>
          <option value="series_82">Series 82 — Private Securities Offerings Representative</option>
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="license_number">License number</Label>
        <Input
          id="license_number"
          placeholder="e.g. 1234567"
          aria-invalid={errors.license_number ? "true" : "false"}
          {...register("license_number")}
        />
        {errors.license_number && (
          <p role="alert" className="text-xs text-destructive">
            {errors.license_number.message}
          </p>
        )}
      </div>

      <Button type="submit" disabled={isSubmitting} className="w-full sm:w-auto">
        {isSubmitting && <Loader2 className="size-4 animate-spin" />}
        Submit license attestation
      </Button>
    </form>
  );
}
