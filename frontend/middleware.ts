import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export default function middleware(req: NextRequest) {

   // Log the request
   console.log('Request:', req);


  // Skip middleware for static files and auth routes
  if (
    req.nextUrl.pathname.startsWith('/_next/') ||
    req.nextUrl.pathname.startsWith('/api/auth/') ||
    req.nextUrl.pathname.startsWith('/favicon.ico') ||
    req.nextUrl.pathname.startsWith('/public/')
  ) {
    return NextResponse.next();
  }

  const response = NextResponse.next();

  // Check if session cookie exists
  const sessionCookie = req.cookies.get('aiqtoolkit-session');

  if (!sessionCookie) {
    // Generate a new session ID for visitors without one
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Set the session cookie
    response.cookies.set('aiqtoolkit-session', sessionId, {
      httpOnly: false,
      sameSite: 'lax',
      path: '/',
      secure: process.env.NODE_ENV === 'production',
      maxAge: 30 * 24 * 60 * 60, // 30 days
    });

    // Add session ID to headers for API routes
    if (req.nextUrl.pathname.startsWith('/api/')) {
      response.headers.set('x-session-id', sessionId);
    }
  } else {

    // Print session cookie
    console.log('Session cookie:', sessionCookie);

    // Add existing session ID to headers for API routes
    if (req.nextUrl.pathname.startsWith('/api/')) {
      response.headers.set('x-session-id', sessionCookie.value);
    }
  }

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (NextAuth API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!api/auth|_next/static|_next/image|favicon.ico|public).*)',
  ],
};
