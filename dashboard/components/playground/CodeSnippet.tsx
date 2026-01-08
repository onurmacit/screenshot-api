"use client";

import { useState, useMemo } from "react";
import { Copy, Check, Link, Terminal, Code, FileCode } from "lucide-react";

interface CodeSnippetProps {
    curl: string;
    apiUrl: string;
    params: Record<string, string | number | boolean>;
    apiKey?: string;
}

type TabType = "url" | "curl" | "javascript" | "python";

const TABS: { id: TabType; label: string; icon: typeof Link }[] = [
    { id: "url", label: "URL", icon: Link },
    { id: "curl", label: "cURL", icon: Terminal },
    { id: "javascript", label: "JavaScript", icon: Code },
    { id: "python", label: "Python", icon: FileCode },
];

export function CodeSnippet({ curl, apiUrl, params, apiKey = "YOUR_API_KEY" }: CodeSnippetProps) {
    const [activeTab, setActiveTab] = useState<TabType>("curl");
    const [copied, setCopied] = useState(false);

    // Pre-generate all code snippets once (memoized)
    const codeSnippets = useMemo(() => {
        // URL
        const queryParams = new URLSearchParams();
        queryParams.set("api_key", apiKey);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== "" && value !== false) {
                queryParams.set(key, String(value));
            }
        });
        const urlCode = `${apiUrl}?${queryParams.toString()}`;

        // JavaScript  
        const jsCode = `const response = await fetch('${apiUrl}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': '${apiKey}'
  },
  body: JSON.stringify(${JSON.stringify(params, null, 4).split('\n').join('\n  ')})
});

const data = await response.json();
console.log(data.url); // Screenshot URL`;

        // Python
        const pythonParams = JSON.stringify(params, null, 4)
            .replace(/"/g, "'")
            .replace(/true/g, "True")
            .replace(/false/g, "False")
            .replace(/null/g, "None");
        const pythonCode = `import requests

response = requests.post(
    '${apiUrl}',
    headers={
        'Content-Type': 'application/json',
        'X-API-Key': '${apiKey}'
    },
    json=${pythonParams}
)

data = response.json()
print(data['url'])  # Screenshot URL`;

        return {
            url: urlCode,
            curl: curl,
            javascript: jsCode,
            python: pythonCode,
        };
    }, [curl, apiUrl, params, apiKey]);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(codeSnippets[activeTab]);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="w-[480px] rounded-lg overflow-hidden shadow-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            {/* Header - Fixed height */}
            <div className="h-12 px-3 flex items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                {/* Tabs */}
                <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-md p-0.5">
                    {TABS.map((tab) => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`
                                    flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-all
                                    ${isActive
                                        ? "bg-white dark:bg-slate-950 text-slate-900 dark:text-white shadow-sm"
                                        : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                                    }
                                `}
                            >
                                <Icon className="w-3.5 h-3.5" />
                                {tab.label}
                            </button>
                        );
                    })}
                </div>

                {/* Copy Button */}
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                >
                    {copied ? (
                        <>
                            <Check className="w-3.5 h-3.5 text-green-500" />
                            <span className="text-green-600 dark:text-green-400">Copied!</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy</span>
                        </>
                    )}
                </button>
            </div>

            {/* Code Area - FIXED HEIGHT, content scrolls inside */}
            <div className="h-64 bg-slate-950 overflow-hidden">
                <div className="h-full overflow-auto p-4 scrollbar-thin">
                    <pre className="text-[13px] leading-relaxed font-mono whitespace-pre">
                        <code className={activeTab === "url" ? "text-blue-400 break-all" : "text-slate-300"}>
                            {codeSnippets[activeTab]}
                        </code>
                    </pre>
                </div>
            </div>

            {/* Custom Scrollbar Styles */}
            <style jsx>{`
                .scrollbar-thin::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                .scrollbar-thin::-webkit-scrollbar-track {
                    background: transparent;
                }
                .scrollbar-thin::-webkit-scrollbar-thumb {
                    background: #475569;
                    border-radius: 4px;
                }
                .scrollbar-thin::-webkit-scrollbar-thumb:hover {
                    background: #64748b;
                }
                .scrollbar-thin::-webkit-scrollbar-corner {
                    background: transparent;
                }
            `}</style>
        </div>
    );
}
