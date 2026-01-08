"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Camera, Settings2, Shield, Maximize, Sliders } from "lucide-react";
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

    // Count active options per category
    const viewportCount = [deviceScale !== 1, darkMode].filter(Boolean).length;
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

    // Get params for CodeSnippet
    const getCodeSnippetParams = (): Record<string, string | number | boolean> => {
        const params: Record<string, string | number | boolean> = {
            width,
            height,
            format,
        };

        if (sourceType === "url") params.url = url;
        else if (sourceType === "html") params.html = htmlContent;
        else params.markdown = markdownContent;

        if (selector.trim()) params.selector = selector;
        if (blockAds) params.block_ads = true;
        if (blockCookieBanners) params.block_cookie_banners = true;
        if (blockTrackers) params.block_trackers = true;
        if (blockChatWidgets) params.block_chat_widgets = true;
        if (fullPage) params.full_page = true;
        if (darkMode) params.dark_mode = true;
        if (delay > 0) params.delay = delay;

        return params;
    };

    return (
        <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-180px)]">
            {/* Left Panel - Controls */}
            <div className="w-full lg:w-[420px] flex-shrink-0 flex flex-col gap-4 overflow-y-auto pr-2">

                {/* Quick Start Card - Most important, always visible */}
                <Card className="border-2 border-blue-100 dark:border-blue-900/50">
                    <CardContent className="pt-5 space-y-4">
                        {/* Source Type Tabs */}
                        <Tabs value={sourceType} onValueChange={(v) => setSourceType(v as "url" | "html" | "markdown")} className="w-full">
                            <TabsList className="grid w-full grid-cols-3">
                                <TabsTrigger value="url">URL</TabsTrigger>
                                <TabsTrigger value="html">HTML</TabsTrigger>
                                <TabsTrigger value="markdown">Markdown</TabsTrigger>
                            </TabsList>
                        </Tabs>

                        {/* Source Input */}
                        {sourceType === "url" && (
                            <div className="space-y-1.5">
                                <Label className="text-xs text-muted-foreground">Website URL</Label>
                                <Input
                                    placeholder="https://example.com"
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    className="h-10"
                                />
                            </div>
                        )}
                        {sourceType === "html" && (
                            <div className="space-y-1.5">
                                <Label className="text-xs text-muted-foreground">HTML Content</Label>
                                <Textarea placeholder="<h1>Hello</h1>" value={htmlContent} onChange={(e) => setHtmlContent(e.target.value)} rows={3} />
                            </div>
                        )}
                        {sourceType === "markdown" && (
                            <div className="space-y-1.5">
                                <Label className="text-xs text-muted-foreground">Markdown Content</Label>
                                <Textarea placeholder="# Hello" value={markdownContent} onChange={(e) => setMarkdownContent(e.target.value)} rows={3} />
                            </div>
                        )}

                        {/* API Key */}
                        <div className="space-y-1.5">
                            <Label className="text-xs text-muted-foreground">API Key</Label>
                            <Input
                                type="password"
                                placeholder="sk_live_..."
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="h-10"
                            />
                        </div>

                        {/* Render Button */}
                        <Button
                            className="w-full h-11 bg-blue-600 hover:bg-blue-700"
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
                    </CardContent>
                </Card>

                {/* Code Snippet - Second priority for developers */}
                <CodeSnippet
                    curl={generateCurl()}
                    apiUrl={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/screenshot`}
                    params={getCodeSnippetParams()}
                    apiKey={apiKey || "YOUR_API_KEY"}
                />

                {/* Advanced Options - Collapsed by default */}
                <Accordion type="multiple" className="space-y-2">
                    {/* VIEWPORT & DISPLAY */}
                    <AccordionItem value="viewport" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline py-3">
                            <div className="flex items-center gap-2">
                                <Settings2 className="h-4 w-4 text-slate-500" />
                                <span className="text-sm font-medium">Viewport & Display</span>
                                {viewportCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{viewportCount}</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-3 pb-4">
                            <div className="grid grid-cols-3 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs">Width</Label>
                                    <Input type="number" value={width} onChange={(e) => setWidth(Number(e.target.value))} className="h-9" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Height</Label>
                                    <Input type="number" value={height} onChange={(e) => setHeight(Number(e.target.value))} className="h-9" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Format</Label>
                                    <Select value={format} onValueChange={setFormat}>
                                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="png">PNG</SelectItem>
                                            <SelectItem value="jpeg">JPEG</SelectItem>
                                            <SelectItem value="webp">WebP</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs">Device Scale</Label>
                                    <Select value={deviceScale.toString()} onValueChange={(v) => setDeviceScale(Number(v))}>
                                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="1">1x</SelectItem>
                                            <SelectItem value="2">2x (Retina)</SelectItem>
                                            <SelectItem value="3">3x</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-center justify-between pt-5">
                                    <Label className="text-xs">Dark Mode</Label>
                                    <Switch checked={darkMode} onCheckedChange={setDarkMode} />
                                </div>
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Element Selector <span className="text-muted-foreground">(optional)</span></Label>
                                <Input placeholder=".hero, #main" value={selector} onChange={(e) => setSelector(e.target.value)} className="h-9" />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* BLOCKING */}
                    <AccordionItem value="blocking" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline py-3">
                            <div className="flex items-center gap-2">
                                <Shield className="h-4 w-4 text-slate-500" />
                                <span className="text-sm font-medium">Blocking</span>
                                {blockingCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{blockingCount}</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-2 pb-4">
                            <div className="flex items-center justify-between">
                                <Label className="text-sm">Block Ads</Label>
                                <Switch checked={blockAds} onCheckedChange={setBlockAds} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label className="text-sm">Block Cookie Banners</Label>
                                <Switch checked={blockCookieBanners} onCheckedChange={setBlockCookieBanners} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label className="text-sm">Block Trackers</Label>
                                <Switch checked={blockTrackers} onCheckedChange={setBlockTrackers} />
                            </div>
                            <div className="flex items-center justify-between">
                                <Label className="text-sm">Block Chat Widgets</Label>
                                <Switch checked={blockChatWidgets} onCheckedChange={setBlockChatWidgets} />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* FULL PAGE & SCROLL */}
                    <AccordionItem value="fullpage" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline py-3">
                            <div className="flex items-center gap-2">
                                <Maximize className="h-4 w-4 text-slate-500" />
                                <span className="text-sm font-medium">Full Page & Scroll</span>
                                {fullPageCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{fullPageCount}</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-3 pb-4">
                            <div className="flex items-center justify-between">
                                <Label className="text-sm">Full Page Screenshot</Label>
                                <Switch checked={fullPage} onCheckedChange={setFullPage} />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Scroll Into View <span className="text-muted-foreground">(selector)</span></Label>
                                <Input placeholder="#section, .element" value={scrollIntoView} onChange={(e) => setScrollIntoView(e.target.value)} className="h-9" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Scroll Adjust Top <span className="text-muted-foreground">(pixels)</span></Label>
                                <Input type="number" value={scrollAdjustTop} onChange={(e) => setScrollAdjustTop(Number(e.target.value))} className="h-9" />
                            </div>
                        </AccordionContent>
                    </AccordionItem>

                    {/* ADVANCED */}
                    <AccordionItem value="advanced" className="border rounded-lg px-4">
                        <AccordionTrigger className="hover:no-underline py-3">
                            <div className="flex items-center gap-2">
                                <Sliders className="h-4 w-4 text-slate-500" />
                                <span className="text-sm font-medium">Advanced</span>
                                {advancedCount > 0 && (
                                    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{advancedCount}</span>
                                )}
                            </div>
                        </AccordionTrigger>
                        <AccordionContent className="space-y-3 pb-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <Label className="text-xs">Delay <span className="text-muted-foreground">(ms)</span></Label>
                                    <Input type="number" value={delay} onChange={(e) => setDelay(Number(e.target.value))} placeholder="0" className="h-9" />
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-xs">Timeout <span className="text-muted-foreground">(ms)</span></Label>
                                    <Input type="number" value={timeout} onChange={(e) => setTimeout(Number(e.target.value))} className="h-9" />
                                </div>
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">User Agent</Label>
                                <Input placeholder="Custom user agent string" value={userAgent} onChange={(e) => setUserAgent(e.target.value)} className="h-9" />
                            </div>
                        </AccordionContent>
                    </AccordionItem>
                </Accordion>
            </div>

            {/* Right Panel - Preview */}
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

                    {/* Screenshot Content Area */}
                    <div className="bg-white rounded-xl mt-2 overflow-hidden flex-1 flex items-center justify-center relative">
                        {/* Loading Overlay */}
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

                        {/* Image */}
                        {result && (
                            <img
                                src={result}
                                alt="Screenshot Preview"
                                className={`w-full h-full object-contain transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
                            />
                        )}

                        {/* Empty State */}
                        {!result && !error && !isLoading && (
                            <div className="text-center text-gray-400 py-16">
                                <Camera className="h-12 w-12 mx-auto mb-4 opacity-30" />
                                <p className="text-sm font-medium">No screenshot yet</p>
                                <p className="text-xs mt-1 text-gray-300">Click "Render Screenshot" to generate</p>
                            </div>
                        )}
                    </div>
                </div>

                {/* Monitor Stand */}
                <div className="flex justify-center mt-0">
                    <div className="w-16 h-5 bg-gradient-to-b from-gray-700 to-gray-800 rounded-b-sm"></div>
                </div>
                <div className="flex justify-center">
                    <div className="w-28 h-2 bg-gradient-to-b from-gray-600 to-gray-700 rounded-b-lg shadow-md"></div>
                </div>

                {/* Download Button */}
                {result && !isLoading && (
                    <div className="mt-4 flex justify-center">
                        <Button
                            variant="outline"
                            size="lg"
                            onClick={() => {
                                const link = document.createElement('a');
                                link.href = result;
                                link.download = `screenshot-${Date.now()}.${format}`;
                                link.target = '_blank';
                                link.click();
                            }}
                        >
                            <svg className="mr-2 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Download {format.toUpperCase()}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
