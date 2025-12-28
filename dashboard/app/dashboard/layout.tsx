"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
    LayoutDashboard,
    Play,
    CreditCard,
    Key,
    Settings,
    LogOut,
    AppWindow
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useSession, signOut } from "next-auth/react";
import Image from "next/image";
import { isTokenExpired, getTokenExpirationTime } from "@/services/api";

const sidebarItems = [
    { icon: LayoutDashboard, label: "Overview", href: "/dashboard" },
    { icon: Play, label: "Playground", href: "/dashboard/playground" },
    { icon: Key, label: "API Keys", href: "/dashboard/api-keys" },
    { icon: CreditCard, label: "Subscription", href: "/dashboard/subscription" },
    // { icon: Settings, label: "Settings", href: "/dashboard/settings" },
];

// Token check interval (every 30 seconds)
const TOKEN_CHECK_INTERVAL = 30 * 1000;

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const router = useRouter();
    const pathname = usePathname();
    const [isMounted, setIsMounted] = useState(false);
    const { data: session, status } = useSession();

    // Logout function
    const handleLogout = useCallback(async (expired: boolean = false) => {
        // Clear localStorage
        localStorage.removeItem("token");
        // Clear cookie
        document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
        // Sign out from NextAuth
        await signOut({ callbackUrl: expired ? "/login?expired=true" : "/login" });
    }, []);

    // Check token validity
    const checkTokenValidity = useCallback(() => {
        const token = localStorage.getItem("token");

        if (!token) {
            // No token - redirect to login
            router.push("/login");
            return false;
        }

        if (isTokenExpired(token)) {
            // Token expired - logout and redirect
            console.log("Token expired, logging out...");
            handleLogout(true);
            return false;
        }

        return true;
    }, [router, handleLogout]);

    useEffect(() => {
        setIsMounted(true);
        if (status === "loading") return;

        const token = localStorage.getItem("token");

        // Sync NextAuth token to localStorage if present
        // @ts-ignore
        if (status === "authenticated" && session?.accessToken && !token) {
            // @ts-ignore
            localStorage.setItem("token", session.accessToken);
        }

        // Initial token check
        if (!token && status === "unauthenticated") {
            router.push("/login");
            return;
        }

        // Check if token is already expired
        if (token && isTokenExpired(token)) {
            handleLogout(true);
            return;
        }

        // Set up periodic token validity check
        const intervalId = setInterval(() => {
            checkTokenValidity();
        }, TOKEN_CHECK_INTERVAL);

        // Set up a timer to logout exactly when token expires
        if (token) {
            const expTime = getTokenExpirationTime(token);
            if (expTime) {
                const timeUntilExpiry = expTime - Date.now();
                if (timeUntilExpiry > 0 && timeUntilExpiry < 24 * 60 * 60 * 1000) {
                    // Only set timeout if expiry is within 24 hours
                    const timeoutId = setTimeout(() => {
                        console.log("Token expired (timeout), logging out...");
                        handleLogout(true);
                    }, timeUntilExpiry);

                    return () => {
                        clearInterval(intervalId);
                        clearTimeout(timeoutId);
                    };
                }
            }
        }

        return () => clearInterval(intervalId);
    }, [router, status, session, checkTokenValidity, handleLogout]);

    // Show loading state while checking authentication
    // This prevents the dashboard from flashing before redirect
    if (!isMounted || status === "loading") {
        return (
            <div className="flex h-screen items-center justify-center bg-gray-50">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
                    <p className="text-sm text-muted-foreground">Loading...</p>
                </div>
            </div>
        );
    }

    // If not authenticated and no token, don't render dashboard
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (status === "unauthenticated" && !token) {
        return (
            <div className="flex h-screen items-center justify-center bg-gray-50">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600" />
                    <p className="text-sm text-muted-foreground">Redirecting to login...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
                <div className="p-6 flex items-center gap-2 border-b border-gray-100">
                    <Image
                        src="/logo-arkaplansız 1.svg"
                        alt="Logo"
                        width={32}
                        height={32}
                        className="h-8 w-auto"
                    />
                    <span className="font-bold text-lg">ScreenshotAPI</span>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    {sidebarItems.map((item) => (
                        <Link key={item.href} href={item.href}>
                            <Button
                                variant={pathname === item.href ? "secondary" : "ghost"}
                                className={cn(
                                    "w-full justify-start gap-2",
                                    pathname === item.href && "bg-blue-50 text-blue-700 hover:bg-blue-100"
                                )}
                            >
                                <item.icon className="h-4 w-4" />
                                {item.label}
                            </Button>
                        </Link>
                    ))}
                </nav>

                <div className="p-4 border-t border-gray-100">
                    <Button variant="ghost" className="w-full justify-start gap-2 text-red-600 hover:bg-red-50 hover:text-red-700" onClick={() => handleLogout(false)}>
                        <LogOut className="h-4 w-4" />
                        Logout
                    </Button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto">
                <div className="p-8">
                    {children}
                </div>
            </main>
        </div>
    );
}
