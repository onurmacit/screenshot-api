"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";

interface Job {
    id: string;
    user_email: string;
    type: string;
    status: string;
    url: string;
    format: string | null;
    processing_time_ms: number | null;
    file_size_bytes: number | null;
    created_at: string;
}

interface PaginatedResponse {
    items: Job[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export default function AdminJobsPage() {
    const [data, setData] = useState<PaginatedResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);

    useEffect(() => {
        const fetchJobs = async () => {
            setLoading(true);
            try {
                const response = await api.get(`/api/v1/admin/jobs?page=${page}&per_page=50`);
                setData(response.data);
            } catch (err) {
                console.error("Failed to load jobs", err);
            } finally {
                setLoading(false);
            }
        };
        fetchJobs();
    }, [page]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[300px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    const formatBytes = (bytes: number | null) => {
        if (!bytes) return "-";
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    const formatTime = (ms: number | null) => {
        if (!ms) return "-";
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">All Render Jobs ({data?.total || 0})</h2>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Format</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {data?.items.map((job) => (
                                <tr key={job.id} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm text-gray-900 max-w-[200px] truncate" title={job.url}>
                                        {job.url}
                                    </td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{job.user_email}</td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 capitalize">{job.type}</td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500 uppercase">{job.format || "-"}</td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{formatTime(job.processing_time_ms)}</td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">{formatBytes(job.file_size_bytes)}</td>
                                    <td className="px-4 py-3 whitespace-nowrap">
                                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${job.status === "completed" ? "bg-green-100 text-green-800" :
                                            job.status === "failed" ? "bg-red-100 text-red-800" :
                                                "bg-yellow-100 text-yellow-800"
                                            }`}>
                                            {job.status}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                                        {new Date(job.created_at).toLocaleString()}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
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
