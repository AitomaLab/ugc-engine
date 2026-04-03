import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Auth middleware — checks for Supabase session cookies.
 * 
 * Supabase stores its auth tokens in cookies prefixed with "sb-".
 * We check for the presence of these cookies to determine if the user is logged in.
 * This avoids the complexity of @supabase/ssr server-side session validation
 * and works reliably with the client-side signInWithPassword() flow.
 */
export async function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;

  // Public routes that don't require auth
  const publicRoutes = ['/login', '/signup', '/forgot-password', '/reset-password'];
  const isPublicRoute = publicRoutes.some(route => path.startsWith(route));

  // Check for Supabase auth cookie (set by @supabase/supabase-js client)
  // Supabase stores tokens in cookies like "sb-<project-ref>-auth-token"
  const cookies = req.cookies.getAll();
  const hasAuthCookie = cookies.some(c => 
    c.name.includes('sb-') && c.name.includes('auth-token')
  );

  // If not logged in and not on a public route, redirect to login
  if (!hasAuthCookie && !isPublicRoute) {
    const loginUrl = new URL('/login', req.url);
    loginUrl.searchParams.set('redirectTo', path);
    return NextResponse.redirect(loginUrl);
  }

  // If logged in and on login/signup, redirect to home
  // (but NOT forgot-password/reset-password — recovery sessions need those pages)
  const redirectAuthRoutes = ['/login', '/signup'];
  const shouldRedirectAuth = redirectAuthRoutes.some(route => path.startsWith(route));
  if (hasAuthCookie && shouldRedirectAuth) {
    return NextResponse.redirect(new URL('/', req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all routes except static files and Next.js internals
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
};
