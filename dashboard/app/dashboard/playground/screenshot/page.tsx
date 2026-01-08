"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Camera } from "lucide-react";
import { api } from "@/services/api";
import { PlaygroundHeader, CodeSnippet } from "@/components/playground";

export default function ScreenshotPlaygroundPage() {
    // Source type and content
    const [sourceType, setSourceType] = useState<"url" | "html" | "markdown">("url");
    const [url, setUrl] = useState("https://stripe.com");
    const [htmlContent, setHtmlContent] = useState("<h1>Hello World</h1>\n<p>This is a test page rendered from HTML.</p>");
    const [markdownContent, setMarkdownContent] = useState("# Hello World\n\nThis is a **test page** rendered from Markdown.");

    const [apiKey, setApiKey] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isImageLoaded, setIsImageLoaded] = useState(false);

    // Screenshot options
    const [format, setFormat] = useState("png");
    const [width, setWidth] = useState(1920);
    const [height, setHeight] = useState(1080);
    const [fullPage, setFullPage] = useState(false);
    const [selector, setSelector] = useState("");
    const [blockAds, setBlockAds] = useState(false);
    const [darkMode, setDarkMode] = useState(false);

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

        // Validate source content
        if (sourceType === "url" && !url.trim()) {
            setError("Please enter a URL");
            return;
        }
        if (sourceType === "html" && !htmlContent.trim()) {
            setError("Please enter HTML content");
            return;
        }
        if (sourceType === "markdown" && !markdownContent.trim()) {
            setError("Please enter Markdown content");
            return;
        }

        setIsLoading(true);
        setError(null);
        setResult(null);
        setIsImageLoaded(false);

        try {
            // Build request body based on source type
            const requestBody: Record<string, unknown> = {
                format,
                width,
                height,
                full_page: fullPage,
            };

            if (sourceType === "url") {
                requestBody.url = url;
            } else if (sourceType === "html") {
                requestBody.html = htmlContent;
            } else if (sourceType === "markdown") {
                requestBody.markdown = markdownContent;
            }

            // Add selector if provided
            if (selector.trim()) {
                requestBody.selector = selector.trim();
            }

            const response = await api.post("/api/v1/renders/screenshot", requestBody, {
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
        const sourceField = sourceType === "url"
            ? `"url": "${url}"`
            : sourceType === "html"
                ? `"html": "${htmlContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`
                : `"markdown": "${markdownContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`;

        const selectorField = selector.trim() ? `,\n    "selector": "${selector}"` : "";

        return `curl -X POST ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/screenshot \\
  -H "X-API-Key: ${apiKey || "YOUR_API_KEY"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    ${sourceField},
    "width": ${width},
    "height": ${height},
    "format": "${format}",
    "full_page": ${fullPage}${selectorField}
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
                        {/* API Key */}
                        <div className="space-y-2">
                            <Label>API Key</Label>
                            <Input
                                type="password"
                                placeholder="Enter your API Key"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </div>

                        {/* Source Type Tabs */}
                        <div className="space-y-2">
                            <Label>Source</Label>
                            <Tabs value={sourceType} onValueChange={(v) => setSourceType(v as "url" | "html" | "markdown")} className="w-full">
                                <TabsList className="grid w-full grid-cols-3">
                                    <TabsTrigger value="url">URL</TabsTrigger>
                                    <TabsTrigger value="html">HTML</TabsTrigger>
                                    <TabsTrigger value="markdown">Markdown</TabsTrigger>
                                </TabsList>
                            </Tabs>
                        </div>

                        {/* Conditional Input Based on Source Type */}
                        {sourceType === "url" && (
                            <div className="space-y-2">
                                <Label>URL</Label>
                                <Input
                                    placeholder="https://example.com"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                />
                            </div>
                        )}
                        {sourceType === "html" && (
                            <div className="space-y-2">
                                <Label>HTML Content</Label>
                                <Textarea
                                    placeholder="<h1>Hello World</h1>"
                                    value={htmlContent}
                                    onChange={(e) => setHtmlContent(e.target.value)}
                                    rows={4}
                                />
                            </div>
                        )}
                        {sourceType === "markdown" && (
                            <div className="space-y-2">
                                <Label>Markdown Content</Label>
                                <Textarea
                                    placeholder="# Hello World"
                                    value={markdownContent}
                                    onChange={(e) => setMarkdownContent(e.target.value)}
                                    rows={4}
                                />
                            </div>
                        )}

                        {/* Selector (optional) */}
                        <div className="space-y-2">
                            <Label>Element Selector <span className="text-muted-foreground text-xs">(optional)</span></Label>
                            <Input
                                placeholder=".hero, #main"
                                value={selector}
                                onChange={(e) => setSelector(e.target.value)}
                            />
                        </div>

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

            {/* Preview Panel - Full Width Monitor */}
            <div className="flex-1 flex flex-col min-h-[500px]">
                {/* Monitor Frame - Always Visible */}
                <div className="flex-1 flex flex-col">
                    {/* Monitor Screen */}
                    <div className="bg-gray-900 rounded-2xl p-2 shadow-2xl flex-1 flex flex-col">
                        {/* Browser Chrome */}
                        <div className="bg-gray-800 rounded-xl px-4 py-2.5 flex items-center gap-3">
                            <div className="flex gap-2">
                                <div className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400 transition-colors cursor-pointer"></div>
                                <div className="w-3 h-3 rounded-full bg-yellow-500 hover:bg-yellow-400 transition-colors cursor-pointer"></div>
                                <div className="w-3 h-3 rounded-full bg-green-500 hover:bg-green-400 transition-colors cursor-pointer"></div>
                            </div>
                            <div className="flex-1 mx-4">
                                <div className="bg-gray-700 rounded-lg px-4 py-1.5 text-sm text-gray-300 truncate">
                                    {url}
                                </div>
                            </div>
                        </div>
                        {/* Screenshot Content Area */}
                        <div className="bg-white rounded-xl mt-2 overflow-hidden flex-1 flex items-center justify-center min-h-[400px]">
                            {isLoading ? (
                                <div className="text-center text-gray-400 py-16">
                                    <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-blue-500" />
                                    <p className="text-sm font-medium">Rendering screenshot...</p>
                                    <p className="text-xs mt-1 text-gray-300">This may take a few seconds</p>
                                </div>
                            ) : error ? (
                                <div className="text-center max-w-sm py-12 px-4">
                                    <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-3">
                                        <span className="text-red-500 text-xl">!</span>
                                    </div>
                                    <p className="font-medium text-gray-800 mb-1">Rendering Failed</p>
                                    <p className="text-sm text-gray-500">{error}</p>
                                </div>
                            ) : result ? (
                                <>
                                    {!isImageLoaded && (
                                        <div className="text-center text-gray-400 py-16">
                                            <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-blue-500" />
                                            <p className="text-sm font-medium">Loading image...</p>
                                        </div>
                                    )}
                                    <img
                                        src={result}
                                        alt="Screenshot Preview"
                                        className={`w-full h-full object-contain transition-opacity duration-200 ${isImageLoaded ? 'opacity-100' : 'opacity-0 absolute'}`}
                                        onLoad={() => setIsImageLoaded(true)}
                                    />
                                </>
                            ) : (
                                <div className="text-center text-gray-400 py-16">
                                    <Camera className="h-10 w-10 mx-auto mb-3 opacity-40" />
                                    <p className="text-sm font-medium">No screenshot yet</p>
                                    <p className="text-xs mt-1 text-gray-300">Click "Render Screenshot" to generate</p>
                                </div>
                            )}
                        </div>
                    </div>
                    {/* Monitor Stand */}
                    <div className="flex justify-center">
                        <div className="w-16 h-5 bg-gradient-to-b from-gray-700 to-gray-800 rounded-b-sm"></div>
                    </div>
                    <div className="flex justify-center">
                        <div className="w-28 h-2 bg-gradient-to-b from-gray-600 to-gray-700 rounded-b-lg shadow-md"></div>
                    </div>
                </div>

                {/* Download Button - Outside Frame, Bottom Right */}
                {result && (
                    <div className="mt-4 flex justify-end">
                        <button
                            onClick={() => {
                                const link = document.createElement('a');
                                link.href = result;
                                link.download = `screenshot-${Date.now()}.${format}`;
                                link.target = '_blank';
                                link.click();
                            }}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-gray-900 hover:bg-gray-800 text-white rounded-lg font-medium text-sm transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Download {format.toUpperCase()}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
