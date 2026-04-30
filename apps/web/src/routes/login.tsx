import { useEffect } from "react";
import { Link } from "react-router-dom";

import { LoginForm } from "@/components/auth/login-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function LoginPage() {
  useEffect(() => {
    document.title = "Sign in · Vestrs";
  }, []);

  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] items-center justify-center py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-2 text-center">
          <CardTitle>Welcome back.</CardTitle>
          <CardDescription>Sign in to continue your onboarding.</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm />
          <p className="mt-6 text-center text-sm text-muted-foreground">
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
    </div>
  );
}
