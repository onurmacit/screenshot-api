"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Loader2, Camera } from "lucide-react";
import { api } from "@/services/api";
import { PlaygroundHeader, CodeSnippet, PreviewPanel, DownloadButton } from "@/components/playground";

export default function ScreenshotPlaygroundPage() {
    const [url, setUrl] = useState("https://stripe.com");
    const [apiKey, setApiKey] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Screenshot options
    const [format, setFormat] = useState("png");
    const [width, setWidth] = useState(1920);
    const [height, setHeight] = useState(1080);
    const [fullPage, setFullPage] = useState(false);
    const [blockAds, setBlockAds] = useState(false);
    const [darkMode, setDarkMode] = useState(false);

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await api.post("/api/v1/renders/screenshot", {
                url,
                format,
                width,
                height,
                full_page: fullPage,
            }, {
                headers: {
                    "X-API-Key": apiKey
                }
            });

            if (response.data.status === "completed" && response.data.url) {
                setResult(response.data.url);
            } else if (response.data.id) {
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
        <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-280px)]">
            {/* Controls Panel */}
            <div className="w-full lg:w-96 flex-shrink-0 space-y-6 overflow-y-auto pr-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Camera className="h-5 w-5" />
                            Screenshot Options
                        </CardTitle>
                        <CardDescription>Configure screenshot parameters</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <PlaygroundHeader
                            apiKey={apiKey}
                            onApiKeyChange={setApiKey}
                            url={url}
                            onUrlChange={setUrl}
                        />

                        <Separator />

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

                <CodeSnippet code={generateCurl()} title="cURL Command" />
            </div>

            {/* Preview Panel */}
            <PreviewPanel
                isLoading={isLoading}
                error={error}
                emptyState={
                    <div className="text-center text-gray-400">
                        <Camera className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Click "Render Screenshot" to preview</p>
                    </div>
                }
            >
                {result && (
                    <>
                        <img src={result} alt="Screenshot Preview" className="max-w-full max-h-full shadow-lg rounded-lg" />
                        <DownloadButton url={result} label="Download Screenshot" />
                    </>
                )}
            </PreviewPanel>
        </div>
    );
}
