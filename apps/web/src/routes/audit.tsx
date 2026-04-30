import { ArrowLeft, Loader2 } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuditFeed } from "@/lib/audit";
import type { AuditEntry } from "@/lib/schemas/audit";
import { cn } from "@/lib/utils";

export function AuditPage() {
  useEffect(() => {
    document.title = "Audit log · Vestrs";
  }, []);
  return (
    <AuthGuard>
      <AuditContent />
    </AuthGuard>
  );
}

function AuditContent() {
  const feed = useAuditFeed();

  const entries: AuditEntry[] = feed.data?.pages.flatMap((page) => page.items) ?? [];

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
          <CardTitle>Audit log</CardTitle>
          <CardDescription>
            Every state-changing action — login, KYC submit, accreditation, bank link, investment —
            is recorded here in the same database transaction as the action itself.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {feed.isLoading ? (
            <div className="space-y-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No audit entries yet. Sign in events, KYC submissions, and investments will appear
              here.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {entries.map((entry) => (
                <Row key={entry.id} entry={entry} />
              ))}
            </ul>
          )}

          {feed.hasNextPage && (
            <div className="mt-5 flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => feed.fetchNextPage()}
                disabled={feed.isFetchingNextPage}
              >
                {feed.isFetchingNextPage && <Loader2 className="size-4 animate-spin" />}
                Load older
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ entry }: { entry: AuditEntry }) {
  const ts = new Date(entry.timestamp);
  return (
    <li className="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <code className="text-sm font-medium">{entry.action}</code>
          <StatusBadge status={entry.status} />
        </div>
        {hasMeta(entry.metadata) && (
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {summariseMeta(entry.metadata)}
          </p>
        )}
      </div>
      <time
        dateTime={entry.timestamp}
        className="shrink-0 text-xs text-muted-foreground"
        title={ts.toISOString()}
      >
        {ts.toLocaleString()}
      </time>
    </li>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "success"
      ? "border-success/40 text-success"
      : status === "failure"
        ? "border-destructive/40 text-destructive"
        : "border-border text-muted-foreground";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border bg-card/40 px-2 py-0.5 text-[10px] uppercase tracking-wider",
        tone,
      )}
    >
      {status}
    </span>
  );
}

function hasMeta(metadata: Record<string, unknown>): boolean {
  return Object.keys(metadata).length > 0;
}

function summariseMeta(metadata: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(metadata)) {
    if (value === null || value === undefined) continue;
    const v = typeof value === "object" ? JSON.stringify(value) : String(value);
    parts.push(`${key}=${v}`);
    if (parts.length >= 4) break;
  }
  return parts.join(" · ");
}
