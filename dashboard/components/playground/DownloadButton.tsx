"use client";

import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

interface DownloadButtonProps {
    url: string;
    label?: string;
}

export function DownloadButton({ url, label = "Download" }: DownloadButtonProps) {
    return (
        <div className="p-4 border-t bg-white">
            <a href={url} target="_blank" rel="noopener noreferrer" download>
                <Button variant="outline" className="w-full">
                    <Download className="mr-2 h-4 w-4" />
                    {label}
                </Button>
            </a>
        </div>
    );
}
