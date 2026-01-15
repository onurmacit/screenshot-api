"use client";

import { SessionProvider } from "next-auth/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
    // Create QueryClient inside component to avoid sharing between requests
    const [queryClient] = useState(() => new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 60 * 1000, // 1 minute - data considered fresh
                gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache
                refetchOnWindowFocus: false, // Don't refetch on tab switch
                retry: 1, // Only retry once on failure
            }
        }
    }));

    return (
        <QueryClientProvider client={queryClient}>
            <SessionProvider>
                {children}
            </SessionProvider>
        </QueryClientProvider>
    );
}
