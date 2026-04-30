import { useEffect } from "react";
import { Link } from "react-router-dom";

import { LoginForm } from "@/components/auth/login-form";
import { AuthSideInfo } from "@/components/auth/side-info";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LoginPage() {
  useEffect(() => {
    document.title = "Sign in · Vestrs";
  }, []);

  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] items-center py-8">
      <div className="mx-auto grid w-full max-w-5xl gap-6 md:grid-cols-2 md:items-stretch">
        <Card className="w-full max-w-md justify-self-center md:max-w-none md:justify-self-stretch">
          <CardHeader className="space-y-2 text-center md:text-left">
            <CardTitle>Welcome back.</CardTitle>
            <CardDescription>Sign in to continue your onboarding.</CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm />
            <p className="mt-6 text-center text-sm text-muted-foreground md:text-left">
              New to Vestrs?{" "}
              <Link
                to="/signup"
                className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
              >
                Open an account
              </Link>
            </p>
          </CardContent>
        </Card>

        <AuthSideInfo />
      </div>
    </div>
  );
}
