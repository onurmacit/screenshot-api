"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Activity, Globe, Clock, TrendingUp } from "lucide-react";

interface DemoCapture {
    ip: string;
    url: string;
    timestamp: string;
    render_time_ms: number;
    width?: number;
    height?: number;
    format?: string;
}

interface DemoStats {
    total_today: number;
    total_week: number;
    total_all_time: number;
    top_urls: { url: string; count: number }[];
    recent_captures: DemoCapture[];
}

export default function DemoActivityPage() {
    const [stats, setStats] = useState<DemoStats | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const response = await api.get("/api/v1/admin/demo-stats");
                setStats(response.data);
            } catch (err: any) {
                setError(err.response?.data?.detail || "Failed to load demo stats");
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
        const interval = setInterval(fetchStats, 30000); // Refresh every 30s
        return () => clearInterval(interval);
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
        { label: "Today", value: stats?.total_today || 0, icon: Activity, color: "blue" },
        { label: "This Week", value: stats?.total_week || 0, icon: TrendingUp, color: "green" },
        { label: "All Time", value: stats?.total_all_time || 0, icon: Globe, color: "purple" },
    ];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900">Demo Activity</h1>
                <p className="text-sm text-gray-500 mt-1">
                    Public demo usage statistics and recent captures
                </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

            {/* Top URLs */}
            {stats?.top_urls && stats.top_urls.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Captured URLs</h3>
                    <div className="space-y-2">
                        {stats.top_urls.map((item, index) => (
                            <div key={index} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                    <span className="text-sm font-medium text-gray-500 w-6">#{index + 1}</span>
                                    <Globe className="h-4 w-4 text-gray-400 flex-shrink-0" />
                                    <span className="text-sm text-gray-900 truncate">{item.url}</span>
                                </div>
                                <span className="text-sm font-semibold text-gray-900 ml-4">{item.count}x</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Recent Captures */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-900">Recent Demo Captures</h3>
                    <p className="text-sm text-gray-500 mt-1">Last 50 demo screenshot requests</p>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    IP Address
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    URL
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Viewport
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Render Time
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Time
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {stats?.recent_captures && stats.recent_captures.length > 0 ? (
                                stats.recent_captures.map((capture, index) => (
                                    <tr key={index} className="hover:bg-gray-50">
                                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">
                                            {capture.ip}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-900 max-w-md truncate">
                                            {capture.url}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {capture.width}x{capture.height}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <div className="flex items-center gap-1">
                                                <Clock className="h-3 w-3 text-gray-400" />
                                                {capture.render_time_ms}ms
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                            {new Date(capture.timestamp).toLocaleString()}
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={5} className="px-6 py-12 text-center text-sm text-gray-500">
                                        No demo captures yet
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
