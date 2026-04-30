import * as React from "react";
import { useNavigate } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/lib/auth";

/** Wraps protected pages — redirects to /login if anonymous. */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const me = useMe();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (!me.isLoading && me.data === null) {
      navigate("/login", { replace: true });
    }
  }, [me.isLoading, me.data, navigate]);

  if (me.isLoading || me.data === null) {
    return (
      <div className="container py-16">
        <div className="mx-auto max-w-2xl space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
