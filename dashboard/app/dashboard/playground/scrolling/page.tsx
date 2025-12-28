"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ScrollText, Clock, Sparkles } from "lucide-react";

export default function ScrollingPlaygroundPage() {
    return (
        <div className="flex items-center justify-center min-h-[60vh]">
            <Card className="max-w-md text-center">
                <CardHeader>
                    <div className="mx-auto w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mb-4">
                        <ScrollText className="h-8 w-8 text-yellow-600" />
                    </div>
                    <CardTitle className="text-2xl">Scrolling Screenshots</CardTitle>
                    <CardDescription className="text-base">
                        Capture animated scroll sequences of entire web pages
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        <span>Coming Soon</span>
                    </div>

                    <div className="border-t pt-4">
                        <h4 className="font-medium mb-3">Planned Features</h4>
                        <ul className="text-sm text-muted-foreground space-y-2 text-left">
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-yellow-500" />
                                Animated GIF output
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-yellow-500" />
                                Customizable scroll speed
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-yellow-500" />
                                Start/end position control
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-yellow-500" />
                                Pause at specific elements
                            </li>
                        </ul>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
