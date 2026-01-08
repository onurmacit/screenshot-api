"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Copy, Check, Link, Terminal, Code, FileCode } from "lucide-react";

// Support both old simple interface and new tabbed interface
interface SimpleCodeSnippetProps {
    code: string;
    title?: string;
}

interface TabbedCodeSnippetProps {
    curl: string;
    apiUrl: string;
    params: Record<string, string | number | boolean>;
    apiKey?: string;
}

type CodeSnippetProps = SimpleCodeSnippetProps | TabbedCodeSnippetProps;

function isSimpleMode(props: CodeSnippetProps): props is SimpleCodeSnippetProps {
    return 'code' in props && typeof props.code === 'string';
}

export function CodeSnippet(props: CodeSnippetProps) {
    const [copied, setCopied] = useState(false);
    const [activeTab, setActiveTab] = useState("curl");

    // Simple mode - just show the code
    if (isSimpleMode(props)) {
        const { code, title = "Code Snippet" } = props;

        const handleCopy = async () => {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        };

        return (
            <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm">{title}</CardTitle>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleCopy}
                        className="h-8 w-8 p-0"
                    >
                        {copied ? (
                            <Check className="h-4 w-4 text-green-500" />
                        ) : (
                            <Copy className="h-4 w-4" />
                        )}
                    </Button>
                </CardHeader>
                <CardContent>
                    <pre className="bg-slate-950 text-slate-50 p-4 rounded-lg text-xs overflow-x-auto">
                        <code>{code}</code>
                    </pre>
                </CardContent>
            </Card>
        );
    }

    // Tabbed mode - show multiple language options
    const { curl, apiUrl, params, apiKey = "YOUR_API_KEY" } = props;

    // Generate URL with query params
    const generateUrlCode = () => {
        const queryParams = new URLSearchParams();
        queryParams.set('api_key', apiKey);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== '' && value !== false) {
                queryParams.set(key, String(value));
            }
        });
        return `${apiUrl}?${queryParams.toString()}`;
    };

    // Generate JavaScript code
    const generateJsCode = () => {
        const bodyObj = { ...params };
        return `const response = await fetch('${apiUrl}', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': '${apiKey}'
  },
  body: JSON.stringify(${JSON.stringify(bodyObj, null, 4).split('\n').join('\n  ')})
});

const data = await response.json();
console.log(data.url); // Screenshot URL`;
    };

    // Generate Python code
    const generatePythonCode = () => {
        const bodyObj = { ...params };
        const jsonStr = JSON.stringify(bodyObj, null, 4)
            .replace(/"/g, "'")
            .replace(/true/g, "True")
            .replace(/false/g, "False")
            .replace(/null/g, "None");
        return `import requests

response = requests.post(
    '${apiUrl}',
    headers={
        'Content-Type': 'application/json',
        'X-API-Key': '${apiKey}'
    },
    json=${jsonStr}
)

data = response.json()
print(data['url'])  # Screenshot URL`;
    };

    const getActiveCode = () => {
        switch (activeTab) {
            case 'url': return generateUrlCode();
            case 'curl': return curl;
            case 'javascript': return generateJsCode();
            case 'python': return generatePythonCode();
            default: return curl;
        }
    };

    const handleCopy = async () => {
        await navigator.clipboard.writeText(getActiveCode());
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Card className="overflow-hidden shadow-md border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between px-4 py-2 border-b bg-slate-50/50 dark:bg-slate-900/50">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <div className="flex items-center justify-between">
                        <TabsList className="h-9 bg-slate-100 dark:bg-slate-800 p-1">
                            <TabsTrigger value="url" className="text-xs gap-1.5 px-3 h-7 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-950 shadow-sm transition-all">
                                <Link className="h-3.5 w-3.5" />
                                URL
                            </TabsTrigger>
                            <TabsTrigger value="curl" className="text-xs gap-1.5 px-3 h-7 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-950 shadow-sm transition-all">
                                <Terminal className="h-3.5 w-3.5" />
                                cURL
                            </TabsTrigger>
                            <TabsTrigger value="javascript" className="text-xs gap-1.5 px-3 h-7 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-950 shadow-sm transition-all">
                                <Code className="h-3.5 w-3.5" />
                                JavaScript
                            </TabsTrigger>
                            <TabsTrigger value="python" className="text-xs gap-1.5 px-3 h-7 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-950 shadow-sm transition-all">
                                <FileCode className="h-3.5 w-3.5" />
                                Python
                            </TabsTrigger>
                        </TabsList>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCopy}
                            className="h-8 gap-2 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                            {copied ? (
                                <>
                                    <Check className="h-3.5 w-3.5 text-green-500" />
                                    <span className="text-green-600 dark:text-green-400">Copied!</span>
                                </>
                            ) : (
                                <>
                                    <Copy className="h-3.5 w-3.5 text-slate-500" />
                                    <span>Copy</span>
                                </>
                            )}
                        </Button>
                    </div>
                </Tabs>
            </div>
            <CardContent className="p-0">
                <div className="bg-slate-950 h-[280px] overflow-hidden">
                    <pre className="p-5 text-[13px] leading-relaxed font-mono h-full overflow-scroll custom-scrollbar whitespace-pre">
                        <code className={activeTab === 'url' ? 'text-blue-400' : 'text-slate-300'}>
                            {getActiveCode()}
                        </code>
                    </pre>
                </div>
            </CardContent>
            <style jsx global>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 6px;
                    height: 6px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: #334155;
                    border-radius: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: #475569;
                }
            `}</style>
        </Card>
    );
}
