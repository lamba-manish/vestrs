import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="container flex min-h-[calc(100dvh-8rem)] items-center justify-center py-12">
      <div className="max-w-md space-y-4 text-center">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">404</p>
        <h1 className="font-serif-display text-3xl tracking-tight">
          This page doesn&apos;t exist.
        </h1>
        <p className="text-muted-foreground">The link may be old, or the page may have moved.</p>
        <Button asChild>
          <Link to="/">Back to home</Link>
        </Button>
      </div>
    </div>
  );
}
