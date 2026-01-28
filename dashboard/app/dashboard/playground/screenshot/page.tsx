"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Camera, ChevronRight, Download, Check, X } from "lucide-react";
import { api, authApi, APIKey } from "@/services/api";
import CryptoJS from "crypto-js";
import { CodeSnippet } from "@/components/playground";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export default function ScreenshotPlaygroundPage() {
    // === ESSENTIALS ===
    const [sourceType, setSourceType] = useState<"url" | "html" | "markdown">("url");
    const [url, setUrl] = useState("https://stripe.com");
    const [htmlContent, setHtmlContent] = useState("<h1>Hello World</h1>\n<p>This is a test page rendered from HTML.</p>");
    const [markdownContent, setMarkdownContent] = useState("# Hello World\n\nThis is a **test page** rendered from Markdown.");
    const [signRequests, setSignRequests] = useState(false);
    const [responseType, setResponseType] = useState("binary");
    const [selector, setSelector] = useState("");
    const [jsonResult, setJsonResult] = useState<string | null>(null);

    // === FORCE SCROLL TOGGLE (UI HELPER) ===
    const [forceScroll, setForceScroll] = useState(false);

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
    const [captureBeyondViewport, setCaptureBeyondViewport] = useState(false);
    const [scrollIntoView, setScrollIntoView] = useState("");
    const [scrollAdjustTop, setScrollAdjustTop] = useState(0);

    // === ADVANCED ===
    const [delay, setDelay] = useState(0);
    const [timeout, setTimeout] = useState(30000);
    const [userAgent, setUserAgent] = useState("");
    const [refreshCache, setRefreshCache] = useState(false);

    // === STATE ===
    const [apiKey, setApiKey] = useState("");
    const [userKeys, setUserKeys] = useState<APIKey[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isImageLoaded, setIsImageLoaded] = useState(false);

    // === RESPONSE METADATA ===
    const [responseMetadata, setResponseMetadata] = useState<{
        status: number;
        contentType: string;
        fileSize: number;
        headers: Record<string, string>;
        renderTime?: number;
        width?: number;
        height?: number;
    } | null>(null);

    // Ref to measure right panel height
    const rightPanelRef = useRef<HTMLDivElement>(null);
    const [rightPanelHeight, setRightPanelHeight] = useState<number | null>(null);

    // Measure right panel height on mount and resize
    useEffect(() => {
        const measureHeight = () => {
            if (rightPanelRef.current) {
                setRightPanelHeight(rightPanelRef.current.offsetHeight);
            }
        };

        measureHeight();
        window.addEventListener('resize', measureHeight);
        return () => window.removeEventListener('resize', measureHeight);
    }, []);

    // Load API Keys - auto-select oldest key (ScreenshotOne style)
    useEffect(() => {
        const loadKeys = async () => {
            try {
                const keys = await authApi.listApiKeys();
                // Filter only valid dual-keys (those with access_key)
                const validKeys = keys.filter(k => k.access_key);

                // Sort by created_at ascending (oldest first) - ScreenshotOne uses oldest key
                validKeys.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

                setUserKeys(validKeys);

                // Auto-select oldest key (first after sorting)
                if (validKeys.length > 0) {
                    setApiKey(validKeys[0].access_key || "");
                }
            } catch (error) {
                console.error("Failed to load keys", error);
            }
        };
        loadKeys();
    }, []);


    // Count active options per category
    const blockingCount = [blockAds, blockCookieBanners, blockTrackers, blockChatWidgets].filter(Boolean).length;
    // Scroll options moved to Essentials, so Full Page section count is just fullPage + captureBeyondViewport (if changed from default)
    const fullPageCount = [fullPage, !captureBeyondViewport].filter(Boolean).length;
    const advancedCount = [delay > 0, userAgent, refreshCache].filter(Boolean).length;

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

        // Validate Sign Requests capability
        const selectedKeyObj = userKeys.find(k => k.access_key === apiKey);
        if (signRequests && sourceType === "url") {
            if (!selectedKeyObj?.secret_key) {
                setError("Selected API Key does not have a secret key available for signing.");
                return;
            }
        }

        setIsLoading(true);
        setError(null);
        setResult(null);
        setJsonResult(null);
        setIsImageLoaded(false);
        setResponseMetadata(null);

        try {
            // SHARED PARAMS LOGIC
            const params: Record<string, string | number | boolean> = getCodeSnippetParams();
            // Ensure format consistency
            if (sourceType === "url") params.url = url; // getCodeSnippetParams adds it but let's be sure

            // === SIGNED GET REQUEST FLOW ===
            if (signRequests && sourceType === "url" && selectedKeyObj?.secret_key) {
                // 1. Prepare params for signing (Strings only)
                const signParams: Record<string, string> = {};

                // Add access_key to params if needed? 
                // ScreenshotOne: access_key is query param.
                signParams["access_key"] = apiKey;

                Object.entries(params).forEach(([k, v]) => {
                    signParams[k] = String(v);
                });

                // 2. Sort and Build Query String
                const keys = Object.keys(signParams).sort();
                const queryParts = keys.map(k => `${k}=${signParams[k]}`);
                const queryString = queryParts.join("&");

                // 3. Sign
                const signature = CryptoJS.HmacSHA256(queryString, selectedKeyObj.secret_key!).toString(CryptoJS.enc.Hex);

                // 4. Request (GET)
                // We use api.get but with responseType blob/json
                const endpoint = "/api/v1/renders/"; // FastScreenshot endpoint

                const requestConfig: any = {
                    params: {
                        ...signParams,
                        signature: signature
                    },
                    timeout: 120000,
                };

                if (responseType === "binary") {
                    requestConfig.responseType = 'blob';
                    const response = await api.get(endpoint, requestConfig);

                    const blob = response.data as Blob;
                    const imageUrl = URL.createObjectURL(blob);
                    setResult(imageUrl);

                    // Metadata extraction (same as POST)
                    const processingTime = response.headers['x-processing-time-ms'];
                    const contentLength = response.headers['content-length'];
                    const cacheControl = response.headers['cache-control'];
                    const imageWidth = response.headers['x-image-width'];
                    const imageHeight = response.headers['x-image-height'];

                    setResponseMetadata({
                        status: 200,
                        contentType: blob.type || `image/${format}`,
                        fileSize: blob.size || parseInt(contentLength || '0'),
                        headers: {
                            'cache-control': cacheControl || 'private, no-cache, max-age=0, no-transform',
                            'content-length': (blob.size || contentLength || 0).toString(),
                            'content-type': blob.type || `image/${format}`,
                        },
                        renderTime: processingTime ? parseInt(processingTime) : undefined,
                        width: imageWidth ? parseInt(imageWidth) : width,
                        height: imageHeight ? parseInt(imageHeight) : height,
                    });

                } else {
                    // JSON response
                    const response = await api.get(endpoint, requestConfig);
                    // Logic checks response
                    const resultUrl = response.data.url || response.data.screenshot_url;
                    setResult(resultUrl);
                    setJsonResult(JSON.stringify(response.data, null, 2));

                    // Metadata... (Simplified for brevity)
                    setResponseMetadata({
                        status: 200,
                        contentType: "application/json",
                        fileSize: 0,
                        headers: {},
                        renderTime: response.data.processing_time_ms
                    });
                }

                return;
            }

            // === LEGACY/POST REQUEST FLOW (Original) ===
            const requestBody: Record<string, unknown> = {
                format,
                width,
                height,
                full_page: fullPage,
                capture_beyond_viewport: captureBeyondViewport,
                response_type: responseType,
            };

            // Source
            if (sourceType === "url") {
                requestBody.url = url;
            } else if (sourceType === "html") {
                requestBody.html = htmlContent;
            } else if (sourceType === "markdown") {
                requestBody.markdown = markdownContent;
            }

            // Essentials (Selector & Scroll)
            if (selector.trim()) requestBody.selector = selector.trim();

            // Only send scroll options if forceScroll is enabled
            if (forceScroll) {
                if (scrollIntoView.trim()) requestBody.scroll_into_view = scrollIntoView.trim();
                if (scrollAdjustTop !== 0) requestBody.scroll_adjust_top = scrollAdjustTop;
            }

            // Viewport
            if (deviceScale !== 1) requestBody.device_scale = deviceScale;
            if (darkMode) requestBody.dark_mode = darkMode;

            // Blocking
            if (blockAds) requestBody.block_ads = blockAds;
            if (blockCookieBanners) requestBody.block_cookie_banners = blockCookieBanners;
            if (blockTrackers) requestBody.block_trackers = blockTrackers;
            if (blockChatWidgets) requestBody.block_chat_widgets = blockChatWidgets;

            // Advanced
            if (delay > 0) requestBody.delay = delay;
            if (timeout !== 30000) requestBody.timeout = timeout;
            if (userAgent.trim()) requestBody.user_agent = userAgent.trim();
            if (refreshCache) requestBody.refresh = true;

            // For binary response, we need to get blob
            if (responseType === "binary") {
                const response = await api.post("/api/v1/renders/screenshot", requestBody, {
                    headers: { "X-API-Key": apiKey },
                    responseType: 'blob',
                    timeout: 120000, // 2 minutes timeout
                });

                // Create object URL from blob
                const blob = response.data as Blob;
                const imageUrl = URL.createObjectURL(blob);
                setResult(imageUrl);

                // Capture response metadata from headers
                const processingTime = response.headers['x-processing-time-ms'];
                const contentLength = response.headers['content-length'];
                const cacheControl = response.headers['cache-control'];
                const imageWidth = response.headers['x-image-width'];
                const imageHeight = response.headers['x-image-height'];
                setResponseMetadata({
                    status: 200,
                    contentType: blob.type || `image/${format}`,
                    fileSize: blob.size || parseInt(contentLength || '0'),
                    headers: {
                        'cache-control': cacheControl || 'private, no-cache, max-age=0, no-transform',
                        'content-length': (blob.size || contentLength || 0).toString(),
                        'content-type': blob.type || `image/${format}`,
                    },
                    renderTime: processingTime ? parseInt(processingTime) : undefined,
                    width: imageWidth ? parseInt(imageWidth) : width,
                    height: imageHeight ? parseInt(imageHeight) : height,
                });
            } else {
                // JSON response mode
                const response = await api.post("/api/v1/renders/screenshot", requestBody, {
                    headers: { "X-API-Key": apiKey },
                    timeout: 120000, // 2 minutes timeout
                });

                // New ScreenshotResponse format
                if (response.data.url || response.data.screenshot_url) {
                    const resultUrl = response.data.url || response.data.screenshot_url;
                    setResult(resultUrl);
                    setJsonResult(JSON.stringify(response.data, null, 2));

                    // Capture response metadata
                    const fileSizeBytes = response.data.file_size || 0;
                    setResponseMetadata({
                        status: 200,
                        contentType: `image/${response.data.format || format}`,
                        fileSize: fileSizeBytes,
                        headers: {
                            'cache-control': 'private, no-cache, max-age=0, no-transform',
                            'content-length': fileSizeBytes.toString(),
                            'content-type': `image/${response.data.format || format}`,
                        },
                        renderTime: response.data.processing_time_ms,
                        width: response.data.width || width,
                        height: response.data.height || height,
                    });
                } else if (response.data.id || response.data.job_id) {
                    setError("Job started asynchronously. Check Jobs page.");
                } else {
                    console.error("Unexpected response format:", response.data);
                    setError("Unexpected response format from server");
                }
            }
        } catch (err: any) {
            console.error("Render error:", err);
            const errorMessage = err.response?.data?.detail
                || err.response?.data?.message
                || err.message
                || "An error occurred";
            setError(errorMessage);
        } finally {
            // Always stop loading
            setIsLoading(false);
        }
    };

    const generateCurl = () => {
        const sourceField = sourceType === "url"
            ? `"url": "${url}"`
            : sourceType === "html"
                ? `"html": "${htmlContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`
                : `"markdown": "${markdownContent.replace(/"/g, '\\"').replace(/\n/g, '\\n')}"`;

        // SIGNED REQUEST CURL (GET)
        const selectedKeyObj = userKeys.find(k => k.access_key === apiKey);

        if (signRequests && sourceType === "url" && selectedKeyObj?.secret_key) {
            const params: Record<string, string | number | boolean> = getCodeSnippetParams();
            params.url = url;

            // Signing Logic duplication (Refactor later?)
            const signParams: Record<string, string> = { access_key: apiKey };
            Object.entries(params).forEach(([k, v]) => signParams[k] = String(v));

            const keys = Object.keys(signParams).sort();
            const queryParts = keys.map(k => `${k}=${signParams[k]}`);
            const queryString = queryParts.join("&");
            const signature = CryptoJS.HmacSHA256(queryString, selectedKeyObj.secret_key).toString(CryptoJS.enc.Hex);

            const fullQuery = `${queryString}&signature=${signature}`;

            return `curl -X GET "${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/?${fullQuery}"`;
        }

        // POST REQUEST CURL
        let extras = "";
        if (selector.trim()) extras += `,\n    "selector": "${selector.trim()}"`;

        if (forceScroll) {
            if (scrollIntoView.trim()) extras += `,\n    "scroll_into_view": "${scrollIntoView.trim()}"`;
            if (scrollAdjustTop !== 0) extras += `,\n    "scroll_adjust_top": ${scrollAdjustTop}`;
        }

        if (blockAds) extras += `,\n    "block_ads": true`;
        if (blockCookieBanners) extras += `,\n    "block_cookie_banners": true`;
        if (blockTrackers) extras += `,\n    "block_trackers": true`;
        if (blockChatWidgets) extras += `,\n    "block_chat_widgets": true`;

        if (fullPage) extras += `,\n    "full_page": true`;
        // API Default is True, so only send if explicitly False
        if (captureBeyondViewport === false) extras += `,\n    "capture_beyond_viewport": false`;
        if (responseType !== "binary") extras += `,\n    "response_type": "${responseType}"`;

        if (deviceScale !== 1) extras += `,\n    "device_scale": ${deviceScale}`;
        if (darkMode) extras += `,\n    "dark_mode": true`;

        if (delay > 0) extras += `,\n    "delay": ${delay}`;
        if (timeout !== 30000) extras += `,\n    "timeout": ${timeout}`;
        if (userAgent.trim()) extras += `,\n    "user_agent": "${userAgent.trim()}"`;
        if (refreshCache) extras += `,\n    "refresh": true`;

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
            response_type: responseType,
        };

        if (sourceType === "url") params.url = url;
        else if (sourceType === "html") params.html = htmlContent;
        else params.markdown = markdownContent;

        if (selector.trim()) params.selector = selector;

        if (forceScroll) {
            if (scrollIntoView.trim()) params.scroll_into_view = scrollIntoView;
            if (scrollAdjustTop !== 0) params.scroll_adjust_top = scrollAdjustTop;
        }

        if (blockAds) params.block_ads = true;
        if (blockCookieBanners) params.block_cookie_banners = true;
        if (blockTrackers) params.block_trackers = true;
        if (blockChatWidgets) params.block_chat_widgets = true;

        if (fullPage) params.full_page = true;
        if (!captureBeyondViewport) params.capture_beyond_viewport = false;

        if (darkMode) params.dark_mode = true;
        if (delay > 0) params.delay = delay;
        if (refreshCache) params.refresh = true;

        return params;
    };

    return (
        <>
            {/* Grid Layout - Left panel matches right panel height exactly */}
            <div className="grid grid-cols-1 lg:grid-cols-[384px_1fr] gap-6 lg:items-start">
                {/* Left Panel - Height synced with right panel */}
                <div
                    className="border rounded-xl bg-background overflow-hidden"
                    style={{ height: rightPanelHeight ? `${rightPanelHeight}px` : 'auto' }}
                >
                    {/* Scrollable content area */}
                    <div className="h-full overflow-y-auto p-4 space-y-4">

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
                                        <Label className="font-semibold text-gray-700">Source</Label>
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
                                        <div className="space-y-1">
                                            <Input placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
                                            <p className="text-xs text-muted-foreground">Any website you want to take screenshot of.</p>
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

                                    {/* Sign Requests - Only active for URL source */}
                                    <div className="flex flex-col gap-1 pt-1 pb-1">
                                        <div className="flex items-center gap-2">
                                            <Switch
                                                id="sign-req"
                                                checked={signRequests}
                                                onCheckedChange={setSignRequests}
                                                disabled={sourceType !== "url"}
                                            />
                                            <Label htmlFor="sign-req" className={`font-medium ${sourceType !== "url" ? 'text-gray-400' : ''}`}>
                                                Sign requests
                                            </Label>
                                        </div>
                                        {sourceType !== "url" && (
                                            <p className="text-[10px] text-muted-foreground pl-10">Signed requests available only for URL source</p>
                                        )}
                                        {signRequests && (
                                            <p className="text-[10px] text-blue-500 pl-10">Generates secure Signed URL for public sharing</p>
                                        )}
                                    </div>

                                    {/* Response Type */}
                                    <div className="space-y-2">
                                        <Label className="font-semibold text-gray-700">Response type</Label>
                                        <Select value={responseType} onValueChange={setResponseType}>
                                            <SelectTrigger><SelectValue /></SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="binary">By Format (binary result)</SelectItem>
                                                <SelectItem value="json">JSON (metadata + url)</SelectItem>
                                            </SelectContent>
                                        </Select>
                                        <p className="text-xs text-muted-foreground">By Format (binary or text result, depends on the format)</p>
                                    </div>

                                    {/* Selector */}
                                    <div className="space-y-2">
                                        <Label className="font-semibold text-gray-700">Selector</Label>
                                        <Input placeholder=".some-selector" value={selector} onChange={(e) => setSelector(e.target.value)} />
                                        <p className="text-xs text-muted-foreground">A selector to take screenshot of.</p>
                                    </div>

                                    {/* Toggle: Scroll the element into view (UI Helper) */}
                                    <div className="flex items-center gap-2 mt-2">
                                        <Switch id="force-scroll" checked={forceScroll} onCheckedChange={setForceScroll} />
                                        <Label htmlFor="force-scroll" className="text-sm font-normal text-gray-700">Scroll the element into view before rendering.</Label>
                                    </div>

                                    {/* Scroll Inputs Grid - CONDITIONALLY RENDERED */}
                                    {forceScroll && (
                                        <div className="grid grid-cols-2 gap-4 animate-in fade-in slide-in-from-top-2 duration-300">
                                            <div className="space-y-2">
                                                <Label className="font-semibold text-gray-700">Scroll into view</Label>
                                                <Input placeholder="" value={scrollIntoView} onChange={(e) => setScrollIntoView(e.target.value)} />
                                                <p className="text-xs text-muted-foreground">Selector to scroll into view.</p>
                                            </div>
                                            <div className="space-y-2">
                                                <Label className="font-semibold text-gray-700">Adjust top</Label>
                                                <Input type="number" value={scrollAdjustTop} onChange={(e) => setScrollAdjustTop(Number(e.target.value))} />
                                                <p className="text-xs text-muted-foreground">Once reached the selector, scroll by this amount of pixels.</p>
                                            </div>
                                        </div>
                                    )}

                                    {/* Capture Beyond Viewport & GPU */}
                                    <div className="space-y-3 pt-2">
                                        <div className="flex items-center gap-2">
                                            <Switch id="cbv" checked={captureBeyondViewport} onCheckedChange={setCaptureBeyondViewport} />
                                            <Label htmlFor="cbv" className="text-sm text-blue-600 underline cursor-pointer flex items-center gap-1">
                                                Capture beyond viewport <span className="text-[10px]">↗</span>
                                            </Label>
                                        </div>
                                        <div className="flex items-center gap-2 opacity-50 cursor-not-allowed">
                                            <Switch id="gpu" disabled />
                                            <Label htmlFor="gpu" className="text-sm text-gray-500">Request GPU Rendering <span className="text-blue-500 underline text-xs ml-1">Upgrade to get access to GPU rendering.</span></Label>
                                        </div>
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

                            {/* FULL PAGE */}
                            <AccordionItem value="fullpage" className="border rounded-lg px-4">
                                <AccordionTrigger className="hover:no-underline">
                                    <div className="flex items-center gap-2">
                                        <span className="font-medium">Full Page</span>
                                        {fullPage && (
                                            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">active</span>
                                        )}
                                    </div>
                                </AccordionTrigger>
                                <AccordionContent className="space-y-4 pb-4">
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Full Page Screenshot</Label>
                                            <div className="text-[10px] text-muted-foreground">Capture entire scrollable page height</div>
                                        </div>
                                        <Switch checked={fullPage} onCheckedChange={setFullPage} />
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
                                    <div className="flex items-center justify-between">
                                        <div className="space-y-0.5">
                                            <Label>Bypass Cache</Label>
                                            <div className="text-[10px] text-muted-foreground">Force fresh render, ignore cached result</div>
                                        </div>
                                        <Switch checked={refreshCache} onCheckedChange={setRefreshCache} />
                                    </div>
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

                    </div>
                </div>

                {/* Right Panel - Preview (measured for left panel height) */}
                <div ref={rightPanelRef} className="flex flex-col min-w-0">

                    {/* Monitor Frame - Fixed size, doesn't stretch */}
                    <div className="bg-gradient-to-b from-gray-700 to-gray-900 rounded-2xl p-3 shadow-2xl">
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
                        {/* Screenshot Content Area - 16:9 aspect ratio */}
                        <div className="bg-white rounded-xl mt-2 overflow-hidden aspect-video flex items-center justify-center relative">
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
                            {/* Content Display: JSON or Image */}
                            {jsonResult ? (
                                <div className="w-full h-full overflow-auto bg-[#1e1e1e] p-4 text-left">
                                    <pre className="font-mono text-xs text-green-400 whitespace-pre">
                                        {jsonResult}
                                    </pre>
                                </div>
                            ) : (
                                result && (
                                    <img
                                        src={result}
                                        alt="Screenshot Preview"
                                        className={`w-full h-full object-cover transition-opacity duration-300 ${isLoading ? 'opacity-0' : 'opacity-100'}`}
                                        onLoad={() => setIsImageLoaded(true)}
                                    />
                                )
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

                    {/* Response Bar with Render Button - Button always at right */}
                    <div className="mt-4 flex justify-end items-stretch">
                        {/* Response Info Bar - Expands LEFT from button */}
                        <div
                            className={`
                                flex items-center px-6 text-sm h-11 whitespace-nowrap
                                bg-gray-800 text-white rounded-l-lg
                                transition-all duration-500 ease-out overflow-hidden
                                ${responseMetadata && !isLoading
                                    ? 'flex-1 opacity-100'
                                    : 'max-w-0 opacity-0 px-0'
                                }
                            `}
                        >
                            {/* Inner content wrapper - fades out during loading */}
                            <div className={`flex items-center w-full transition-opacity duration-200 ${isLoading ? 'opacity-0' : 'opacity-100'}`}>
                                {/* LEFT GROUP: Status + Type + Size + Headers */}
                                <div className="flex items-center gap-4 whitespace-nowrap">
                                    {/* Status Badge */}
                                    <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
                                        </span>
                                        200
                                    </span>

                                    {/* Content Type */}
                                    <span className="text-gray-400 font-mono text-xs hidden md:inline">
                                        {responseMetadata?.contentType}
                                    </span>

                                    {/* File Size */}
                                    <span className="text-white font-medium">
                                        {responseMetadata?.fileSize && responseMetadata.fileSize > 1024 * 1024
                                            ? `${(responseMetadata.fileSize / (1024 * 1024)).toFixed(1)} MB`
                                            : responseMetadata?.fileSize
                                                ? `${(responseMetadata.fileSize / 1024).toFixed(0)} KB`
                                                : ''}
                                    </span>

                                    {/* Headers Popover */}
                                    {responseMetadata?.headers && Object.keys(responseMetadata.headers).length > 0 && (
                                        <Popover>
                                            <PopoverTrigger asChild>
                                                <button className="cursor-pointer text-xs text-blue-400 hover:text-blue-300 font-medium px-2.5 py-1 rounded-md hover:bg-gray-700 transition-all border border-gray-600 hover:border-gray-500">
                                                    Headers
                                                </button>
                                            </PopoverTrigger>
                                            <PopoverContent className="w-80 p-3 bg-gray-900 border-gray-700" align="start">
                                                <div className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wider">Response Headers</div>
                                                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                                                    {Object.entries(responseMetadata.headers).map(([key, value]) => (
                                                        <div key={key} className="flex justify-between items-start gap-3 text-xs">
                                                            <span className="text-gray-500 shrink-0">{key}</span>
                                                            <span className="font-mono text-gray-300 text-right break-all">{value}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </PopoverContent>
                                        </Popover>
                                    )}
                                </div>

                                {/* CENTER GROUP: Dimensions + Render Time (pushed towards right) */}
                                <div className="flex-1 flex items-center justify-end gap-4 mr-2">
                                    {/* Dimensions */}
                                    {responseMetadata?.width && responseMetadata?.height && (
                                        <span className="text-gray-300 font-mono text-xs">
                                            {responseMetadata.width} x {responseMetadata.height}
                                        </span>
                                    )}

                                    {/* Render Time */}
                                    {responseMetadata?.renderTime && (
                                        <span className="text-gray-400 font-mono text-xs">
                                            {responseMetadata.renderTime}ms
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Download Button - Clone of Render, shown when result exists */}
                        {result && responseMetadata && !isLoading && (
                            <button
                                onClick={() => {
                                    const link = document.createElement('a');
                                    link.href = result;
                                    link.download = `screenshot-${Date.now()}.${format}`;
                                    link.target = '_blank';
                                    link.click();
                                }}
                                className="min-w-[140px] h-11 px-6 flex items-center justify-center gap-2 font-semibold text-sm bg-gray-800 text-white transition-all duration-200 ease-out hover:bg-gray-700 cursor-pointer"
                            >
                                <Download className="h-4 w-4" />
                                <span>Download</span>
                            </button>
                        )}

                        {/* Render Button - Premium, Fixed Position, Always Right */}
                        <button
                            onClick={handleRender}
                            disabled={isLoading || !apiKey}
                            className={`
                                min-w-[140px] h-11 px-6
                                flex items-center justify-center gap-2
                                font-semibold text-sm
                                bg-gray-800 text-white
                                transition-all duration-200 ease-out
                                disabled:opacity-50 disabled:cursor-not-allowed
                                ${responseMetadata && !isLoading
                                    ? 'rounded-r-lg rounded-l-none'
                                    : 'rounded-lg shadow-lg'
                                }
                                ${isLoading
                                    ? 'cursor-wait'
                                    : 'hover:bg-gray-700 cursor-pointer'
                                }
                            `}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>Rendering</span>
                                </>
                            ) : (
                                <>
                                    <Camera className="h-4 w-4" />
                                    <span>Render</span>
                                </>
                            )}
                        </button>
                    </div>

                    {/* Code Snippet - Full Width */}
                    <div className="mt-6">
                        <CodeSnippet
                            curl={generateCurl()}
                            apiUrl={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/screenshot`}
                            params={getCodeSnippetParams()}
                            apiKey={apiKey || "YOUR_API_KEY"}
                        />
                    </div>

                </div>
            </div>
        </>
    );
}
