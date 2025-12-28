"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Loader2, FileText } from "lucide-react";
import { api } from "@/services/api";
import { PlaygroundHeader, CodeSnippet, PreviewPanel, DownloadButton } from "@/components/playground";

export default function PDFPlaygroundPage() {
    const [url, setUrl] = useState("https://stripe.com");
    const [apiKey, setApiKey] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [result, setResult] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // PDF options
    const [pdfFormat, setPdfFormat] = useState("A4");
    const [landscape, setLandscape] = useState(false);
    const [printBackground, setPrintBackground] = useState(true);
    const [scale, setScale] = useState(1);

    const handleRender = async () => {
        if (!apiKey) {
            setError("Please enter your API Key");
            return;
        }

        setIsLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await api.post("/api/v1/renders/pdf", {
                url,
                format: pdfFormat,
                landscape,
                print_background: printBackground,
                scale,
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
                setError("Failed to generate PDF");
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.message || err.message || "An error occurred");
        } finally {
            setIsLoading(false);
        }
    };

    const generateCurl = () => {
        return `curl -X POST ${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/renders/pdf \\
  -H "X-API-Key: ${apiKey || "YOUR_API_KEY"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "${url}",
    "format": "${pdfFormat}",
    "landscape": ${landscape},
    "print_background": ${printBackground},
    "scale": ${scale}
  }'`;
    };

    return (
        <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-280px)]">
            {/* Controls Panel */}
            <div className="w-full lg:w-96 flex-shrink-0 space-y-6 overflow-y-auto pr-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5" />
                            PDF Options
                        </CardTitle>
                        <CardDescription>Configure PDF generation parameters</CardDescription>
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
                                <Label>Page Format</Label>
                                <Select value={pdfFormat} onValueChange={setPdfFormat}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="A0">A0</SelectItem>
                                        <SelectItem value="A1">A1</SelectItem>
                                        <SelectItem value="A2">A2</SelectItem>
                                        <SelectItem value="A3">A3</SelectItem>
                                        <SelectItem value="A4">A4</SelectItem>
                                        <SelectItem value="A5">A5</SelectItem>
                                        <SelectItem value="A6">A6</SelectItem>
                                        <SelectItem value="Letter">Letter</SelectItem>
                                        <SelectItem value="Legal">Legal</SelectItem>
                                        <SelectItem value="Tabloid">Tabloid</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Scale</Label>
                                <Input
                                    type="number"
                                    value={scale}
                                    onChange={(e) => setScale(Number(e.target.value))}
                                    min={0.1}
                                    max={2}
                                    step={0.1}
                                />
                            </div>
                        </div>

                        <Separator />

                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="landscape">Landscape</Label>
                                <Switch id="landscape" checked={landscape} onCheckedChange={setLandscape} />
                            </div>

                            <div className="flex items-center justify-between">
                                <Label htmlFor="printBackground">Print Background</Label>
                                <Switch id="printBackground" checked={printBackground} onCheckedChange={setPrintBackground} />
                            </div>
                        </div>

                        <Button className="w-full" onClick={handleRender} disabled={isLoading}>
                            {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                            Generate PDF
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
                        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>Click "Generate PDF" to preview</p>
                    </div>
                }
            >
                {result && (
                    <>
                        <iframe src={result} className="w-full h-full rounded-lg shadow-lg" />
                        <DownloadButton url={result} label="Download PDF" />
                    </>
                )}
            </PreviewPanel>
        </div>
    );
}
