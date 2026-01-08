"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Camera, ChevronRight } from "lucide-react";
import { api } from "@/services/api";
import { CodeSnippet } from "@/components/playground";

export default function ScreenshotPlaygroundPage() {
    // === ESSENTIALS ===
    const [sourceType, setSourceType] = useState<"url" | "html" | "markdown">("url");
    const [url, setUrl] = useState("https://stripe.com");
    const [htmlContent, setHtmlContent] = useState("<h1>Hello World</h1>\n<p>This is a test page rendered from HTML.</p>");
    const [markdownContent, setMarkdownContent] = useState("# Hello World\n\nThis is a **test page** rendered from Markdown.");
    const [selector, setSelector] = useState("");

    // === VIEWPORT & DISPLAY ===
    const [format, setFormat] = useState("png");
    const [width, setWidth] = useState(1920);
    const [height, setHeight] = useState(1080);
    const [deviceScale, setDeviceScale] = useState(1);
    const [darkMode, setDarkMode] = useState(false);

    // === BLOCKING ===
    const [blockAds, setBlockAds] = useState(false);
    const [blockCookieBanners, setBlockCookieBanners] = useState(false);
    const [blockTrackers, setBlockTrackers] = useState(false);
    const [blockChatWidgets, setBlockChatWidgets] = useState(false);

    // === FULL PAGE & CLIP ===
    const [fullPage, setFullPage] = useState(false);
    const [scrollIntoView, setScrollIntoView] = useState("");
    const [scrollAdjustTop, setScrollAdjustTop] = useState(0);

    // === ADVANCED ===
    const [delay, setDelay] = useState(0);
    const [timeout, setTimeout] = useState(30000);
    const [userAgent, setUserAgent] = useState("");

    // === STATE ===
    const [apiKey, setApiKey] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isImageLoaded, setIsImageLoaded] = useState(false);

    // Count active options per category
    const blockingCount = [blockAds, blockCookieBanners, blockTrackers, blockChatWidgets].filter(Boolean).length;
    const fullPageCount = [fullPage, scrollIntoView].filter(Boolean).length;
    const advancedCount = [delay > 0, userAgent].filter(Boolean).length;

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

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
            const requestBody: Record<string, unknown> = {
                format,
                width,
                height,
                full_page: fullPage,
            };

            // Source
            if (sourceType === "url") {
                requestBody.url = url;
            } else if (sourceType === "html") {
                requestBody.html = htmlContent;
            } else if (sourceType === "markdown") {
                requestBody.markdown = markdownContent;
            }

            // Essentials
            if (selector.trim()) requestBody.selector = selector.trim();

            // Viewport
            if (deviceScale !== 1) requestBody.device_scale = deviceScale;
            if (darkMode) requestBody.dark_mode = darkMode;

            // Blocking
            if (blockAds) requestBody.block_ads = blockAds;
            if (blockCookieBanners) requestBody.block_cookie_banners = blockCookieBanners;
            if (blockTrackers) requestBody.block_trackers = blockTrackers;
            if (blockChatWidgets) requestBody.block_chat_widgets = blockChatWidgets;

            // Full Page
            if (scrollIntoView.trim()) requestBody.scroll_into_view = scrollIntoView.trim();
            if (scrollAdjustTop !== 0) requestBody.scroll_adjust_top = scrollAdjustTop;

            // Advanced
            if (delay > 0) requestBody.delay = delay;
            if (timeout !== 30000) requestBody.timeout = timeout;
            if (userAgent.trim()) requestBody.user_agent = userAgent.trim();

            const response = await api.post("/api/v1/renders/screenshot", requestBody, {
                headers: { "X-API-Key": apiKey }
            });

            if (response.data.status === "completed" && response.data.url) {
                setResult(response.data.url);
                // Keep isLoading true - image onLoad will set it to false
            } else if (response.data.id) {
                setError("Job started asynchronously. Check Jobs page.");
                setIsLoading(false);
            } else {
                setError("Failed to generate screenshot");
                setIsLoading(false);
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.message || err.message || "An error occurred");
            setIsLoading(false);
        }
    };

    const generateCurl = () => {
        const sourceField = sourceType === "url"
            ? `"url": "${url}"`
            : sourceType === "html"
                ? `"html": "${htmlContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`
                : `"markdown": "${markdownContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`;

        let extras = "";
        if (selector.trim()) extras += `,\n    "selector": "${selector}"`;
        if (blockAds) extras += `,\n    "block_ads": true`;
        if (blockCookieBanners) extras += `,\n    "block_cookie_banners": true`;
        if (fullPage) extras += `,\n    "full_page": true`;
        if (darkMode) extras += `,\n    "dark_mode": true`;
        if (delay > 0) extras += `,\n    "delay": ${delay}`;

        return `curl -X POST ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/screenshot \\
  -H "X-API-Key: ${apiKey || "YOUR_API_KEY"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    ${sourceField},
    "width": ${width},
    "height": ${height},
    "format": "${format}"${extras}
  }'`;
    };

    return (
        <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-280px)]">
            {/* Controls Panel */}
            <div className="w-full lg:w-96 flex-shrink-0 space-y-4 overflow-y-auto pr-2">
                {/* API Key - Always visible */}
                <Card>
                    <CardContent className="pt-4">
                        <div className="space-y-2">
                            <Label>API Key</Label>
                            <Input
                                type="password"
                                placeholder="Enter your API Key"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                            />
                        </div>
                    </CardContent>
                </Card>

                {/* Accordion Options */}
                <Accordion type="multiple" defaultValue={["essentials", "viewport"]} className="space-y-2">
                    {/* ESSENTIALS - Always expanded by default */}
                    <AccordionItem value="essentials" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline">
                            <div className="flex items-center gap-2">
                                <Camera className="h-4 w-4" />
                                <span className="font-medium">Essentials</span>
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-4 pb-4">
                            {/* Source Type */}
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

                            {/* Source Input */}
                            {sourceType === "url" && (
                                <div className="space-y-2">
                                    <Label>URL</Label>
                                    <Input placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
                                </div>
                            )}
                            {sourceType === "html" && (
                                <div className="space-y-2">
                                    <Label>HTML Content</Label>
                                    <Textarea placeholder="<h1>Hello</h1>" value={htmlContent} onChange={(e) => setHtmlContent(e.target.value)} rows={4} />
                                </div>
                            )}
                            {sourceType === "markdown" && (
                                <div className="space-y-2">
                                    <Label>Markdown Content</Label>
                                    <Textarea placeholder="# Hello" value={markdownContent} onChange={(e) => setMarkdownContent(e.target.value)} rows={4} />
                                </div>
                            )}

                            {/* Selector */}
                            <div className="space-y-2">
                                <Label>Element Selector <span className="text-muted-foreground text-xs">(optional)</span></Label>
                                <Input placeholder=".hero, #main" value={selector} onChange={(e) => setSelector(e.target.value)} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* VIEWPORT & DISPLAY */}
                    <AccordionItem value="viewport" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline">
                            <div className="flex items-center gap-2">
                                <span className="font-medium">Viewport & Display</span>
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-4 pb-4">
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
                            <div className="space-y-2">
                                <Label>Format</Label>
                                <Select value={format} onValueChange={setFormat}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="png">PNG</SelectItem>
                                        <SelectItem value="jpeg">JPEG</SelectItem>
                                        <SelectItem value="webp">WebP</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Device Scale</Label>
                                <Select value={deviceScale.toString()} onValueChange={(v) => setDeviceScale(Number(v))}>
                                    <SelectTrigger><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="1">1x</SelectItem>
                                        <SelectItem value="2">2x (Retina)</SelectItem>
                                        <SelectItem value="3">3x</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="flex items-center justify-between">
                                <Label>Dark Mode</Label>
                                <Switch checked={darkMode} onCheckedChange={setDarkMode} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* BLOCKING */}
                    <AccordionItem value="blocking" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline">
                            <div className="flex items-center gap-2">
                                <span className="font-medium">Blocking</span>
                                {blockingCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{blockingCount} active</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-3 pb-4">
                            <div className="flex items-center justify-between">
                                <Label>Block Ads</Label>
                                <Switch checked={blockAds} onCheckedChange={setBlockAds} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label>Block Cookie Banners</Label>
                                <Switch checked={blockCookieBanners} onCheckedChange={setBlockCookieBanners} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label>Block Trackers</Label>
                                <Switch checked={blockTrackers} onCheckedChange={setBlockTrackers} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label>Block Chat Widgets</Label>
                                <Switch checked={blockChatWidgets} onCheckedChange={setBlockChatWidgets} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* FULL PAGE & CLIP */}
                    <AccordionItem value="fullpage" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline">
                            <div className="flex items-center gap-2">
                                <span className="font-medium">Full Page & Scroll</span>
                                {fullPageCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{fullPageCount} active</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-4 pb-4">
                            <div className="flex items-center justify-between">
                                <Label>Full Page Screenshot</Label>
                                <Switch checked={fullPage} onCheckedChange={setFullPage} />
                            </div>
                            <div className="space-y-2">
                                <Label>Scroll Into View <span className="text-muted-foreground text-xs">(selector)</span></Label>
                                <Input placeholder="#section, .element" value={scrollIntoView} onChange={(e) => setScrollIntoView(e.target.value)} />
                            </div>
                            <div className="space-y-2">
                                <Label>Scroll Adjust Top <span className="text-muted-foreground text-xs">(pixels)</span></Label>
                                <Input type="number" value={scrollAdjustTop} onChange={(e) => setScrollAdjustTop(Number(e.target.value))} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* ADVANCED */}
                    <AccordionItem value="advanced" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline">
                            <div className="flex items-center gap-2">
                                <span className="font-medium">Advanced</span>
                                {advancedCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{advancedCount} active</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-4 pb-4">
                            <div className="space-y-2">
                                <Label>Delay <span className="text-muted-foreground text-xs">(ms)</span></Label>
                                <Input type="number" value={delay} onChange={(e) => setDelay(Number(e.target.value))} placeholder="0" />
                            </div>
                            <div className="space-y-2">
                                <Label>Timeout <span className="text-muted-foreground text-xs">(ms)</span></Label>
                                <Input type="number" value={timeout} onChange={(e) => setTimeout(Number(e.target.value))} />
                            </div>
                            <div className="space-y-2">
                                <Label>User Agent</Label>
                                <Input placeholder="Custom user agent string" value={userAgent} onChange={(e) => setUserAgent(e.target.value)} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>

                {/* Render Button */}
                <Button
                    className="w-full"
                    size="lg"
                    onClick={handleRender}
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Rendering...
                        </>
                    ) : (
                        <>
                            <Camera className="mr-2 h-4 w-4" />
                            Render Screenshot
                        </>
                    )}
                </Button>

                {/* Code Snippet */}
                <CodeSnippet code={generateCurl()} />
            </div>

            {/* Preview Panel */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Monitor Frame */}
                <div className="bg-gradient-to-b from-gray-700 to-gray-900 rounded-2xl p-3 shadow-2xl flex-1 flex flex-col">
                    {/* Browser Chrome */}
                    <div className="bg-gray-800 rounded-xl px-4 py-2.5 flex items-center gap-3">
                        <div className="flex gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-500 hover:bg-red-400 transition-colors cursor-pointer"></div>
                            <div className="w-3 h-3 rounded-full bg-yellow-500 hover:bg-yellow-400 transition-colors cursor-pointer"></div>
                            <div className="w-3 h-3 rounded-full bg-green-500 hover:bg-green-400 transition-colors cursor-pointer"></div>
                        </div>
                        <div className="flex-1 mx-4">
                            <div className="bg-gray-700 rounded-lg px-4 py-1.5 text-sm text-gray-300 truncate">
                                {sourceType === "url" ? url : sourceType === "html" ? "[HTML Content]" : "[Markdown Content]"}
                            </div>
                        </div>
                    </div>
                    {/* Screenshot Content Area - Fixed height to prevent resizing */}
                    <div className="bg-white rounded-xl mt-2 overflow-hidden h-[500px] flex items-center justify-center relative">
                        {/* Loading Overlay - shows during API call and image loading */}
                        {isLoading && (
                            <div className="absolute inset-0 flex items-center justify-center bg-white z-10">
                                <div className="text-center text-gray-400">
                                    <Loader2 className="h-10 w-10 mx-auto mb-3 animate-spin text-blue-500" />
                                    <p className="text-sm font-medium">Rendering screenshot...</p>
                                    <p className="text-xs mt-1 text-gray-300">This may take a few seconds</p>
                                </div>
                            </div>
                        )}

                        {/* Error State */}
                        {error && !isLoading && (
                            <div className="text-center max-w-sm py-12 px-4">
                                <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-3">
                                    <span className="text-red-500 text-xl">!</span>
                                </div>
                                <p className="font-medium text-gray-800 mb-1">Rendering Failed</p>
                                <p className="text-sm text-gray-500">{error}</p>
                            </div>
                        )}

                        {/* Image - renders hidden during loading, visible when ready */}
                        {result && (
                            <img
                                src={result}
                                alt="Screenshot Preview"
                                className={`w-full h-full object-contain transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
                                onLoad={() => {
                                    setIsImageLoaded(true);
                                    setIsLoading(false);
                                }}
                            />
                        )}

                        {/* Empty State */}
                        {!result && !error && !isLoading && (
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

                {/* Download Button */}
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
