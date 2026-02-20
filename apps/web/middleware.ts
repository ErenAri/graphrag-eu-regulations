import { NextRequest, NextResponse } from "next/server";

const ALLOWED_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // This service does not rely on the image optimizer endpoint.
  if (pathname === "/_next/image") {
    return new NextResponse(null, { status: 404 });
  }

  // Reject server-action style invocations; this application exposes read-only routes.
  if (request.headers.has("next-action")) {
    return NextResponse.json({ error: "server_actions_disabled" }, { status: 403 });
  }

  if (!ALLOWED_METHODS.has(request.method)) {
    return NextResponse.json({ error: "method_not_allowed" }, { status: 405 });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/webpack-hmr|favicon.ico).*)"]
};
