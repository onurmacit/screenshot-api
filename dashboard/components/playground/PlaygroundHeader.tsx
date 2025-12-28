"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

interface PlaygroundHeaderProps {
    apiKey: string;
    onApiKeyChange: (value: string) => void;
    url: string;
    onUrlChange: (value: string) => void;
}

export function PlaygroundHeader({
    apiKey,
    onApiKeyChange,
    url,
    onUrlChange,
}: PlaygroundHeaderProps) {
    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <Label>API Key</Label>
                <Input
                    type="password"
                    value={apiKey}
                    onChange={(e) => onApiKeyChange(e.target.value)}
                    placeholder="sk_..."
                />
            </div>

            <Separator />

            <div className="space-y-2">
                <Label>URL</Label>
                <Input
                    value={url}
                    onChange={(e) => onUrlChange(e.target.value)}
                    placeholder="https://example.com"
                />
            </div>
        </div>
    );
}
