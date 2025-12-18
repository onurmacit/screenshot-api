export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen items-center justify-center bg-gray-50 uppercase-none">
            <div className="w-full max-w-md space-y-8 p-8">{children}</div>
        </div>
    );
}
