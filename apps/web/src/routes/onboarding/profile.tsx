import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { COUNTRIES } from "@/lib/countries";
import { userMessage } from "@/lib/error-messages";
import { useProfile, useUpdateProfile } from "@/lib/profile";
import {
  composePhone,
  type ProfileFormValues,
  profileFormSchema,
  splitPhone,
} from "@/lib/schemas/profile";

export function ProfilePage() {
  useEffect(() => {
    document.title = "Profile · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <ProfileContent />
    </AuthGuard>
  );
}

function ProfileContent() {
  const me = useProfile();
  const update = useUpdateProfile();
  const navigate = useNavigate();

  const initialPhone = useMemo(
    () => splitPhone(me.data?.phone, me.data?.domicile),
    [me.data?.phone, me.data?.domicile],
  );

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: me.data
      ? {
          full_name: me.data.full_name ?? "",
          nationality: me.data.nationality ?? "",
          domicile: me.data.domicile ?? "",
          phone_country: initialPhone.phone_country,
          phone_number: initialPhone.phone_number,
        }
      : undefined,
  });

  async function onSubmit(values: ProfileFormValues) {
    try {
      // Backend expects a single E.164 string. Compose from the split fields.
      await update.mutateAsync({
        full_name: values.full_name,
        nationality: values.nationality,
        domicile: values.domicile,
        phone: composePhone(values),
      });
      toast.success("Profile saved.");
      navigate("/dashboard");
    } catch (e) {
      handleProfileError(e);
    }
  }

  function handleProfileError(e: unknown) {
    if (!(e instanceof ApiError)) {
      toast.error("Something went wrong. Please try again.");
      return;
    }
    if (e.details) {
      for (const [field, msgs] of Object.entries(e.details)) {
        // The backend doesn't know about phone_country/phone_number;
        // it only sees `phone`. Surface phone-related errors on the
        // national-number input (the most common edit point) and clean
        // up pydantic's "Value error, …" prefix so the message reads
        // like a user-facing nudge.
        const target = field === "phone" ? "phone_number" : (field as keyof ProfileFormValues);
        const cleaned = cleanServerMessage(msgs[0]);
        setError(target, { message: cleaned });
      }
      return;
    }
    console.error("profile_update_failed", { code: e.code, requestId: e.requestId });
    toast.error(userMessage(e));
  }

  function cleanServerMessage(raw: string): string {
    // pydantic's field-validator ValueError comes through as
    // "Value error, phone number is not a valid number" — strip the
    // prefix and capitalize the first character.
    const stripped = raw.replace(/^value error,\s*/i, "");
    return stripped.charAt(0).toUpperCase() + stripped.slice(1);
  }

  const countryOptions: ComboboxOption[] = useMemo(
    () =>
      COUNTRIES.map((c) => ({
        value: c.code,
        searchTokens: `${c.code} ${c.name} ${c.dial}`,
        label: (
          <span className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">{c.code}</span>
            <span>{c.name}</span>
          </span>
        ),
        triggerLabel: (
          <span className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">{c.code}</span>
            <span>{c.name}</span>
          </span>
        ),
      })),
    [],
  );

  const dialOptions: ComboboxOption[] = useMemo(
    () =>
      COUNTRIES.map((c) => ({
        value: c.code,
        searchTokens: `${c.name} +${c.dial} ${c.code}`,
        label: (
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">+{c.dial}</span>
            <span>{c.name}</span>
          </span>
        ),
        triggerLabel: <span className="font-mono text-sm">+{c.dial}</span>,
      })),
    [],
  );

  return (
    <div className="container max-w-3xl py-10 sm:py-12">
      <Link
        to="/dashboard"
        className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to dashboard
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Your profile</CardTitle>
          <CardDescription>
            Required for KYC and accreditation. We use ISO-3166-1 alpha-2 country codes; pick from
            the list — free-text country names aren't accepted.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit(onSubmit)} className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                autoComplete="name"
                aria-invalid={errors.full_name ? "true" : "false"}
                {...register("full_name")}
              />
              {errors.full_name && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.full_name.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="nationality">Nationality</Label>
              <Controller
                control={control}
                name="nationality"
                render={({ field }) => (
                  <Combobox
                    id="nationality"
                    options={countryOptions}
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Select country…"
                    searchPlaceholder="Search by name or ISO code…"
                    ariaInvalid={!!errors.nationality}
                  />
                )}
              />
              {errors.nationality && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.nationality.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="domicile">Country of residence</Label>
              <Controller
                control={control}
                name="domicile"
                render={({ field }) => (
                  <Combobox
                    id="domicile"
                    options={countryOptions}
                    value={field.value}
                    onChange={field.onChange}
                    placeholder="Select country…"
                    searchPlaceholder="Search by name or ISO code…"
                    ariaInvalid={!!errors.domicile}
                  />
                )}
              />
              {errors.domicile && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.domicile.message}
                </p>
              )}
            </div>

            <div className="space-y-2 sm:col-span-2">
              {/* htmlFor points at the dial-code combobox so screen
                  readers + Playwright `getByLabel(/phone/)` pick up the
                  whole field group. */}
              <Label htmlFor="phone_country">Phone</Label>
              {/* Two independent columns each carrying their own error
                  slot, so a "not a valid number" message renders under
                  the number input rather than under the dial-code
                  picker (the previous shared-error placement put the
                  message in the wrong column for users typing in the
                  number field). */}
              <div className="grid gap-3 sm:grid-cols-[200px_1fr]">
                <div>
                  <Controller
                    control={control}
                    name="phone_country"
                    render={({ field }) => (
                      <Combobox
                        id="phone_country"
                        options={dialOptions}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder="Country code"
                        searchPlaceholder="Search by country or +code…"
                        ariaInvalid={!!errors.phone_country}
                        contentClassName="w-[300px]"
                      />
                    )}
                  />
                  {errors.phone_country?.message && (
                    <p role="alert" className="mt-1 text-xs text-destructive">
                      {errors.phone_country.message}
                    </p>
                  )}
                </div>
                <div>
                  <Input
                    id="phone_number"
                    type="tel"
                    inputMode="tel"
                    placeholder="9876543210"
                    autoComplete="tel-national"
                    aria-invalid={errors.phone_number ? "true" : "false"}
                    {...register("phone_number")}
                  />
                  {errors.phone_number?.message && (
                    <p role="alert" className="mt-1 text-xs text-destructive">
                      {errors.phone_number.message}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2 sm:col-span-2">
              <Button asChild variant="ghost" type="button">
                <Link to="/dashboard">Cancel</Link>
              </Button>
              <Button type="submit" disabled={isSubmitting || me.isLoading}>
                {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Save profile
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
