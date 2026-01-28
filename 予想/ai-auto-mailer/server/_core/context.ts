import type { CreateExpressContextOptions } from "@trpc/server/adapters/express";
import type { User } from "../../drizzle/schema";
import { sdk } from "./sdk";
import { verifyToken } from "../auth";

const AUTH_COOKIE_NAME = "auth_token";

// Helper function to parse cookies from header
function parseCookies(cookieHeader: string | undefined): Record<string, string> {
  if (!cookieHeader) return {};
  return cookieHeader.split(';').reduce((acc, cookie) => {
    const [key, value] = cookie.trim().split('=');
    if (key && value) {
      acc[key] = value;
    }
    return acc;
  }, {} as Record<string, string>);
}

export type TrpcContext = {
  req: CreateExpressContextOptions["req"];
  res: CreateExpressContextOptions["res"];
  user: User | null;
};

export async function createContext(
  opts: CreateExpressContextOptions
): Promise<TrpcContext> {
  let user: User | null = null;

  // Parse cookies - try req.cookies first, then fallback to header parsing
  let authToken: string | undefined;
  if (opts.req.cookies && opts.req.cookies[AUTH_COOKIE_NAME]) {
    authToken = opts.req.cookies[AUTH_COOKIE_NAME];
  } else {
    // Fallback: parse cookie header directly
    const cookies = parseCookies(opts.req.headers.cookie);
    authToken = cookies[AUTH_COOKIE_NAME];
  }

  // Try local auth token
  if (authToken) {
    try {
      const authUser = await verifyToken(authToken);
      if (authUser) {
        // Convert AuthUser to User type
        user = {
          id: authUser.id,
          openId: null,
          email: authUser.email,
          passwordHash: null,
          name: authUser.name || null,
          loginMethod: "local",
          role: authUser.role,
          createdAt: new Date(),
          updatedAt: new Date(),
          lastSignedIn: new Date(),
        };
      }
    } catch (error) {
      // Token verification failed, continue to OAuth
      user = null;
    }
  }

  // If no local auth, try OAuth
  if (!user) {
    try {
      user = await sdk.authenticateRequest(opts.req);
    } catch (error) {
      // Authentication is optional for public procedures.
      user = null;
    }
  }

  return {
    req: opts.req,
    res: opts.res,
    user,
  };
}
