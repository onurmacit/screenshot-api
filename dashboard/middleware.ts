import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

// Routes that require authentication
const protectedRoutes = ["/dashboard"];

// Routes that should redirect to dashboard if already authenticated
const authRoutes = ["/login", "/register"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Check for NextAuth session token
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET || "placeholder-secret",
  });
  
  // Also check for our custom JWT token in cookies
  const customToken = request.cookies.get("token")?.value;
  
  // User is authenticated if either token exists
  const isAuthenticated = !!token || !!customToken;
  
  // Root path - redirect based on auth status
  if (pathname === "/") {
    const redirectUrl = isAuthenticated ? "/dashboard" : "/login";
    const response = NextResponse.redirect(new URL(redirectUrl, request.url));
    // Prevent browser caching of redirects
    response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
    response.headers.set("Pragma", "no-cache");
    response.headers.set("Expires", "0");
    return response;
  }
  
  // Protected routes - redirect to login if not authenticated
  const isProtectedRoute = protectedRoutes.some(route => 
    pathname.startsWith(route)
  );
  
  if (isProtectedRoute && !isAuthenticated) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("callbackUrl", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
    return response;
  }
  
  // Auth routes - redirect to dashboard if already authenticated
  const isAuthRoute = authRoutes.some(route => 
    pathname.startsWith(route)
  );
  
  if (isAuthRoute && isAuthenticated) {
    const response = NextResponse.redirect(new URL("/dashboard", request.url));
    response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
    return response;
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - api routes (they handle their own auth)
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico, public files
     */
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\..*|public).*)",
  ],
};

