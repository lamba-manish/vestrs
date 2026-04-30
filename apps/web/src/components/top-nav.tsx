import { LogOut, User as UserIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useMe } from "@/lib/auth";

export function TopNav() {
  const me = useMe();
  const logout = useLogout();

  // Render decision rule: if we have a positively-resolved user, show the
  // account dropdown; otherwise (loading OR anonymous) show the
  // sign-in/open-account CTAs immediately. Most first paints are
  // anonymous visitors, and showing a 24px skeleton while /me resolves
  // makes the page feel cold for 2-3s on the first hit. The brief flash
  // for authenticated users is the lesser evil — tanstack-query has a
  // 60s staleTime, so subsequent navigations don't re-flash.
  const authed = !me.isLoading && me.data;

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Link
          to="/"
          className="font-serif-display text-xl tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          Vestrs
        </Link>

        <nav className="flex items-center gap-1">
          <ThemeToggle />

          {authed ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                  <UserIcon className="size-4" />
                  <span className="max-w-[12rem] truncate text-sm">{me.data!.email}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-56">
                <DropdownMenuLabel>Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/dashboard">Dashboard</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/audit">Audit log</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onSelect={(e) => {
                    e.preventDefault();
                    logout.mutate();
                  }}
                >
                  <LogOut className="mr-2 size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <div className="flex items-center gap-1">
              <Button variant="ghost" asChild>
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild>
                <Link to="/signup">Open account</Link>
              </Button>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
