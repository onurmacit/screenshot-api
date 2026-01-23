"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Users, Key, Image, FileText } from "lucide-react";

interface RecentJob {
    id: string;
    url: string;
    user_email: string;
    type: string;
    format: string;
    status: string;
    created_at: string;
}

interface AdminStats {
    total_users: number;
    total_api_keys: number;
    total_jobs: number;
    total_screenshots: number;
    total_pdfs: number;
    recent_jobs: RecentJob[];
}

export default function AdminOverviewPage() {
    const [stats, setStats] = useState<AdminStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.get("/api/v1/admin/stats");
                setStats(response.data);
            } catch (err: any) {
                setError(err.response?.data?.detail || "Failed to load stats");
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, []);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[300px]">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                {error}
            </div>
        );
    }

    const statCards = [
        { label: "Total Users", value: stats?.total_users || 0, icon: Users, color: "blue" },
        { label: "API Keys", value: stats?.total_api_keys || 0, icon: Key, color: "green" },
        { label: "Screenshots", value: stats?.total_screenshots || 0, icon: Image, color: "purple" },
        { label: "PDFs", value: stats?.total_pdfs || 0, icon: FileText, color: "orange" },
    ];

    return (
        <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {statCards.map((stat) => (
                    <div
                        key={stat.label}
                        className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm"
                    >
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-500">{stat.label}</p>
                                <p className="text-3xl font-bold text-gray-900 mt-1">
                                    {stat.value.toLocaleString()}
                                </p>
                            </div>
                            <div className={`p-3 rounded-lg bg-${stat.color}-100`}>
                                <stat.icon className={`h-6 w-6 text-${stat.color}-600`} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Total Jobs */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Total Render Jobs</h3>
                <p className="text-4xl font-bold text-gray-900">
                    {stats?.total_jobs?.toLocaleString() || 0}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                    {stats?.total_screenshots || 0} screenshots + {stats?.total_pdfs || 0} PDFs
                </p>
            </div>

            {/* Recent Jobs Table */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
                    <p className="text-sm text-gray-500 mt-1">Last 10 render jobs</p>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">URL</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Format</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {stats?.recent_jobs && stats.recent_jobs.length > 0 ? (
                                stats.recent_jobs.map((job) => (
                                    <tr key={job.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4 text-sm text-gray-900 max-w-[200px] truncate" title={job.url}>
                                            {job.url}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{job.user_email}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 capitalize">{job.type}</td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 uppercase">{job.format || "-"}</td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${job.status === "completed" ? "bg-green-100 text-green-800" :
                                                    job.status === "failed" ? "bg-red-100 text-red-800" :
                                                        "bg-yellow-100 text-yellow-800"
                                                }`}>
                                                {job.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {new Date(job.created_at).toLocaleString()}
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center text-sm text-gray-500">
                                        No recent jobs
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
