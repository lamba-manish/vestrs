import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { userMessage } from "@/lib/error-messages";
import { useProfile, useUpdateProfile } from "@/lib/profile";
import { type ProfileFormValues, profileFormSchema } from "@/lib/schemas/profile";

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
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileFormSchema),
    values: me.data
      ? {
          full_name: me.data.full_name ?? "",
          nationality: me.data.nationality ?? "",
          domicile: me.data.domicile ?? "",
          phone: me.data.phone ?? "",
        }
      : undefined,
  });

  async function onSubmit(values: ProfileFormValues) {
    try {
      await update.mutateAsync(values);
      toast.success("Profile saved.");
      navigate("/dashboard");
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.details) {
          for (const [field, msgs] of Object.entries(e.details)) {
            setError(field as keyof ProfileFormValues, { message: msgs[0] });
          }
          return;
        }
        console.error("profile_update_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

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
          <CardTitle>Your profile</CardTitle>
          <CardDescription>
            Required for KYC and accreditation. Use ISO-3166-1 alpha-2 country codes (US, IN, GB)
            and an international phone format.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit(onSubmit)} className="grid gap-4 sm:grid-cols-2">
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
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+14155551234"
                autoComplete="tel"
                aria-invalid={errors.phone ? "true" : "false"}
                {...register("phone")}
              />
              {errors.phone && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.phone.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="nationality">Nationality (ISO-2)</Label>
              <Input
                id="nationality"
                placeholder="US"
                maxLength={2}
                aria-invalid={errors.nationality ? "true" : "false"}
                {...register("nationality")}
              />
              {errors.nationality && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.nationality.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="domicile">Country of residence (ISO-2)</Label>
              <Input
                id="domicile"
                placeholder="US"
                maxLength={2}
                aria-invalid={errors.domicile ? "true" : "false"}
                {...register("domicile")}
              />
              {errors.domicile && (
                <p role="alert" className="text-xs text-destructive">
                  {errors.domicile.message}
                </p>
              )}
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
