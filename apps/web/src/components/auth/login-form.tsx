import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useLogin } from "@/lib/auth";
import { userMessage } from "@/lib/error-messages";
import { type LoginValues, loginSchema } from "@/lib/schemas/auth";

export function LoginForm() {
  const login = useLogin();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginValues) {
    try {
      await login.mutateAsync(values);
      toast.success("Welcome back.");
    } catch (e) {
      if (e instanceof ApiError) {
        // Vague-by-design: same message for unknown-email and wrong-password.
        // Surface on the password field — same copy either way, so no
        // enumeration risk.
        if (e.code === "AUTH_INVALID_CREDENTIALS") {
          setError("password", { message: userMessage(e) });
          return;
        }
        if (e.details) {
          for (const [field, msgs] of Object.entries(e.details)) {
            setError(field as keyof LoginValues, { message: msgs[0] });
          }
          return;
        }
        // Unknown server error — log the request id for support correlation
        // but show the user a clean message.
        console.error("login_failed", { code: e.code, requestId: e.requestId });
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
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={errors.password ? "true" : "false"}
          {...register("password")}
        />
        {errors.password && (
          <p role="alert" className="text-xs text-destructive">
            {errors.password.message}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting && <Loader2 className="size-4 animate-spin" />}
        Sign in
      </Button>
    </form>
  );
}
