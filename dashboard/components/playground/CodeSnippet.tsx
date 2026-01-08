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
        <Card className="overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <div className="flex items-center justify-between">
                        <TabsList className="h-8">
                            <TabsTrigger value="url" className="text-xs gap-1 px-2 h-6">
                                <Link className="h-3 w-3" />
                                URL
                            </TabsTrigger>
                            <TabsTrigger value="curl" className="text-xs gap-1 px-2 h-6">
                                <Terminal className="h-3 w-3" />
                                cURL
                            </TabsTrigger>
                            <TabsTrigger value="javascript" className="text-xs gap-1 px-2 h-6">
                                <Code className="h-3 w-3" />
                                JavaScript
                            </TabsTrigger>
                            <TabsTrigger value="python" className="text-xs gap-1 px-2 h-6">
                                <FileCode className="h-3 w-3" />
                                Python
                            </TabsTrigger>
                        </TabsList>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCopy}
                            className="h-7 gap-1 text-xs"
                        >
                            {copied ? (
                                <>
                                    <Check className="h-3 w-3 text-green-500" />
                                    Copied!
                                </>
                            ) : (
                                <>
                                    <Copy className="h-3 w-3" />
                                    Copy
                                </>
                            )}
                        </Button>
                    </div>
                </Tabs>
            </div>
            <CardContent className="p-0">
                <pre className="bg-slate-950 text-slate-50 p-4 text-xs overflow-x-auto max-h-48 overflow-y-auto">
                    <code className={activeTab === 'url' ? 'text-blue-400 break-all' : ''}>
                        {getActiveCode()}
                    </code>
                </pre>
            </CardContent>
        </Card>
    );
}
