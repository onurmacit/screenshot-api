"use client";

import { useEffect, useState } from "react";
import { format, subDays, startOfMonth, endOfMonth } from "date-fns";
import {
    BarChart,
    Activity,
    CreditCard,
    FileImage,
    FileText,
    Calendar
} from "lucide-react";
import { toast } from "sonner";
import { authApi, UsageHistoryResponse } from "@/services/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";

export default function SubscriptionPage() {
    const [usage, setUsage] = useState<UsageHistoryResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [period, setPeriod] = useState("month"); // 'month' | '30days'

    useEffect(() => {
        fetchUsage();
    }, [period]);

    const fetchUsage = async () => {
        setIsLoading(true);
        try {
            const today = new Date();
            let start = "";
            let end = format(today, "yyyy-MM-dd");
            let granularity = "day";

            if (period === "month") {
                start = format(startOfMonth(today), "yyyy-MM-dd");
                // end is today
            } else {
                start = format(subDays(today, 30), "yyyy-MM-dd");
            }

            const data = await authApi.getUsageHistory({
                start_date: start,
                end_date: end,
                granularity
            });
            setUsage(data);
        } catch (error) {
            toast.error("Failed to load usage data");
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    const usagePercentage = usage
        ? Math.min(100, (usage.total_requests / 1000) * 100) // Assuming 1000 limit for now
        : 0;

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Subscription & Usage</h1>
                <p className="text-muted-foreground mt-2">
                    Track your API usage and manage your subscription plan.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Requests</CardTitle>
                        <Activity className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {isLoading ? <Skeleton className="h-8 w-20" /> : (
                            <>
                                <div className="text-2xl font-bold">{usage?.total_requests || 0}</div>
                                <p className="text-xs text-muted-foreground">in current period</p>
                            </>
                        )}
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Screenshots</CardTitle>
                        <FileImage className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {isLoading ? <Skeleton className="h-8 w-20" /> : (
                            <>
                                <div className="text-2xl font-bold">{usage?.usage.reduce((acc, curr) => acc + curr.screenshots, 0) || 0}</div>
                                <p className="text-xs text-muted-foreground">images generated</p>
                            </>
                        )}
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">PDFs</CardTitle>
                        <FileText className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        {isLoading ? <Skeleton className="h-8 w-20" /> : (
                            <>
                                <div className="text-2xl font-bold">{usage?.usage.reduce((acc, curr) => acc + curr.pdfs, 0) || 0}</div>
                                <p className="text-xs text-muted-foreground">documents generated</p>
                            </>
                        )}
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Current Plan</CardTitle>
                        <CreditCard className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">Free</div>
                        <p className="text-xs text-muted-foreground">1,000 requests / month</p>
                    </CardContent>
                </Card>
            </div>

            <Card className="col-span-4">
                <CardHeader>
                    <CardTitle>Usage Overview</CardTitle>
                    <CardDescription>
                        Daily request volume for the selected period.
                    </CardDescription>
                </CardHeader>
                <CardContent className="pl-2">
                    {/* Simple visual representation instead of full charting library for MVP */}
                    {isLoading ? (
                        <div className="space-y-2">
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-3/4" />
                            <Skeleton className="h-4 w-5/6" />
                        </div>
                    ) : (
                        <div className="h-[200px] w-full flex items-end justify-between gap-2 p-4">
                            {usage?.usage.slice(-14).map((day) => ( // Show last 14 days
                                <div key={day.date} className="group relative flex-1 flex flex-col justify-end items-center gap-2 h-full">
                                    <div
                                        className="w-full bg-blue-500 rounded-t-sm hover:bg-blue-600 transition-all"
                                        style={{ height: `${Math.max(5, (day.requests / (Math.max(...usage.usage.map(u => u.requests)) || 1)) * 100)}%` }}
                                    ></div>
                                    <span className="text-[10px] text-muted-foreground rotate-[-45deg] origin-top-left translate-y-4">
                                        {format(new Date(day.date), "MMM d")}
                                    </span>
                                    {/* Tooltip */}
                                    <div className="absolute bottom-full mb-2 hidden group-hover:block bg-slate-800 text-white text-xs p-2 rounded z-10 whitespace-nowrap">
                                        {day.date}: {day.requests} reqs
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
