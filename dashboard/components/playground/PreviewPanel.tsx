"use client";

import { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface PreviewPanelProps {
    isLoading: boolean;
    error: string | null;
    children: ReactNode;
    emptyState?: ReactNode;
}

export function PreviewPanel({
    isLoading,
    error,
    children,
    emptyState,
}: PreviewPanelProps) {
    return (
        <div className="flex-1 bg-gray-100 rounded-lg border border-gray-200 flex flex-col relative overflow-hidden">
            {isLoading && (
                <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex items-center justify-center z-10">
                    <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
                </div>
            )}

            <div className="flex-1 flex items-center justify-center overflow-auto p-4">
                {children || emptyState}
            </div>

            {error && (
                <div className="absolute bottom-4 left-4 right-4 bg-red-100 border border-red-200 text-red-700 p-4 rounded-md">
                    {error}
                </div>
            )}
        </div>
    );
}
