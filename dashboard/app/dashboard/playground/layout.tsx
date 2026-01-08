"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Camera, FileText, ScrollText, Video } from "lucide-react";

const playgroundNavItems = [
    { icon: Camera, label: "Screenshot", href: "/dashboard/playground/screenshot" },
    { icon: FileText, label: "PDF", href: "/dashboard/playground/pdf" },
    { icon: ScrollText, label: "Scrolling", href: "/dashboard/playground/scrolling", badge: "Soon" },
    { icon: Video, label: "Video", href: "/dashboard/playground/video", badge: "Soon" },
];

export default function PlaygroundLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();

    return (
        <div className="space-y-4">
            {/* Compact Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Playground</h1>
                    <p className="text-muted-foreground text-sm">
                        Test the API and generate code snippets
                    </p>
                </div>
                {/* Tabs in header row */}
                <div className="flex gap-1.5">
                    {playgroundNavItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link key={item.href} href={item.href}>
                                <button
                                    className={`
                                        flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all
                                        ${isActive
                                            ? "bg-blue-600 text-white shadow-sm"
                                            : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
                                        }
                                    `}
                                >
                                    <item.icon className="h-4 w-4" />
                                    {item.label}
                                    {item.badge && (
                                        <span className="ml-0.5 text-[10px] bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">
                                            {item.badge}
                                        </span>
                                    )}
                                </button>
                            </Link>
                        );
                    })}
                </div>
            </div>

            {/* Page Content */}
            {children}
        </div>
    );
}
