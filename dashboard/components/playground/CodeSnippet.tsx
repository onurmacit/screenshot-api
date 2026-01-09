"use client";

import { useState, useMemo } from "react";
import { Copy, Check, Link, Terminal, Code, FileCode, ChevronDown, Search } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";

interface CodeSnippetProps {
    curl: string;
    apiUrl: string;
    params: Record<string, string | number | boolean>;
    apiKey?: string;
}

// All available languages/libraries
const ALL_LANGUAGES = [
    // Popular (shown as tabs)
    { id: "url", label: "URL", icon: Link, category: "popular" },
    { id: "curl", label: "cURL", icon: Terminal, category: "popular" },
    { id: "javascript", label: "JavaScript", icon: Code, category: "popular" },
    { id: "python", label: "Python", icon: FileCode, category: "popular" },
    { id: "go", label: "Go", icon: Code, category: "popular" },
    { id: "ruby", label: "Ruby", icon: Code, category: "popular" },
    { id: "php", label: "PHP", icon: Code, category: "popular" },

    // SDKs
    { id: "javascript-sdk", label: "JavaScript (SDK)", icon: Code, category: "sdk" },
    { id: "python-sdk", label: "Python (SDK)", icon: FileCode, category: "sdk" },
    { id: "go-sdk", label: "Go (SDK)", icon: Code, category: "sdk" },
    { id: "php-sdk", label: "PHP (SDK)", icon: Code, category: "sdk" },
    { id: "ruby-sdk", label: "Ruby (SDK)", icon: Code, category: "sdk" },
    { id: "java-sdk", label: "Java (SDK)", icon: Code, category: "sdk" },
    { id: "csharp-sdk", label: "C# (SDK)", icon: Code, category: "sdk" },

    // Node.js variants
    { id: "node-http", label: "Node (HTTP)", icon: Code, category: "node" },
    { id: "node-axios", label: "Node (Axios)", icon: Code, category: "node" },
    { id: "node-fetch", label: "Node (Fetch)", icon: Code, category: "node" },

    // PHP variants
    { id: "php", label: "PHP", icon: Code, category: "php" },
    { id: "php-guzzle", label: "PHP (Guzzle)", icon: Code, category: "php" },
    { id: "php-requests", label: "PHP (Requests)", icon: Code, category: "php" },

    // Python variants
    { id: "python-requests", label: "Python (Requests)", icon: FileCode, category: "python" },

    // Other languages
    { id: "rust", label: "Rust", icon: Code, category: "languages" },
    { id: "swift", label: "Swift", icon: Code, category: "languages" },
    { id: "kotlin", label: "Kotlin", icon: Code, category: "languages" },
    { id: "java", label: "Java", icon: Code, category: "languages" },
    { id: "csharp", label: "C#", icon: Code, category: "languages" },
    { id: "dart", label: "Dart", icon: Code, category: "languages" },
    { id: "elixir", label: "Elixir", icon: Code, category: "languages" },
    { id: "clojure", label: "Clojure", icon: Code, category: "languages" },
    { id: "objective-c", label: "Objective-C", icon: Code, category: "languages" },
    { id: "wget", label: "Wget", icon: Terminal, category: "languages" },
] as const;

type LanguageId = typeof ALL_LANGUAGES[number]["id"];

// Primary tabs shown directly
const PRIMARY_TABS = ALL_LANGUAGES.filter(l => l.category === "popular");

// Categories for the dropdown menu
const CATEGORIES = [
    { id: "sdk", label: "SDKs (Recommended)" },
    { id: "node", label: "Node.js" },
    { id: "php", label: "PHP" },
    { id: "python", label: "Python" },
    { id: "languages", label: "Languages" },
];

// Dark mode syntax highlighting - eye-friendly for late night coding
// Background: #020617 (slate-950), Text: #E5E7EB (gray-200)
function highlightCode(code: string): string {
    // Escape HTML
    let html = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // Order matters! Apply in sequence:
    // 1. Comments first (so they're not affected by other rules)
    html = html.replace(/(\/\/[^\n]*|#[^\n]*)/g, '<span style="color:#64748B">$1</span>');

    // 2. Strings
    html = html.replace(/(["'])(?:(?!\1)[^\\]|\\.)*\1/g, '<span style="color:#4ADE80">$&</span>');

    // 3. Keywords
    const keywords = ['const', 'let', 'var', 'function', 'async', 'await', 'return', 'import', 'from', 'require', 'export', 'new', 'class', 'def', 'print', 'True', 'False', 'None', 'self', 'func', 'package', 'defer', 'go', 'nil', 'if', 'else', 'for', 'while', 'try', 'catch', 'throw', 'using', 'var', 'public', 'private', 'static', 'void', 'string', 'int', 'bool'];
    keywords.forEach(kw => {
        html = html.replace(new RegExp(`\\b(${kw})\\b`, 'g'), '<span style="color:#38BDF8">$1</span>');
    });

    // 4. Numbers and booleans
    html = html.replace(/\b(\d+|true|false)\b/gi, '<span style="color:#FACC15">$1</span>');

    // 5. Function calls (word followed by parenthesis)
    html = html.replace(/\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/g, '<span style="color:#A78BFA">$1</span>(');

    return html;
}

export function CodeSnippet({ curl, apiUrl, params, apiKey = "YOUR_API_KEY" }: CodeSnippetProps) {
    const [activeTab, setActiveTab] = useState<LanguageId>("curl");
    const [copied, setCopied] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    // Generate code for all languages
    const codeSnippets = useMemo(() => {
        const snippets: Record<string, string> = {};

        // URL with query string
        const queryParams = new URLSearchParams();
        queryParams.set("api_key", apiKey);
        Object.entries(params).forEach(([key, value]) => {
            if (value !== undefined && value !== "" && value !== false) {
                queryParams.set(key, String(value));
            }
        });
        snippets.url = `${apiUrl}?${queryParams.toString()}`;

        // cURL
        snippets.curl = curl;

        // JavaScript (Fetch)
        snippets.javascript = `const response = await fetch('${apiUrl}', {
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
        snippets.python = `import requests

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

        // Python (Requests) - same as python
        snippets["python-requests"] = snippets.python;

        // Node.js variants
        snippets["node-http"] = `const https = require('https');

const data = JSON.stringify(${JSON.stringify(params, null, 2)});

const options = {
  hostname: 'api.screenshotbeam.com',
  path: '/api/v1/renders/screenshot',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': '${apiKey}',
    'Content-Length': data.length
  }
};

const req = https.request(options, (res) => {
  let body = '';
  res.on('data', chunk => body += chunk);
  res.on('end', () => console.log(JSON.parse(body)));
});

req.write(data);
req.end();`;

        snippets["node-axios"] = `const axios = require('axios');

const response = await axios.post('${apiUrl}', ${JSON.stringify(params, null, 2)}, {
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': '${apiKey}'
  }
});

console.log(response.data.url);`;

        snippets["node-fetch"] = snippets.javascript;

        // Go
        snippets.go = `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

func main() {
    payload := map[string]interface{}{
        ${Object.entries(params).map(([k, v]) => `"${k}": ${typeof v === 'string' ? `"${v}"` : v}`).join(',\n        ')}
    }
    
    jsonData, _ := json.Marshal(payload)
    
    req, _ := http.NewRequest("POST", "${apiUrl}", bytes.NewBuffer(jsonData))
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("X-API-Key", "${apiKey}")
    
    client := &http.Client{}
    resp, _ := client.Do(req)
    defer resp.Body.Close()
    
    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result["url"])
}`;

        // Ruby
        snippets.ruby = `require 'net/http'
require 'json'
require 'uri'

uri = URI('${apiUrl}')
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = true

request = Net::HTTP::Post.new(uri)
request['Content-Type'] = 'application/json'
request['X-API-Key'] = '${apiKey}'
request.body = ${JSON.stringify(params)}.to_json

response = http.request(request)
data = JSON.parse(response.body)
puts data['url']`;

        // Rust
        snippets.rust = `use reqwest::header::{HeaderMap, CONTENT_TYPE};
use serde_json::json;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = reqwest::Client::new();
    
    let mut headers = HeaderMap::new();
    headers.insert(CONTENT_TYPE, "application/json".parse()?);
    headers.insert("X-API-Key", "${apiKey}".parse()?);
    
    let body = json!(${JSON.stringify(params, null, 4)});
    
    let response = client
        .post("${apiUrl}")
        .headers(headers)
        .json(&body)
        .send()
        .await?;
    
    let data: serde_json::Value = response.json().await?;
    println!("{}", data["url"]);
    
    Ok(())
}`;

        // PHP
        snippets.php = `<?php
$ch = curl_init();

curl_setopt($ch, CURLOPT_URL, '${apiUrl}');
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json',
    'X-API-Key: ${apiKey}'
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(${JSON.stringify(params)}));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
curl_close($ch);

$data = json_decode($response, true);
echo $data['url'];
?>`;

        // PHP Guzzle
        snippets["php-guzzle"] = `<?php
require 'vendor/autoload.php';

use GuzzleHttp\\Client;

$client = new Client();
$response = $client->post('${apiUrl}', [
    'headers' => [
        'Content-Type' => 'application/json',
        'X-API-Key' => '${apiKey}'
    ],
    'json' => ${JSON.stringify(params, null, 4)}
]);

$data = json_decode($response->getBody(), true);
echo $data['url'];
?>`;

        // PHP Requests
        snippets["php-requests"] = `<?php
require 'vendor/autoload.php';

$response = Requests::post('${apiUrl}', [
    'Content-Type' => 'application/json',
    'X-API-Key' => '${apiKey}'
], json_encode(${JSON.stringify(params)}));

$data = json_decode($response->body, true);
echo $data['url'];
?>`;

        // Java
        snippets.java = `import java.net.http.*;
import java.net.URI;

HttpClient client = HttpClient.newHttpClient();
HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("${apiUrl}"))
    .header("Content-Type", "application/json")
    .header("X-API-Key", "${apiKey}")
    .POST(HttpRequest.BodyPublishers.ofString("${JSON.stringify(params).replace(/"/g, '\\"')}"))
    .build();

HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
System.out.println(response.body());`;

        // Swift
        snippets.swift = `import Foundation

let url = URL(string: "${apiUrl}")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.setValue("${apiKey}", forHTTPHeaderField: "X-API-Key")

let params: [String: Any] = ${JSON.stringify(params)}
request.httpBody = try? JSONSerialization.data(withJSONObject: params)

URLSession.shared.dataTask(with: request) { data, response, error in
    if let data = data,
       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
        print(json["url"] ?? "")
    }
}.resume()`;

        // Kotlin
        snippets.kotlin = `import java.net.http.*
import java.net.URI

val client = HttpClient.newHttpClient()
val request = HttpRequest.newBuilder()
    .uri(URI.create("${apiUrl}"))
    .header("Content-Type", "application/json")
    .header("X-API-Key", "${apiKey}")
    .POST(HttpRequest.BodyPublishers.ofString("""${JSON.stringify(params)}"""))
    .build()

val response = client.send(request, HttpResponse.BodyHandlers.ofString())
println(response.body())`;

        // C#
        snippets.csharp = `using System.Net.Http;
using System.Text;
using System.Text.Json;

var client = new HttpClient();
client.DefaultRequestHeaders.Add("X-API-Key", "${apiKey}");

var content = new StringContent(
    JsonSerializer.Serialize(new { ${Object.entries(params).map(([k, v]) => `${k} = ${typeof v === 'string' ? `"${v}"` : v}`).join(', ')} }),
    Encoding.UTF8,
    "application/json"
);

var response = await client.PostAsync("${apiUrl}", content);
var data = await response.Content.ReadAsStringAsync();
Console.WriteLine(data);`;

        // Dart
        snippets.dart = `import 'dart:convert';
import 'package:http/http.dart' as http;

Future<void> main() async {
  final response = await http.post(
    Uri.parse('${apiUrl}'),
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': '${apiKey}',
    },
    body: jsonEncode(${JSON.stringify(params)}),
  );
  
  final data = jsonDecode(response.body);
  print(data['url']);
}`;

        // Wget
        snippets.wget = `wget --post-data='${JSON.stringify(params)}' \\
  --header='Content-Type: application/json' \\
  --header='X-API-Key: ${apiKey}' \\
  '${apiUrl}'`;

        // Elixir
        snippets.elixir = `HTTPoison.post!(
  "${apiUrl}",
  Jason.encode!(${JSON.stringify(params)}),
  [
    {"Content-Type", "application/json"},
    {"X-API-Key", "${apiKey}"}
  ]
)
|> Map.get(:body)
|> Jason.decode!()
|> Map.get("url")
|> IO.puts()`;

        // Clojure
        snippets.clojure = `(require '[clj-http.client :as client])

(def response
  (client/post "${apiUrl}"
    {:headers {"Content-Type" "application/json"
               "X-API-Key" "${apiKey}"}
     :body (json/write-str ${JSON.stringify(params)})
     :as :json}))

(println (:url (:body response)))`;

        // Objective-C
        snippets["objective-c"] = `NSMutableURLRequest *request = [[NSMutableURLRequest alloc] init];
[request setURL:[NSURL URLWithString:@"${apiUrl}"]];
[request setHTTPMethod:@"POST"];
[request setValue:@"application/json" forHTTPHeaderField:@"Content-Type"];
[request setValue:@"${apiKey}" forHTTPHeaderField:@"X-API-Key"];

NSDictionary *params = @{${Object.entries(params).map(([k, v]) => `@"${k}": @${typeof v === 'string' ? `"${v}"` : v}`).join(', ')}};
NSData *jsonData = [NSJSONSerialization dataWithJSONObject:params options:0 error:nil];
[request setHTTPBody:jsonData];

NSURLSession *session = [NSURLSession sharedSession];
[[session dataTaskWithRequest:request completionHandler:^(NSData *data, NSURLResponse *response, NSError *error) {
    NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    NSLog(@"%@", json[@"url"]);
}] resume];`;

        // SDKs - placeholder with installation instructions
        const sdkLanguages = ["javascript-sdk", "python-sdk", "go-sdk", "php-sdk", "ruby-sdk", "java-sdk", "csharp-sdk"];
        sdkLanguages.forEach(sdk => {
            const lang = sdk.replace("-sdk", "");
            snippets[sdk] = `// ${lang.charAt(0).toUpperCase() + lang.slice(1)} SDK - Coming Soon!
// Install: npm install @screenshotbeam/${lang}

// Example usage:
// import { ScreenshotBeam } from '@screenshotbeam/${lang}';
// const client = new ScreenshotBeam('${apiKey}');
// const screenshot = await client.capture(${JSON.stringify(params, null, 2)});`;
        });

        return snippets;
    }, [curl, apiUrl, params, apiKey]);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(codeSnippets[activeTab] || "");
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleSelectLanguage = (langId: LanguageId) => {
        setActiveTab(langId);
        setIsDropdownOpen(false);
        setSearchQuery("");
    };

    // Filter languages based on search
    const filteredLanguages = ALL_LANGUAGES.filter(lang =>
        lang.label.toLowerCase().includes(searchQuery.toLowerCase()) &&
        lang.category !== "popular"
    );

    // Get active language info
    const activeLanguage = ALL_LANGUAGES.find(l => l.id === activeTab);
    const isActivePrimary = PRIMARY_TABS.some(t => t.id === activeTab);

    return (
        <div className="w-full rounded-lg overflow-hidden shadow-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
            {/* Header - Tabs + More + Copy */}
            <div className="px-3 py-2 flex items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                {/* Tabs Container */}
                <div className="flex items-center gap-1">
                    {/* Primary Tabs */}
                    <div className="flex items-center gap-0.5 bg-slate-100 dark:bg-slate-800 rounded-md p-0.5">
                        {PRIMARY_TABS.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;
                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`
                                        flex items-center gap-1 px-2 py-1.5 rounded text-xs font-medium transition-all
                                        ${isActive
                                            ? "bg-white dark:bg-slate-950 text-slate-900 dark:text-white shadow-sm"
                                            : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300"
                                        }
                                    `}
                                >
                                    <Icon className="w-3 h-3" />
                                    {tab.label}
                                </button>
                            );
                        })}
                    </div>

                    {/* More Languages Dropdown */}
                    <Popover open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
                        <PopoverTrigger asChild>
                            <button className={`
                                flex items-center gap-1 px-2 py-1.5 rounded text-xs font-medium transition-all ml-1
                                ${!isActivePrimary
                                    ? "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                                }
                            `}>
                                {!isActivePrimary && activeLanguage ? activeLanguage.label : "More"}
                                <ChevronDown className="w-3 h-3" />
                            </button>
                        </PopoverTrigger>
                        <PopoverContent className="w-72 p-0" align="start" side="bottom" sideOffset={4}>
                            {/* Search */}
                            <div className="p-2 border-b">
                                <div className="relative">
                                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                                    <Input
                                        placeholder="Search language..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8 h-8 text-sm"
                                    />
                                </div>
                            </div>

                            {/* Language List - Fixed height to prevent layout shift */}
                            <div className="h-64 overflow-y-auto py-1">
                                {searchQuery ? (
                                    // Search results
                                    filteredLanguages.length > 0 ? (
                                        filteredLanguages.map(lang => (
                                            <button
                                                key={lang.id}
                                                onClick={() => handleSelectLanguage(lang.id)}
                                                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center gap-2 ${activeTab === lang.id ? 'bg-slate-100 dark:bg-slate-800' : ''}`}
                                            >
                                                {lang.label}
                                                {lang.category === "sdk" && (
                                                    <span className="text-[10px] bg-green-100 text-green-700 px-1 rounded">SDK</span>
                                                )}
                                            </button>
                                        ))
                                    ) : (
                                        <div className="px-3 py-4 text-sm text-slate-500 text-center">No results</div>
                                    )
                                ) : (
                                    // Categorized list
                                    CATEGORIES.map(category => {
                                        const categoryLangs = ALL_LANGUAGES.filter(l => l.category === category.id);
                                        if (categoryLangs.length === 0) return null;

                                        return (
                                            <div key={category.id}>
                                                <div className="px-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                                                    {category.label}
                                                </div>
                                                {categoryLangs.map(lang => (
                                                    <button
                                                        key={lang.id}
                                                        onClick={() => handleSelectLanguage(lang.id)}
                                                        className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800 ${activeTab === lang.id ? 'bg-slate-100 dark:bg-slate-800 font-medium' : ''}`}
                                                    >
                                                        {lang.label}
                                                    </button>
                                                ))}
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </PopoverContent>
                    </Popover>
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

            {/* Code Area - Dark Mode Theme */}
            <div className="h-64 bg-[#020617] overflow-hidden rounded-b-lg">
                <div className="h-full overflow-auto p-4 scrollbar-thin">
                    <pre className="text-[13px] leading-relaxed font-mono whitespace-pre" style={{ color: '#E5E7EB' }}>
                        {activeTab === "url" ? (
                            <code className="text-sky-400 break-all">
                                {codeSnippets[activeTab] || ""}
                            </code>
                        ) : (
                            <code dangerouslySetInnerHTML={{ __html: highlightCode(codeSnippets[activeTab] || "// Code snippet not available") }} />
                        )}
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
