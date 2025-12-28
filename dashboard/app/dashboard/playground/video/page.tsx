"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Video, Clock, Sparkles } from "lucide-react";

export default function VideoPlaygroundPage() {
    return (
        <div className="flex items-center justify-center min-h-[60vh]">
            <Card className="max-w-md text-center">
                <CardHeader>
                    <div className="mx-auto w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center mb-4">
                        <Video className="h-8 w-8 text-purple-600" />
                    </div>
                    <CardTitle className="text-2xl">Video Recording</CardTitle>
                    <CardDescription className="text-base">
                        Record video of web page interactions and animations
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
                                <Sparkles className="h-4 w-4 text-purple-500" />
                                WebM and MP4 output
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-purple-500" />
                                Custom duration control
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-purple-500" />
                                Click and scroll recording
                            </li>
                            <li className="flex items-center gap-2">
                                <Sparkles className="h-4 w-4 text-purple-500" />
                                Frame rate configuration
                            </li>
                        </ul>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
