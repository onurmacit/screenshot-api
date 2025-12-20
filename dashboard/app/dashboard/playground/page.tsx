"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Loader2, Copy, Check } from "lucide-react";
import { api } from "@/services/api";

export default function PlaygroundPage() {
    const [url, setUrl] = useState("https://stripe.com");
    const [format, setFormat] = useState("png");
    const [width, setWidth] = useState(1920);
    const [height, setHeight] = useState(1080);
    const [fullPage, setFullPage] = useState(false);
    const [blockAds, setBlockAds] = useState(false);
    const [darkMode, setDarkMode] = useState(false);

    const [apiKey, setApiKey] = useState("");

    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            // We need to pass the API Key in header
            // Since our api client uses JWT automatically, we need to override/add header

            const response = await api.post("/api/v1/renders/screenshot", {
                url,
                format,
                width,
                height,
                full_page: fullPage,
                // block_ads: blockAds, // Check if API supports this yet, if not, ignore
                // dark_mode: darkMode,
            }, {
                headers: {
                    "X-API-Key": apiKey
                }
            });

            if (response.data.status === "completed" && response.data.url) {
                setResult(response.data.url);
            } else if (response.data.id) {
                // Async job started
                setError("Job started asynchronously. Check Jobs page.");
            } else {
                setError("Failed to generate screenshot");
            }

        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.message || err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    const generateCurl = () => {
        return `curl -X POST ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/screenshot \\
  -H "X-API-Key: ${apiKey || "YOUR_API_KEY"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "${url}",
    "width": ${width},
    "height": ${height},
    "format": "${format}",
    "full_page": ${fullPage}
  }'`;
    };

    return (
        <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-120px)]">
            {/* Controls Panel */}
            <div className="w-full lg:w-96 flex-shrink-0 space-y-6 overflow-y-auto pr-2">
                <Card>
                    <CardHeader>
                        <CardTitle>Configuration</CardTitle>
                        <CardDescription>Customize your screenshot parameters</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label>API Key</Label>
                            <Input
                                type="password"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="sk_..."
                            />
                        </div>

                        <Separator />

                        <div className="space-y-2">
                            <Label>URL</Label>
                            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Format</Label>
                                <Select value={format} onValueChange={setFormat}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="png">PNG</SelectItem>
                                        <SelectItem value="jpeg">JPEG</SelectItem>
                                        <SelectItem value="webp">WebP</SelectItem>
                                        <SelectItem value="pdf">PDF</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Width</Label>
                                <Input type="number" value={width} onChange={(e) => setWidth(Number(e.target.value))} />
                            </div>
                            <div className="space-y-2">
                                <Label>Height</Label>
                                <Input type="number" value={height} onChange={(e) => setHeight(Number(e.target.value))} />
                            </div>
                        </div>

                        <Separator />

                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="fullPage">Full Page</Label>
                                <Switch id="fullPage" checked={fullPage} onCheckedChange={setFullPage} />
                            </div>

                            <div className="flex items-center justify-between">
                                <Label htmlFor="blockAds" className="text-gray-400 cursor-not-allowed">Block Ads (Soon)</Label>
                                <Switch id="blockAds" checked={blockAds} onCheckedChange={setBlockAds} disabled />
                            </div>

                            <div className="flex items-center justify-between">
                                <Label htmlFor="darkMode" className="text-gray-400 cursor-not-allowed">Dark Mode (Soon)</Label>
                                <Switch id="darkMode" checked={darkMode} onCheckedChange={setDarkMode} disabled />
                            </div>
                        </div>

                        <Button className="w-full" onClick={handleRender} disabled={isLoading}>
                            {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Render Screenshot
                        </Button>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>Code Snippet</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-slate-950 text-slate-50 p-4 rounded-lg text-xs overflow-x-auto">
                            <code>{generateCurl()}</code>
                        </pre>
                    </CardContent>
                </Card>
            </div>

            {/* Preview Panel */}
            <div className="flex-1 bg-gray-100 rounded-lg border border-gray-200 flex items-center justify-center relative overflow-hidden">
                {isLoading && (
                    <div className="absolute inset-0 bg-white/50 backdrop-blur-sm flex items-center justify-center z-10">
                        <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
                    </div>
                )}

                {result ? (
                    format === 'pdf' ? (
                        <iframe src={result} className="w-full h-full" />
                    ) : (
                        <img src={result} alt="Screenshot Preview" className="max-w-full max-h-full shadow-lg" />
                    )
                ) : (
                    <div className="text-center text-gray-400">
                        <p>Click "Render Screenshot" to preview</p>
                    </div>
                )}

                {error && (
                    <div className="absolute bottom-4 left-4 right-4 bg-red-100 border border-red-200 text-red-700 p-4 rounded-md">
                        {error}
                    </div>
                )}
            </div>
        </div>
    );
}
