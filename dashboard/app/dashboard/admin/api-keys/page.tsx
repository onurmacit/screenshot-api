"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

interface APIKey {
    id: string;
    name: string;
    key_prefix: string;
    user_email: string;
    user_id: string;
    is_active: boolean;
    created_at: string;
    last_used_at: string | null;
    request_count: number;
}

interface PaginatedResponse {
    items: APIKey[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export default function AdminAPIKeysPage() {
    const [data, setData] = useState<PaginatedResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);

    useEffect(() => {
        const fetchKeys = async () => {
            setLoading(true);
            try {
                const response = await api.get(`/api/v1/admin/api-keys?page=${page}&per_page=20`);
                setData(response.data);
            } catch (err) {
                console.error("Failed to load API keys", err);
            } finally {
                setLoading(false);
            }
        };
        fetchKeys();
    }, [page]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[300px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">All API Keys ({data?.total || 0})</h2>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Key</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Owner</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requests</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Last Used</th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {data?.items.map((key) => (
                            <tr key={key.id} className="hover:bg-gray-50">
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{key.name}</td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <code className="px-2 py-1 bg-gray-100 rounded text-sm">sk_live_{key.key_prefix}...</code>
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{key.user_email}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{key.request_count}</td>
                                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                    {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}
                                </td>
                                <td className="px-6 py-4 whitespace-nowrap">
                                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${key.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                                        }`}>
                                        {key.is_active ? "Active" : "Inactive"}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            {data && data.pages > 1 && (
                <div className="flex items-center justify-between">
                    <p className="text-sm text-gray-500">
                        Page {data.page} of {data.pages}
                    </p>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPage(p => Math.max(1, p - 1))}
                            disabled={page === 1}
                            className="px-3 py-1 text-sm border rounded-lg disabled:opacity-50"
                        >
                            Previous
                        </button>
                        <button
                            onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                            disabled={page === data.pages}
                            className="px-3 py-1 text-sm border rounded-lg disabled:opacity-50"
                        >
                            Next
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
