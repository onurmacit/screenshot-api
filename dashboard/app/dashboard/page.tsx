"use client";

import Link from "next/link";
import { ArrowRight, Zap, Key, CreditCard } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Dashboard Overview</h1>
                <p className="text-muted-foreground mt-2">
                    Welcome to ScreenshotAPI. Manage your keys, view usage, and test integration.
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3 items-stretch">
                <Card className="flex flex-col h-full">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Zap className="h-5 w-5 text-yellow-500" />
                            Quick Start
                        </CardTitle>
                        <CardDescription>Test the API instantly</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col flex-grow">
                        <p className="mb-4 text-sm text-muted-foreground">
                            Use the Playground to generate screenshots and get code snippets.
                        </p>
                        <div className="mt-auto">
                            <Link href="/dashboard/playground">
                                <Button className="w-full">
                                    Go to Playground <ArrowRight className="ml-2 h-4 w-4" />
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>

                <Card className="flex flex-col h-full">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Key className="h-5 w-5 text-blue-500" />
                            API Keys
                        </CardTitle>
                        <CardDescription>Manage authentication</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col flex-grow">
                        <p className="mb-4 text-sm text-muted-foreground">
                            Create and revoke API keys for your applications.
                        </p>
                        <div className="mt-auto">
                            <Link href="/dashboard/api-keys">
                                <Button variant="outline" className="w-full">
                                    Manage Keys
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>

                <Card className="flex flex-col h-full">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <CreditCard className="h-5 w-5 text-green-500" />
                            Usage
                        </CardTitle>
                        <CardDescription>Track your consumption</CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col flex-grow">
                        <p className="mb-4 text-sm text-muted-foreground">
                            View your request history and plan limits.
                        </p>
                        <div className="mt-auto">
                            <Link href="/dashboard/subscription">
                                <Button variant="outline" className="w-full">
                                    View Usage
                                </Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
