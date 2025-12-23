import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

// Routes that require authentication
const protectedRoutes = ["/dashboard"];

// Routes that should redirect to dashboard if already authenticated
const authRoutes = ["/login", "/register"];

/**
 * Check if a JWT token is expired
 * @param token - JWT token string
 * @returns true if token is expired or invalid
 */
function isTokenExpired(token: string): boolean {
  try {
    // JWT format: header.payload.signature
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    
    // Decode base64url payload
    const payload = JSON.parse(
      Buffer.from(parts[1].replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString()
    );
    
    const exp = payload.exp;
    if (!exp) return false; // No expiration = never expires
    
    // Check if expired (with 10 second buffer)
    return Date.now() >= (exp * 1000) - 10000;
  } catch {
    return true; // If we can't parse, consider it expired
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Check for NextAuth session token
  const token = await getToken({
    req: request,
    secret: process.env.NEXTAUTH_SECRET || "placeholder-secret",
  });
  
  // Also check for our custom JWT token in cookies
  const customToken = request.cookies.get("token")?.value;
  
  // Check if custom token is expired
  const isCustomTokenValid = customToken && !isTokenExpired(customToken);
  
  // User is authenticated if either token exists AND is valid
  const isAuthenticated = !!token || isCustomTokenValid;
  
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
    
    // Check if there was a token but it expired
    if (customToken && !isCustomTokenValid) {
      loginUrl.searchParams.set("expired", "true");
    }
    
    const response = NextResponse.redirect(loginUrl);
    response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
    
    // Clear the expired token cookie
    if (customToken && !isCustomTokenValid) {
      response.cookies.delete("token");
    }
    
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

