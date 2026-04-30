import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Loader2, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { ApiError } from "@/lib/api";
import { useSignup } from "@/lib/auth";
import { userMessage } from "@/lib/error-messages";
import { PASSWORD_RULES, type SignupValues, signupSchema } from "@/lib/schemas/auth";

export function SignupForm() {
  const signup = useSignup();
  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    mode: "onChange",
  });

  const password = watch("password") ?? "";

  async function onSubmit(values: SignupValues) {
    try {
      await signup.mutateAsync({
        email: values.email,
        password: values.password,
      });
      toast.success("Account created.");
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === "CONFLICT") {
          setError("email", { message: "An account with this email already exists." });
          return;
        }
        if (e.details) {
          for (const [field, msgs] of Object.entries(e.details)) {
            setError(field as keyof SignupValues, { message: msgs[0] });
          }
          return;
        }
        console.error("signup_failed", { code: e.code, requestId: e.requestId });
        toast.error(userMessage(e));
      } else {
        toast.error("Something went wrong. Please try again.");
      }
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          aria-invalid={errors.email ? "true" : "false"}
          {...register("email")}
        />
        {errors.email && (
          <p role="alert" className="text-xs text-destructive">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <PasswordInput
          id="password"
          autoComplete="new-password"
          aria-describedby="password-checklist"
          aria-invalid={errors.password ? "true" : "false"}
          {...register("password")}
        />
        <PasswordChecklist value={password} />
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm_password">Confirm password</Label>
        <PasswordInput
          id="confirm_password"
          autoComplete="new-password"
          aria-invalid={errors.confirm_password ? "true" : "false"}
          {...register("confirm_password")}
        />
        {errors.confirm_password && (
          <p role="alert" className="text-xs text-destructive">
            {errors.confirm_password.message}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="size-4 animate-spin" />}
        Open account
      </Button>
    </form>
  );
}

function PasswordChecklist({ value }: { value: string }) {
  // Surface only the next failing rule, in priority order. Once one
  // rule passes the next slides in. When everything's green, show a
  // single confirmation. This keeps the form's signal tight —
  // five red Xs side-by-side is louder than the form is trying to be.
  const nextFailing = PASSWORD_RULES.find((rule) => !rule.test(value));

  if (value.length === 0) {
    return (
      <p id="password-checklist" className="pt-1 text-xs text-muted-foreground">
        12+ characters, with a lowercase, uppercase, digit, and symbol.
      </p>
    );
  }

  if (!nextFailing) {
    return (
      <p
        id="password-checklist"
        className="inline-flex items-center gap-1.5 pt-1 text-xs text-success"
      >
        <Check className="size-3.5" aria-hidden="true" />
        Strong password.
      </p>
    );
  }

  return (
    <p
      id="password-checklist"
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1.5 pt-1 text-xs text-muted-foreground"
    >
      <X className="size-3.5 text-destructive" aria-hidden="true" />
      <span>{nextFailing.nudge}</span>
    </p>
  );
}
