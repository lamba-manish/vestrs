import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useBankSummary } from "@/lib/bank";
import { findCurrency } from "@/lib/currencies";
import { userMessage } from "@/lib/error-messages";
import { useCreateInvestment, useInvestments } from "@/lib/investments";
import {
  type Investment,
  type InvestmentFormValues,
  investmentFormSchema,
} from "@/lib/schemas/investments";

export function InvestPage() {
  useEffect(() => {
    document.title = "Invest · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <InvestContent />
    </AuthGuard>
  );
}

function InvestContent() {
  const bank = useBankSummary();
  const investments = useInvestments();
  const create = useCreateInvestment();
  const [confirmation, setConfirmation] = useState<Investment | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InvestmentFormValues>({
    resolver: zodResolver(investmentFormSchema),
  });

  async function onSubmit(values: InvestmentFormValues) {
    try {
      const result = await create.mutateAsync(values);
      setConfirmation(result);
      reset();
      toast.success("Investment placed.");
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.details) {
          for (const [field, msgs] of Object.entries(e.details)) {
            setError(field as keyof InvestmentFormValues, { message: msgs[0] });
          }
          return;
        }
        console.error("invest_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

  if (bank.isLoading) {
    return (
      <Shell>
        <Skeleton className="h-64 w-full" />
      </Shell>
    );
  }

  if (!bank.data?.linked || !bank.data.account) {
    return (
      <Shell>
        <Card>
          <CardHeader>
            <CardTitle>Link a bank first</CardTitle>
            <CardDescription>
              Investments settle from your linked bank into a regulated escrow account. Link a bank
              to continue.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to="/onboarding/bank">Link a bank</Link>
            </Button>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  const account = bank.data.account;

  if (confirmation) {
    return (
      <Shell>
        <Card>
          <CardHeader>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 size-5 text-success" aria-hidden="true" />
              <div>
                <CardTitle>Investment placed</CardTitle>
                <CardDescription>
                  Funds have been routed to a regulated escrow account. A receipt is in your audit
                  log.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <Pair k="Amount" v={`${confirmation.currency} ${confirmation.amount}`} />
              <Pair k="Status" v={confirmation.status} />
              <Pair k="Escrow reference" v={confirmation.escrow_reference} />
              <Pair k="Placed" v={new Date(confirmation.created_at).toLocaleString()} />
            </dl>
            <div className="flex flex-wrap justify-end gap-3">
              <Button variant="outline" onClick={() => setConfirmation(null)}>
                Place another
              </Button>
              <Button asChild>
                <Link to="/audit">View audit log</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  return (
    <Shell>
      <Card>
        <CardHeader>
          <CardTitle>Place an investment</CardTitle>
          <CardDescription>
            Funds settle from your linked bank ({account.bank_name} ••• {account.last_four}) into a
            regulated escrow account. Each request is idempotent — duplicates are rejected.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-md border border-border bg-card/40 p-4">
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <Pair
                k="Available balance"
                v={formatBalance(account.currency, account.mock_balance)}
              />
              <Pair k="Currency" v={account.currency} />
            </dl>
          </div>

          <DemoHints />

          <form noValidate onSubmit={handleSubmit(onSubmit)} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="amount">Amount ({account.currency})</Label>
              <Input
                id="amount"
                inputMode="decimal"
                placeholder="10000.00"
                aria-invalid={errors.amount ? "true" : "false"}
                {...register("amount")}
              />
              {errors.amount && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.amount.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Input
                id="notes"
                placeholder="Q2 allocation"
                maxLength={500}
                aria-invalid={errors.notes ? "true" : "false"}
                {...register("notes")}
              />
              {errors.notes && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.notes.message}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-2 sm:col-span-2">
              <Button asChild variant="ghost" type="button">
                <Link to="/dashboard">Cancel</Link>
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Place investment
              </Button>
            </div>
          </form>

          {investments.data && investments.data.total > 0 && (
            <div className="border-t border-border pt-5">
              <h3 className="mb-3 text-sm font-medium">Recent investments</h3>
              <ul className="space-y-2">
                {investments.data.items.slice(0, 5).map((inv) => (
                  <li
                    key={inv.id}
                    className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
                  >
                    <div>
                      <span className="font-medium">
                        {inv.currency} {inv.amount}
                      </span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        {new Date(inv.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className="text-xs uppercase tracking-wider text-muted-foreground">
                      {inv.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="container max-w-2xl py-10 sm:py-12">
      <Link
        to="/dashboard"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to dashboard
      </Link>
      {children}
    </div>
  );
}

function Pair({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{k}</dt>
      <dd className="mt-0.5 font-medium">{v}</dd>
    </div>
  );
}

function formatBalance(code: string, amount: string): string {
  const currency = findCurrency(code);
  if (currency) return `${currency.symbol}${amount} ${currency.code}`;
  return `${code} ${amount}`;
}

function DemoHints() {
  return (
    <div className="rounded-md border border-dashed border-border p-4 text-xs leading-5 text-muted-foreground">
      <p className="mb-1 font-medium text-foreground">Demo controls</p>
      <ul className="list-disc space-y-0.5 pl-5">
        <li>
          Mock balance is seeded at link time. Try an amount under it for a successful placement.
        </li>
        <li>
          Try a very large amount → server returns <code>INSUFFICIENT_BALANCE</code>.
        </li>
        <li>
          Re-submitting the same form replays via the Idempotency-Key — changing the amount with the
          same key is rejected.
        </li>
      </ul>
    </div>
  );
}
