import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useBankSummary, useLinkBank, useUnlinkBank } from "@/lib/bank";
import { CURRENCIES, findCurrency } from "@/lib/currencies";
import { userMessage } from "@/lib/error-messages";
import { type BankLinkFormValues, bankLinkFormSchema, formatAccountType } from "@/lib/schemas/bank";

const ACCOUNT_TYPE_OPTIONS: ComboboxOption[] = [
  { value: "checking", label: "Checking", searchTokens: "checking" },
  { value: "savings", label: "Savings", searchTokens: "savings" },
  { value: "money_market", label: "Money market", searchTokens: "money market" },
];

export function BankPage() {
  useEffect(() => {
    document.title = "Link bank · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <BankContent />
    </AuthGuard>
  );
}

function BankContent() {
  const summary = useBankSummary();
  const link = useLinkBank();
  const unlink = useUnlinkBank();
  const {
    register,
    handleSubmit,
    setError,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<BankLinkFormValues>({
    resolver: zodResolver(bankLinkFormSchema),
    defaultValues: { account_type: "checking", currency: "USD" },
  });

  const currencyOptions: ComboboxOption[] = useMemo(
    () =>
      CURRENCIES.map((c) => ({
        value: c.code,
        searchTokens: `${c.code} ${c.symbol} ${c.name}`,
        label: (
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs font-medium text-muted-foreground">{c.code}</span>
            <span className="text-base">{c.symbol}</span>
            <span>{c.name}</span>
          </span>
        ),
        triggerLabel: (
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs font-medium text-muted-foreground">{c.code}</span>
            <span>{c.symbol}</span>
            <span>{c.name}</span>
          </span>
        ),
      })),
    [],
  );

  async function onSubmit(values: BankLinkFormValues) {
    try {
      await link.mutateAsync(values);
      toast.success("Bank linked.");
      reset();
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.details) {
          for (const [field, msgs] of Object.entries(e.details)) {
            setError(field as keyof BankLinkFormValues, { message: msgs[0] });
          }
          return;
        }
        console.error("bank_link_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

  async function onUnlink() {
    try {
      await unlink.mutateAsync();
      toast.success("Bank unlinked.");
    } catch (e) {
      if (e instanceof ApiError) toast.error(userMessage(e));
    }
  }

  return (
    <div className="container max-w-3xl py-10 sm:py-12">
      <Link
        to="/dashboard"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to dashboard
      </Link>

      {summary.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : summary.data?.linked && summary.data.account ? (
        <LinkedAccountCard
          account={summary.data.account}
          onUnlink={onUnlink}
          unlinking={unlink.isPending}
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Link a bank account</CardTitle>
            <CardDescription>
              We use a Plaid-like adapter. The mock validates the inputs and echoes only the last
              four digits — your account number never leaves the request handler.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              noValidate
              onSubmit={handleSubmit(onSubmit)}
              className="grid gap-5 sm:grid-cols-2"
            >
              <FieldRow
                label="Bank name"
                id="bank_name"
                error={errors.bank_name?.message}
                {...register("bank_name")}
              />
              <FieldRow
                label="Account holder name"
                id="account_holder_name"
                error={errors.account_holder_name?.message}
                {...register("account_holder_name")}
              />

              <div className="space-y-2">
                <Label htmlFor="account_type">Account type</Label>
                <Controller
                  control={control}
                  name="account_type"
                  render={({ field }) => (
                    <Combobox
                      id="account_type"
                      options={ACCOUNT_TYPE_OPTIONS}
                      value={field.value}
                      onChange={(v) => field.onChange(v as BankLinkFormValues["account_type"])}
                      placeholder="Select account type…"
                      searchPlaceholder="Search…"
                      ariaInvalid={!!errors.account_type}
                    />
                  )}
                />
                {errors.account_type && (
                  <p role="alert" className="text-xs text-destructive">
                    {errors.account_type.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Controller
                  control={control}
                  name="currency"
                  render={({ field }) => (
                    <Combobox
                      id="currency"
                      options={currencyOptions}
                      value={field.value}
                      onChange={field.onChange}
                      placeholder="Select currency…"
                      searchPlaceholder="Search by code, symbol, or name…"
                      ariaInvalid={!!errors.currency}
                    />
                  )}
                />
                {errors.currency && (
                  <p role="alert" className="text-xs text-destructive">
                    {errors.currency.message}
                  </p>
                )}
              </div>

              <FieldRow
                label="Account number"
                id="account_number"
                inputMode="numeric"
                error={errors.account_number?.message}
                {...register("account_number")}
              />
              <FieldRow
                label="Routing number"
                id="routing_number"
                inputMode="numeric"
                error={errors.routing_number?.message}
                {...register("routing_number")}
              />

              <div className="flex justify-end gap-3 pt-2 sm:col-span-2">
                <Button asChild variant="ghost" type="button">
                  <Link to="/dashboard">Cancel</Link>
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                  Link bank
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function LinkedAccountCard({
  account,
  onUnlink,
  unlinking,
}: {
  account: {
    bank_name: string;
    account_holder_name: string;
    account_type: string;
    last_four: string;
    currency: string;
    mock_balance: string;
  };
  onUnlink: () => void;
  unlinking: boolean;
}) {
  const currency = findCurrency(account.currency);
  const balanceDisplay = currency
    ? `${currency.symbol}${account.mock_balance} ${currency.code}`
    : `${account.currency} ${account.mock_balance}`;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Bank account linked</CardTitle>
        <CardDescription>
          We store masked details only. Plaintext numbers never reach the database.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <Pair k="Bank" v={account.bank_name} />
          <Pair k="Account" v={`••• ${account.last_four}`} />
          <Pair k="Account type" v={formatAccountType(account.account_type)} />
          <Pair
            k="Currency"
            v={currency ? `${currency.code} (${currency.symbol})` : account.currency}
          />
          <Pair k="Available" v={balanceDisplay} />
          <Pair k="Holder" v={account.account_holder_name} />
        </dl>
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onUnlink} disabled={unlinking}>
            {unlinking && <Loader2 className="size-4 animate-spin" />}
            Unlink
          </Button>
          <Button asChild>
            <Link to="/onboarding/invest">Continue to investment</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
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

interface FieldRowProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  error?: string;
}

function FieldRow({ label, id, error, ...rest }: FieldRowProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={error ? "true" : "false"} {...rest} />
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
