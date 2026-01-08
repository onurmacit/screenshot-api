"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Camera, FileText, ScrollText, Video } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

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
        <div className="space-y-6">
            {/* Header: Title left, Tabs right */}
            <div className="flex items-center justify-between border-b pb-4">
                {/* Left: Title */}
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Playground</h1>
                    <p className="text-muted-foreground mt-1">
                        Test the API and generate code snippets
                    </p>
                </div>

                {/* Right: Navigation Tabs */}
                <div className="flex gap-2">
                    {playgroundNavItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                            <Link key={item.href} href={item.href}>
                                <Button
                                    variant={isActive ? "default" : "outline"}
                                    className={cn(
                                        "gap-2",
                                        isActive && "bg-blue-600 hover:bg-blue-700"
                                    )}
                                >
                                    <item.icon className="h-4 w-4" />
                                    {item.label}
                                    {item.badge && (
                                        <span className="ml-1 text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded">
                                            {item.badge}
                                        </span>
                                    )}
                                </Button>
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
