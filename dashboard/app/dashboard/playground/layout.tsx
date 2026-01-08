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
        <div className="min-h-screen bg-[#0a0a0f] -m-6 p-6">
            {/* Subtle background glow */}
            <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-b from-[#6155f5]/10 to-transparent blur-[120px] pointer-events-none" />

            <div className="relative z-10 space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white">Playground</h1>
                        <p className="text-sm text-slate-400">
                            Test the API and generate code snippets
                        </p>
                    </div>

                    {/* Tabs */}
                    <div className="flex items-center gap-2">
                        {playgroundNavItems.map((item) => {
                            const isActive = pathname === item.href;
                            return (
                                <Link key={item.href} href={item.href}>
                                    <button
                                        className={`
                                            flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all
                                            ${isActive
                                                ? "bg-[#6155f5]/20 border border-[#6155f5]/50 text-white"
                                                : "bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:border-white/20"
                                            }
                                        `}
                                    >
                                        <item.icon className="h-4 w-4" />
                                        {item.label}
                                        {item.badge && (
                                            <span className="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded font-semibold">
                                                {item.badge}
                                            </span>
                                        )}
                                    </button>
                                </Link>
                            );
                        })}
                    </div>
                </div>

                {/* Content */}
                {children}
            </div>
        </div>
    );
}
