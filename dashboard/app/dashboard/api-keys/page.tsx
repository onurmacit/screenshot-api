"use client";

import { useEffect, useState, useMemo } from "react";
import { format } from "date-fns";
import {
    Plus,
    Trash2,
    Copy,
    Key,
    Loader2,
    Eye,
    EyeOff,
    Search,
    CheckSquare,
    Square,
    Minus,
    Check,
    Shield,
    ShieldOff,
} from "lucide-react";
import { toast } from "sonner";
import { authApi, APIKey } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";

// =============================================================================
// API Key Display Component - Input container style
// =============================================================================
interface KeyDisplayProps {
    keyValue: string;
    keyType: 'access' | 'secret';
}

function KeyDisplay({ keyValue, keyType }: KeyDisplayProps) {
    const [isVisible, setIsVisible] = useState(false);
    const [copied, setCopied] = useState(false);

    // Display the key as-is (no prefix added)
    const displayValue = isVisible
        ? keyValue
        : "••••••••••••••";

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(keyValue);
            setCopied(true);
            toast.success(keyType === 'access' ? "Access key copied" : "Secret key copied");
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            toast.error("Failed to copy");
        }
    };

    if (!keyValue || keyValue === "—") {
        return <span className="text-gray-400">—</span>;
    }

    return (
        <div className="flex items-center gap-2">
            {/* Input-style key display */}
            <Input
                value={displayValue}
                readOnly
                className={`
                    font-mono text-sm w-[140px] h-9
                    ${isVisible ? 'bg-slate-50' : 'bg-slate-100 text-slate-400'}
                `}
            />

            {/* Toggle visibility button */}
            <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 hover:bg-slate-100 flex-shrink-0"
                onClick={() => setIsVisible(!isVisible)}
                title={isVisible ? "Hide key" : "Show key"}
            >
                {isVisible ? (
                    <EyeOff className="h-4 w-4 text-slate-500" />
                ) : (
                    <Eye className="h-4 w-4 text-slate-500" />
                )}
            </Button>

            {/* Copy button */}
            <Button
                variant="ghost"
                size="sm"
                className={`
                    h-8 w-8 p-0 flex-shrink-0 transition-colors duration-200
                    ${copied ? 'text-green-600 hover:text-green-600' : 'hover:bg-slate-100'}
                `}
                onClick={handleCopy}
                title={copied ? "Copied!" : `Copy ${keyType} key`}
            >
                {copied ? (
                    <Check className="h-4 w-4" />
                ) : (
                    <Copy className="h-4 w-4 text-slate-500" />
                )}
            </Button>
        </div>
    );
}

// =============================================================================
// Main API Keys Page
// =============================================================================
export default function ApiKeysPage() {
    const [keys, setKeys] = useState<APIKey[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isCreating, setIsCreating] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [newKeyName, setNewKeyName] = useState("");
    const [createEnforceSigning, setCreateEnforceSigning] = useState(false);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    // Search state
    const [searchQuery, setSearchQuery] = useState("");

    // Selection states
    const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

    useEffect(() => {
        fetchKeys();
    }, []);

    const fetchKeys = async () => {
        try {
            const data = await authApi.listApiKeys();
            setKeys(data);
        } catch (error) {
            toast.error("Failed to load API keys");
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    // Filtered keys based on search
    const filteredKeys = useMemo(() => {
        if (!searchQuery.trim()) return keys;
        const query = searchQuery.toLowerCase();
        return keys.filter(
            (key) =>
                key.name?.toLowerCase().includes(query) ||
                key.key_prefix?.toLowerCase().includes(query)
        );
    }, [keys, searchQuery]);

    // Selection helpers
    const allSelected = filteredKeys.length > 0 && filteredKeys.every((k) => selectedKeys.has(k.key_id));
    const someSelected = filteredKeys.some((k) => selectedKeys.has(k.key_id));
    const selectedCount = Array.from(selectedKeys).filter((id) =>
        filteredKeys.some((k) => k.key_id === id)
    ).length;

    const toggleSelectAll = () => {
        if (allSelected) {
            const newSelected = new Set(selectedKeys);
            filteredKeys.forEach((k) => newSelected.delete(k.key_id));
            setSelectedKeys(newSelected);
        } else {
            const newSelected = new Set(selectedKeys);
            filteredKeys.forEach((k) => newSelected.add(k.key_id));
            setSelectedKeys(newSelected);
        }
    };

    const toggleSelectKey = (keyId: string) => {
        const newSelected = new Set(selectedKeys);
        if (newSelected.has(keyId)) {
            newSelected.delete(keyId);
        } else {
            newSelected.add(keyId);
        }
        setSelectedKeys(newSelected);
    };

    const handleCreateKey = async () => {
        if (!newKeyName.trim()) {
            toast.error("Please enter a key name");
            return;
        }

        setIsCreating(true);

        try {
            const result = await authApi.createApiKey({
                name: newKeyName.trim(),
                enforce_signing: createEnforceSigning
            });
            // Add to list and close dialog immediately (ScreenshotOne approach)
            setKeys([result, ...keys]);
            setNewKeyName("");
            setCreateEnforceSigning(false);
            setIsDialogOpen(false);
            toast.success("API Key created");
        } catch (error: any) {
            const errorMessage = error?.response?.data?.detail || error?.message || "Failed to create API key";
            toast.error(errorMessage);
            console.error("API key creation error:", error);
        } finally {
            setIsCreating(false);
        }
    };

    const handleDeleteKey = async (keyId: string) => {
        if (!confirm("Are you sure you want to delete this API key? This action cannot be undone.")) {
            return;
        }

        try {
            await authApi.deleteApiKey(keyId);
            setKeys(keys.filter((k) => k.key_id !== keyId));
            setSelectedKeys((prev) => {
                const newSet = new Set(prev);
                newSet.delete(keyId);
                return newSet;
            });
            toast.success("API Key deleted");
        } catch (error) {
            toast.error("Failed to delete API key");
            console.error(error);
        }
    };

    const handleBulkDelete = async () => {
        const keysToDelete = Array.from(selectedKeys).filter((id) =>
            filteredKeys.some((k) => k.key_id === id)
        );

        if (keysToDelete.length === 0) {
            toast.error("No keys selected");
            return;
        }

        // Prevent deleting all keys - at least one must remain
        if (keysToDelete.length >= keys.length) {
            toast.error("You must keep at least one API key. Select fewer keys to delete.");
            return;
        }

        if (!confirm(`Are you sure you want to delete ${keysToDelete.length} API key(s)? This action cannot be undone.`)) {
            return;
        }

        setIsDeleting(true);
        let successCount = 0;
        let failCount = 0;

        for (const keyId of keysToDelete) {
            try {
                await authApi.deleteApiKey(keyId);
                successCount++;
            } catch (error) {
                failCount++;
                console.error(`Failed to delete key ${keyId}:`, error);
            }
        }

        await fetchKeys();
        setSelectedKeys(new Set());

        if (failCount === 0) {
            toast.success(`${successCount} API key(s) deleted successfully`);
        } else {
            toast.warning(`${successCount} deleted, ${failCount} failed`);
        }

        setIsDeleting(false);
    };

    const closeDialog = () => {
        setNewKeyName("");
        setCreateEnforceSigning(false);
        setIsDialogOpen(false);
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
                    <p className="text-muted-foreground mt-2">
                        Manage your API keys to access the Screenshot API.
                    </p>
                </div>

                {/* Create Key Dialog */}
                <Dialog open={isDialogOpen} onOpenChange={(open) => {
                    if (!open) closeDialog();
                    else setIsDialogOpen(true);
                }}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" /> Create New Key
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-lg">
                        <form onSubmit={(e) => { e.preventDefault(); handleCreateKey(); }} className="space-y-6 py-2">
                            {/* Header */}
                            <div className="text-center space-y-3">
                                <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center">
                                    <Key className="h-8 w-8 text-primary" />
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900">Create API Key</h2>
                                    <p className="text-gray-500 mt-1">Generate a new key to access the Screenshot API</p>
                                </div>
                            </div>

                            {/* Input Field */}
                            <div className="space-y-2">
                                <Label htmlFor="name" className="text-sm font-medium text-gray-700">
                                    Key Name
                                </Label>
                                <Input
                                    id="name"
                                    placeholder="e.g. Production, Development, My App"
                                    value={newKeyName}
                                    onChange={(e) => setNewKeyName(e.target.value)}
                                    disabled={isCreating}
                                    autoFocus
                                    className="h-12 text-base"
                                />
                                <p className="text-sm text-muted-foreground">
                                    A friendly name to identify this key in your dashboard.
                                </p>
                            </div>

                            {/* Enforce Signing Toggle */}
                            <div className="flex flex-row items-center justify-between rounded-lg border p-4 shadow-sm bg-slate-50">
                                <div className="space-y-0.5">
                                    <Label htmlFor="enforce-signing" className="text-base font-medium">
                                        Accept only signed requests
                                    </Label>
                                    <div className="text-sm text-muted-foreground">
                                        Enhanced security: requires HMAC signature for every request.
                                    </div>
                                </div>
                                <Switch
                                    id="enforce-signing"
                                    checked={createEnforceSigning}
                                    onCheckedChange={setCreateEnforceSigning}
                                    disabled={isCreating}
                                />
                            </div>

                            {/* Action Buttons */}
                            <div className="flex gap-3 pt-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setIsDialogOpen(false)}
                                    disabled={isCreating}
                                    className="flex-1 h-12 text-base"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    type="submit"
                                    disabled={isCreating || !newKeyName.trim()}
                                    className="flex-1 h-12 text-base font-medium"
                                >
                                    {isCreating ? (
                                        <>
                                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                            Creating...
                                        </>
                                    ) : (
                                        <>
                                            <Plus className="mr-2 h-5 w-5" />
                                            Create Key
                                        </>
                                    )}
                                </Button>
                            </div>
                        </form>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Keys Card */}
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>Active Keys</CardTitle>
                            <CardDescription>
                                {keys.length} API key{keys.length !== 1 ? 's' : ''} in your account
                            </CardDescription>
                        </div>
                    </div>

                    {/* Search and Bulk Actions */}
                    <div className="flex items-center gap-4 pt-4">
                        <div className="relative flex-1 max-w-sm">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                            <Input
                                placeholder="Search by name or key..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="pl-9"
                            />
                        </div>

                        {selectedCount > 0 && (
                            <div className="flex items-center gap-3">
                                <span className="text-sm text-muted-foreground">
                                    {selectedCount} selected
                                </span>
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={handleBulkDelete}
                                    disabled={isDeleting}
                                >
                                    {isDeleting ? (
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    ) : (
                                        <Trash2 className="mr-2 h-4 w-4" />
                                    )}
                                    Delete Selected
                                </Button>
                            </div>
                        )}
                    </div>
                </CardHeader>

                <CardContent>
                    {isLoading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                        </div>
                    ) : keys.length === 0 ? (
                        <div className="text-center py-12">
                            <Key className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                            <h3 className="text-lg font-medium text-gray-900 mb-1">No API keys yet</h3>
                            <p className="text-gray-500 mb-4">Create your first API key to get started.</p>
                            <Button onClick={() => setIsDialogOpen(true)}>
                                <Plus className="mr-2 h-4 w-4" /> Create API Key
                            </Button>
                        </div>
                    ) : filteredKeys.length === 0 ? (
                        <div className="text-center py-12">
                            <Search className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                            <h3 className="text-lg font-medium text-gray-900 mb-1">No matching keys</h3>
                            <p className="text-gray-500">Try a different search term.</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <Table>
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="w-12">
                                            <button
                                                onClick={toggleSelectAll}
                                                className="flex items-center justify-center hover:bg-gray-100 rounded p-1 transition-colors"
                                            >
                                                {allSelected ? (
                                                    <CheckSquare className="h-4 w-4 text-primary" />
                                                ) : someSelected ? (
                                                    <Minus className="h-4 w-4 text-primary" />
                                                ) : (
                                                    <Square className="h-4 w-4 text-gray-400" />
                                                )}
                                            </button>
                                        </TableHead>
                                        <TableHead>Name</TableHead>
                                        <TableHead>Access Key</TableHead>
                                        <TableHead>Secret Key</TableHead>
                                        <TableHead>Signed</TableHead>
                                        <TableHead>Last Used</TableHead>
                                        <TableHead>Created</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {filteredKeys.map((key) => (
                                        <TableRow
                                            key={key.key_id}
                                            className={`
                                                transition-colors
                                                ${selectedKeys.has(key.key_id) ? "bg-blue-50 hover:bg-blue-100" : ""}
                                            `}
                                        >
                                            <TableCell>
                                                <button
                                                    onClick={() => toggleSelectKey(key.key_id)}
                                                    className="flex items-center justify-center hover:bg-gray-100 rounded p-1 transition-colors"
                                                >
                                                    {selectedKeys.has(key.key_id) ? (
                                                        <CheckSquare className="h-4 w-4 text-primary" />
                                                    ) : (
                                                        <Square className="h-4 w-4 text-gray-400" />
                                                    )}
                                                </button>
                                            </TableCell>
                                            <TableCell className="font-medium">
                                                {key.name || <span className="text-gray-400 italic">Unnamed</span>}
                                            </TableCell>
                                            <TableCell>
                                                <KeyDisplay keyValue={(key as any).access_key || "—"} keyType="access" />
                                            </TableCell>
                                            <TableCell>
                                                <KeyDisplay keyValue={(key as any).secret_key || "—"} keyType="secret" />
                                            </TableCell>
                                            <TableCell>
                                                <button
                                                    className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium transition-colors ${(key as any).enforce_signing
                                                        ? "bg-green-100 text-green-700 hover:bg-green-200"
                                                        : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                                                        }`}
                                                    title={(key as any).enforce_signing ? "Signing enforced" : "Signing optional"}
                                                >
                                                    {(key as any).enforce_signing ? (
                                                        <><Shield className="h-3.5 w-3.5" /> Yes</>
                                                    ) : (
                                                        <><ShieldOff className="h-3.5 w-3.5" /> No</>
                                                    )}
                                                </button>
                                            </TableCell>
                                            <TableCell className="text-sm text-gray-600">
                                                {key.last_used_at
                                                    ? format(new Date(key.last_used_at), "MMM d, HH:mm")
                                                    : <span className="text-gray-400">Never</span>}
                                            </TableCell>
                                            <TableCell className="text-sm text-gray-600">
                                                {format(new Date(key.created_at), "MMM d, yyyy")}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    onClick={() => handleDeleteKey(key.key_id)}
                                                    className={keys.length === 1
                                                        ? "text-gray-300 cursor-not-allowed"
                                                        : "text-red-500 hover:text-red-700 hover:bg-red-50"}
                                                    title={keys.length === 1
                                                        ? "Cannot delete the last API key"
                                                        : "Delete API key"}
                                                    disabled={keys.length === 1}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Footer info */}
            <div className="text-sm text-muted-foreground text-center">
                <p>
                    Use API keys to authenticate your requests.{" "}
                    <a href="/docs" className="text-primary hover:underline">
                        View API Documentation →
                    </a>
                </p>
            </div>
        </div>
    );
}
