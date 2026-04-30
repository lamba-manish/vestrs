import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => {
          // Don't retry 4xx — they aren't transient.
          const status = (err as { status?: number }).status;
          if (status && status >= 400 && status < 500) return false;
          return count < 2;
        },
      },
      mutations: { retry: false },
    },
  });
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = React.useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider defaultPreference="dark">
        {children}
        <Toaster />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
