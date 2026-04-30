import { useEffect } from "react";
import { Link } from "react-router-dom";

import { SignupForm } from "@/components/auth/signup-form";
import { AuthSideInfo } from "@/components/auth/side-info";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function SignupPage() {
  useEffect(() => {
    document.title = "Open an account · Vestrs";
  }, []);

  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] items-center py-8">
      <div className="mx-auto grid w-full max-w-5xl gap-6 md:grid-cols-2 md:items-stretch">
        <Card className="w-full max-w-md justify-self-center md:max-w-none md:justify-self-stretch">
          <CardHeader className="space-y-2 text-center md:text-left">
            <CardTitle>Open an account.</CardTitle>
            <CardDescription>
              All fields are required. We never share your details with third parties beyond your
              KYC and bank-link providers.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SignupForm />
            <p className="mt-6 text-center text-sm text-muted-foreground md:text-left">
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

        <AuthSideInfo />
      </div>
    </div>
  );
}
