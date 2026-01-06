"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Users, Key, Image, BarChart3, Activity } from "lucide-react";

const ADMIN_EMAILS = ["onurmaciit@gmail.com"];

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { data: session, status } = useSession();
    const router = useRouter();
    const [isAdmin, setIsAdmin] = useState(false);

    useEffect(() => {
        if (status === "loading") return;

        const userEmail = session?.user?.email;
        if (!userEmail || !ADMIN_EMAILS.includes(userEmail)) {
            router.push("/dashboard");
            return;
        }
        setIsAdmin(true);
    }, [session, status, router]);

    if (status === "loading" || !isAdmin) {
        return (
            <div className="flex items-center justify-center min-h-[400px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    const navItems = [
        { href: "/dashboard/admin", label: "Overview", icon: BarChart3 },
        { href: "/dashboard/admin/users", label: "Users", icon: Users },
        { href: "/dashboard/admin/api-keys", label: "API Keys", icon: Key },
        { href: "/dashboard/admin/jobs", label: "Jobs", icon: Image },
        { href: "/dashboard/admin/demo-activity", label: "Demo Activity", icon: Activity },
    ];

    return (
        <div className="space-y-6">
            {/* Admin Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
                    <p className="text-gray-600">Manage users, API keys, and jobs</p>
                </div>
                <span className="px-3 py-1 bg-red-100 text-red-800 text-sm font-medium rounded-full">
                    Admin Only
                </span>
            </div>

            {/* Admin Navigation */}
            <nav className="flex gap-2 border-b border-gray-200 pb-4">
                {navItems.map((item) => (
                    <Link
                        key={item.href}
                        href={item.href}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                        <item.icon className="h-4 w-4" />
                        {item.label}
                    </Link>
                ))}
            </nav>

            {/* Content */}
            {children}
        </div>
    );
}
