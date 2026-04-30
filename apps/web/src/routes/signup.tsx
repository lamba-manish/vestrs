import { useEffect } from "react";
import { Link } from "react-router-dom";

import { SignupForm } from "@/components/auth/signup-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function SignupPage() {
  useEffect(() => {
    document.title = "Open an account · Vestrs";
  }, []);

  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] items-center justify-center py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-2 text-center">
          <CardTitle>Open an account.</CardTitle>
          <CardDescription>
            All fields are required. We never share your details with third parties beyond your KYC
            and bank-link providers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignupForm />
          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
            >
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
