"use client";

import { useState } from "react";
import { Loader2, Camera, Settings2, Shield, Maximize, Sliders, Copy, Check, Link, Terminal, Code, FileCode } from "lucide-react";
import { api } from "@/services/api";

type TabType = "url" | "curl" | "javascript" | "python";

const CODE_TABS: { id: TabType; label: string; icon: typeof Link }[] = [
    { id: "url", label: "URL", icon: Link },
    { id: "curl", label: "cURL", icon: Terminal },
    { id: "javascript", label: "JS", icon: Code },
    { id: "python", label: "Python", icon: FileCode },
];

export default function ScreenshotPlaygroundPage() {
    // === SOURCE ===
    const [sourceType, setSourceType] = useState<"url" | "html" | "markdown">("url");
    const [url, setUrl] = useState("stripe.com");
    const [htmlContent, setHtmlContent] = useState("<h1>Hello World</h1>\n<p>This is a test page.</p>");
    const [markdownContent, setMarkdownContent] = useState("# Hello World\n\nThis is a **test page**.");
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

    // === FULL PAGE ===
    const [fullPage, setFullPage] = useState(false);

    // === ADVANCED ===
    const [delay, setDelay] = useState(0);

    // === STATE ===
    const [apiKey, setApiKey] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // === CODE SNIPPET ===
    const [activeCodeTab, setActiveCodeTab] = useState<TabType>("curl");
    const [copied, setCopied] = useState(false);

    // === ADVANCED OPTIONS PANEL ===
    const [showAdvanced, setShowAdvanced] = useState(false);

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

        const source = sourceType === "url" ? url : sourceType === "html" ? htmlContent : markdownContent;
        if (!source.trim()) {
            setError(`Please enter ${sourceType.toUpperCase()} content`);
            return;
        }

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const requestBody: Record<string, unknown> = { format, width, height, full_page: fullPage };

            if (sourceType === "url") {
                let targetUrl = url.trim();
                if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
                    targetUrl = "https://" + targetUrl;
                }
                requestBody.url = targetUrl;
            } else if (sourceType === "html") {
                requestBody.html = htmlContent;
            } else {
                requestBody.markdown = markdownContent;
            }

            if (selector.trim()) requestBody.selector = selector.trim();
            if (deviceScale !== 1) requestBody.device_scale = deviceScale;
            if (darkMode) requestBody.dark_mode = darkMode;
            if (blockAds) requestBody.block_ads = blockAds;
            if (blockCookieBanners) requestBody.block_cookie_banners = blockCookieBanners;
            if (delay > 0) requestBody.delay = delay;

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
            setError(err.response?.data?.message || err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    // Generate code snippets
    const getUrlCode = () => {
        let targetUrl = url.trim();
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            targetUrl = "https://" + targetUrl;
        }
        const params = new URLSearchParams();
        params.set("api_key", apiKey || "YOUR_API_KEY");
        params.set("url", targetUrl);
        params.set("width", width.toString());
        params.set("height", height.toString());
        params.set("format", format);
        return `${process.env.NEXT_PUBLIC_API_URL || "https://api.screenshotbeam.com"}/api/v1/renders/screenshot?${params.toString()}`;
    };

    const getCurlCode = () => {
        let targetUrl = url.trim();
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            targetUrl = "https://" + targetUrl;
        }
        return `curl -X POST ${process.env.NEXT_PUBLIC_API_URL || "https://api.screenshotbeam.com"}/api/v1/renders/screenshot \\
  -H "X-API-Key: ${apiKey || "YOUR_API_KEY"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "${targetUrl}",
    "width": ${width},
    "height": ${height},
    "format": "${format}"
  }'`;
    };

    const getJsCode = () => {
        let targetUrl = url.trim();
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            targetUrl = "https://" + targetUrl;
        }
        return `const response = await fetch('${process.env.NEXT_PUBLIC_API_URL || "https://api.screenshotbeam.com"}/api/v1/renders/screenshot', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': '${apiKey || "YOUR_API_KEY"}'
  },
  body: JSON.stringify({
    url: '${targetUrl}',
    width: ${width},
    height: ${height},
    format: '${format}'
  })
});

const data = await response.json();
console.log(data.url);`;
    };

    const getPythonCode = () => {
        let targetUrl = url.trim();
        if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
            targetUrl = "https://" + targetUrl;
        }
        return `import requests

response = requests.post(
    '${process.env.NEXT_PUBLIC_API_URL || "https://api.screenshotbeam.com"}/api/v1/renders/screenshot',
    headers={
        'Content-Type': 'application/json',
        'X-API-Key': '${apiKey || "YOUR_API_KEY"}'
    },
    json={
        'url': '${targetUrl}',
        'width': ${width},
        'height': ${height},
        'format': '${format}'
    }
)

data = response.json()
print(data['url'])`;
    };

    const getActiveCode = () => {
        switch (activeCodeTab) {
            case "url": return getUrlCode();
            case "curl": return getCurlCode();
            case "javascript": return getJsCode();
            case "python": return getPythonCode();
            default: return getCurlCode();
        }
    };

    const handleCopy = async () => {
        await navigator.clipboard.writeText(getActiveCode());
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="flex gap-6 h-[calc(100vh-160px)]">
            {/* Left Panel */}
            <div className="w-[400px] flex-shrink-0 flex flex-col gap-4 overflow-y-auto dark-scrollbar pr-2">

                {/* Main Input Card */}
                <div className="rounded-2xl p-px bg-gradient-to-b from-[#6155f5]/20 to-transparent">
                    <div className="bg-[#0a0a0f] rounded-2xl p-5 space-y-4">
                        {/* Source Type */}
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-500 mr-2">Source:</span>
                            {(["url", "html", "markdown"] as const).map((type) => (
                                <button
                                    key={type}
                                    onClick={() => setSourceType(type)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all uppercase ${sourceType === type
                                            ? "bg-[#6155f5]/20 border border-[#6155f5]/50 text-white"
                                            : "bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:border-white/20"
                                        }`}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>

                        {/* Source Input */}
                        {sourceType === "url" && (
                            <input
                                type="text"
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && handleRender()}
                                placeholder="Enter URL (e.g., stripe.com)"
                                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-[#6155f5]/50 focus:ring-2 focus:ring-[#6155f5]/20 transition-all font-mono text-sm"
                            />
                        )}
                        {sourceType === "html" && (
                            <textarea
                                value={htmlContent}
                                onChange={(e) => setHtmlContent(e.target.value)}
                                placeholder="<h1>Hello World</h1>"
                                rows={3}
                                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-[#6155f5]/50 focus:ring-2 focus:ring-[#6155f5]/20 transition-all font-mono text-sm resize-none"
                            />
                        )}
                        {sourceType === "markdown" && (
                            <textarea
                                value={markdownContent}
                                onChange={(e) => setMarkdownContent(e.target.value)}
                                placeholder="# Hello World"
                                rows={3}
                                className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-[#6155f5]/50 focus:ring-2 focus:ring-[#6155f5]/20 transition-all font-mono text-sm resize-none"
                            />
                        )}

                        {/* API Key */}
                        <input
                            type="password"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder="API Key (sk_live_...)"
                            className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:border-[#6155f5]/50 focus:ring-2 focus:ring-[#6155f5]/20 transition-all font-mono text-sm"
                        />

                        {/* Capture Button */}
                        <button
                            onClick={handleRender}
                            disabled={isLoading}
                            className="w-full brand-gradient text-white rounded-xl px-6 py-3 font-bold flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all hover:opacity-90"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Capturing...
                                </>
                            ) : (
                                <>
                                    <Camera className="h-4 w-4" />
                                    Capture Screenshot
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* Code Snippet */}
                <div className="rounded-2xl border border-white/10 overflow-hidden">
                    {/* Header */}
                    <div className="bg-white/5 px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-1">
                            {CODE_TABS.map((tab) => {
                                const Icon = tab.icon;
                                const isActive = activeCodeTab === tab.id;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveCodeTab(tab.id)}
                                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${isActive
                                                ? "bg-[#6155f5]/20 border border-[#6155f5]/50 text-white"
                                                : "text-slate-400 hover:text-white"
                                            }`}
                                    >
                                        <Icon className="w-3 h-3" />
                                        {tab.label}
                                    </button>
                                );
                            })}
                        </div>
                        <button
                            onClick={handleCopy}
                            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white transition-all"
                        >
                            {copied ? (
                                <>
                                    <Check className="w-3 h-3 text-emerald-400" />
                                    <span className="text-emerald-400">Copied!</span>
                                </>
                            ) : (
                                <>
                                    <Copy className="w-3 h-3" />
                                    Copy
                                </>
                            )}
                        </button>
                    </div>
                    {/* Code Area */}
                    <div className="bg-black/60 h-48 overflow-auto p-4 dark-scrollbar">
                        <pre className="text-xs font-mono leading-relaxed whitespace-pre text-slate-300">
                            {getActiveCode()}
                        </pre>
                    </div>
                </div>

                {/* Advanced Options Toggle */}
                <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:border-white/20 transition-all text-sm"
                >
                    <Settings2 className="h-4 w-4" />
                    <span>Advanced Options</span>
                    <span className={`ml-auto transition-transform ${showAdvanced ? 'rotate-180' : ''}`}>▼</span>
                </button>

                {/* Advanced Options Panel */}
                {showAdvanced && (
                    <div className="rounded-2xl border border-white/10 p-4 space-y-4">
                        {/* Viewport */}
                        <div className="grid grid-cols-3 gap-3">
                            <div className="space-y-1">
                                <label className="text-xs text-slate-500">Width</label>
                                <input
                                    type="number"
                                    value={width}
                                    onChange={(e) => setWidth(Number(e.target.value))}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#6155f5]/50"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-slate-500">Height</label>
                                <input
                                    type="number"
                                    value={height}
                                    onChange={(e) => setHeight(Number(e.target.value))}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#6155f5]/50"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-xs text-slate-500">Format</label>
                                <select
                                    value={format}
                                    onChange={(e) => setFormat(e.target.value)}
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-[#6155f5]/50"
                                >
                                    <option value="png">PNG</option>
                                    <option value="jpeg">JPEG</option>
                                    <option value="webp">WebP</option>
                                </select>
                            </div>
                        </div>

                        {/* Selector */}
                        <div className="space-y-1">
                            <label className="text-xs text-slate-500">Element Selector (optional)</label>
                            <input
                                type="text"
                                value={selector}
                                onChange={(e) => setSelector(e.target.value)}
                                placeholder=".hero, #main"
                                className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:border-[#6155f5]/50 font-mono"
                            />
                        </div>

                        {/* Toggles */}
                        <div className="grid grid-cols-2 gap-3">
                            <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={blockAds}
                                    onChange={(e) => setBlockAds(e.target.checked)}
                                    className="rounded border-white/20 bg-black/40 text-[#6155f5] focus:ring-[#6155f5]/20"
                                />
                                Block Ads
                            </label>
                            <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={blockCookieBanners}
                                    onChange={(e) => setBlockCookieBanners(e.target.checked)}
                                    className="rounded border-white/20 bg-black/40 text-[#6155f5] focus:ring-[#6155f5]/20"
                                />
                                Block Cookies
                            </label>
                            <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={fullPage}
                                    onChange={(e) => setFullPage(e.target.checked)}
                                    className="rounded border-white/20 bg-black/40 text-[#6155f5] focus:ring-[#6155f5]/20"
                                />
                                Full Page
                            </label>
                            <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={darkMode}
                                    onChange={(e) => setDarkMode(e.target.checked)}
                                    className="rounded border-white/20 bg-black/40 text-[#6155f5] focus:ring-[#6155f5]/20"
                                />
                                Dark Mode
                            </label>
                        </div>
                    </div>
                )}
            </div>

            {/* Right Panel - Preview */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Browser Frame */}
                <div className="rounded-2xl border border-white/10 overflow-hidden flex-1 flex flex-col">
                    {/* Browser Header */}
                    <div className="bg-white/5 border-b border-white/10 px-4 py-3 flex items-center justify-between">
                        <div className="flex gap-1.5">
                            <div className="w-3 h-3 rounded-full bg-red-500/50" />
                            <div className="w-3 h-3 rounded-full bg-yellow-500/50" />
                            <div className="w-3 h-3 rounded-full bg-green-500/50" />
                        </div>
                        <div className="bg-black/40 border border-white/10 rounded-lg px-4 py-1.5 text-xs text-slate-500 font-mono flex-1 mx-8 text-center truncate">
                            {sourceType === "url" ? (url.startsWith("http") ? url : `https://${url}`) : `[${sourceType.toUpperCase()} Content]`}
                        </div>
                        {result && !isLoading && (
                            <button
                                onClick={() => {
                                    const link = document.createElement('a');
                                    link.href = result;
                                    link.download = `screenshot-${Date.now()}.${format}`;
                                    link.target = '_blank';
                                    link.click();
                                }}
                                className="text-xs text-[#6155f5] hover:text-white font-medium transition-colors"
                            >
                                Download
                            </button>
                        )}
                    </div>

                    {/* Preview Content */}
                    <div className="bg-black/60 flex-1 flex items-center justify-center p-6">
                        {isLoading ? (
                            <div className="flex flex-col items-center gap-4">
                                <Loader2 className="h-12 w-12 text-[#6155f5] animate-spin" />
                                <p className="text-slate-400 text-sm">Capturing screenshot...</p>
                            </div>
                        ) : error ? (
                            <div className="flex flex-col items-center gap-4 text-center max-w-md">
                                <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                    <span className="text-red-400 text-xl">!</span>
                                </div>
                                <p className="text-red-400 text-sm">{error}</p>
                            </div>
                        ) : result ? (
                            <img
                                src={result}
                                alt="Screenshot"
                                className="max-w-full max-h-full object-contain rounded-lg shadow-2xl border border-white/10"
                            />
                        ) : (
                            <div className="flex flex-col items-center gap-4 text-center max-w-md">
                                <div className="w-20 h-20 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
                                    <Camera className="h-8 w-8 text-slate-600" />
                                </div>
                                <p className="text-slate-400 text-sm">Enter a URL above and click Capture</p>
                                <p className="text-slate-500 text-xs">Your screenshot will appear here</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
