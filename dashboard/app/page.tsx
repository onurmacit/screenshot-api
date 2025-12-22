// Root page - middleware handles redirect based on auth status
// Authenticated users → /dashboard
// Unauthenticated users → /login

export default function Home() {
  // This should not render - middleware redirects before reaching here
  // But just in case, show a loading state
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
    </div>
  );
}
