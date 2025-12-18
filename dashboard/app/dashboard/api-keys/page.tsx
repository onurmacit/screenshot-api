"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import {
    Plus,
    Trash2,
    Copy,
    Key,
    AlertCircle,
    Loader2,
    Check
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

export default function ApiKeysPage() {
    const [keys, setKeys] = useState<APIKey[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isCreating, setIsCreating] = useState(false);
    const [newKeyName, setNewKeyName] = useState("");
    const [createdKey, setCreatedKey] = useState<string | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

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

    const handleCreateKey = async () => {
        if (!newKeyName.trim()) return;

        setIsCreating(true);
        try {
            const result = await authApi.createApiKey({ name: newKeyName });
            setCreatedKey(result.api_key);
            setKeys([result, ...keys]); // Add to list
            toast.success("API Key created successfully");
        } catch (error) {
            toast.error("Failed to create API key");
            console.error(error);
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
            toast.success("API Key deleted");
        } catch (error) {
            toast.error("Failed to delete API key");
            console.error(error);
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast.success("Copied to clipboard");
    };

    const closeDialog = () => {
        if (createdKey) {
            // If we were showing a created key, clear it when closing
            setCreatedKey(null);
            setNewKeyName("");
        }
        setIsDialogOpen(false);
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
                    <p className="text-muted-foreground mt-2">
                        Manage your API keys to access the Screenshot API.
                    </p>
                </div>
                <Dialog open={isDialogOpen} onOpenChange={(open) => {
                    if (!open) closeDialog();
                    else setIsDialogOpen(true);
                }}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-2 h-4 w-4" /> Create New Key
                        </Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>{createdKey ? "API Key Created" : "Create New API Key"}</DialogTitle>
                            <DialogDescription>
                                {createdKey
                                    ? "Please copy your API key now. You won't be able to see it again!"
                                    : "Enter a name for your new API key to identify it later."}
                            </DialogDescription>
                        </DialogHeader>

                        {createdKey ? (
                            <div className="space-y-4">
                                <Alert className="bg-green-50 border-green-200">
                                    <AlertTitle className="text-green-800">Success</AlertTitle>
                                    <AlertDescription className="text-green-700">
                                        Your API key has been generated.
                                    </AlertDescription>
                                </Alert>
                                <div className="flex items-center space-x-2">
                                    <div className="grid flex-1 gap-2">
                                        <Label htmlFor="link" className="sr-only">
                                            Link
                                        </Label>
                                        <Input
                                            id="link"
                                            defaultValue={createdKey}
                                            readOnly
                                            className="font-mono bg-slate-50"
                                        />
                                    </div>
                                    <Button type="submit" size="sm" className="px-3" onClick={() => copyToClipboard(createdKey)}>
                                        <span className="sr-only">Copy</span>
                                        <Copy className="h-4 w-4" />
                                    </Button>
                                </div>
                                <DialogFooter>
                                    <Button onClick={closeDialog}>Done</Button>
                                </DialogFooter>
                            </div>
                        ) : (
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <Label htmlFor="name">Key Name</Label>
                                    <Input
                                        id="name"
                                        placeholder="e.g. My Production App"
                                        value={newKeyName}
                                        onChange={(e) => setNewKeyName(e.target.value)}
                                    />
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                                    <Button onClick={handleCreateKey} disabled={isCreating || !newKeyName}>
                                        {isCreating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                        Create Key
                                    </Button>
                                </DialogFooter>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Active Keys</CardTitle>
                    <CardDescription>
                        List of all active API keys associated with your account.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {isLoading ? (
                        <div className="flex justify-center p-8">
                            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
                        </div>
                    ) : keys.length === 0 ? (
                        <div className="text-center py-12 text-gray-500">
                            <Key className="h-12 w-12 mx-auto mb-4 opacity-50" />
                            <p>No API keys found. Create one to get started.</p>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Key Prefix</TableHead>
                                    <TableHead>Created</TableHead>
                                    <TableHead>Last Used</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {keys.map((key) => (
                                    <TableRow key={key.key_id}>
                                        <TableCell className="font-medium">{key.name}</TableCell>
                                        <TableCell className="font-mono text-xs">{key.key_prefix}...</TableCell>
                                        <TableCell>{format(new Date(key.created_at), "MMM d, yyyy")}</TableCell>
                                        <TableCell>
                                            {key.last_used_at
                                                ? format(new Date(key.last_used_at), "MMM d, HH:mm")
                                                : "Never"}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={key.is_active ? "default" : "secondary"} className={key.is_active ? "bg-green-600" : ""}>
                                                {key.is_active ? "Active" : "Inactive"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                onClick={() => handleDeleteKey(key.key_id)}
                                                className="text-red-500 hover:text-red-700 hover:bg-red-50"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
