import { z } from "zod";
import { publicProcedure, router } from "../_core/trpc";
import { registerUser, loginUser, verifyToken, getUserById } from "../auth";
import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "../_core/cookies";

const AUTH_COOKIE_NAME = "auth_token";

export const localAuthRouter = router({
  /**
   * Register a new user
   */
  register: publicProcedure
    .input(
      z.object({
        email: z.string().email("有効なメールアドレスを入力してください"),
        password: z.string().min(6, "パスワードは6文字以上で入力してください"),
        name: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const result = await registerUser(input);
      
      if (result.success && result.token) {
        // Set auth cookie
        const cookieOptions = getSessionCookieOptions(ctx.req);
        ctx.res.cookie(AUTH_COOKIE_NAME, result.token, {
          ...cookieOptions,
          maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
        });
      }
      
      return result;
    }),

  /**
   * Login with email and password
   */
  login: publicProcedure
    .input(
      z.object({
        email: z.string().email("有効なメールアドレスを入力してください"),
        password: z.string().min(1, "パスワードを入力してください"),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const result = await loginUser(input);
      
      if (result.success && result.token) {
        // Set auth cookie
        const cookieOptions = getSessionCookieOptions(ctx.req);
        ctx.res.cookie(AUTH_COOKIE_NAME, result.token, {
          ...cookieOptions,
          maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
        });
      }
      
      return result;
    }),

  /**
   * Logout - clear auth cookie
   */
  logout: publicProcedure.mutation(({ ctx }) => {
    const cookieOptions = getSessionCookieOptions(ctx.req);
    ctx.res.clearCookie(AUTH_COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
    ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 }); // Also clear OAuth cookie
    return { success: true };
  }),

  /**
   * Get current user from auth token
   */
  me: publicProcedure.query(async ({ ctx }) => {
    // Parse cookies from header if ctx.req.cookies is empty
    let authToken: string | undefined;
    
    // First try ctx.req.cookies
    if (ctx.req.cookies && ctx.req.cookies[AUTH_COOKIE_NAME]) {
      authToken = ctx.req.cookies[AUTH_COOKIE_NAME];
    } else {
      // Fallback: parse cookie header directly
      const cookieHeader = ctx.req.headers.cookie;
      if (cookieHeader) {
        const cookies = cookieHeader.split(';').reduce((acc, cookie) => {
          const [key, value] = cookie.trim().split('=');
          if (key && value) {
            acc[key] = value;
          }
          return acc;
        }, {} as Record<string, string>);
        authToken = cookies[AUTH_COOKIE_NAME];
      }
    }
    
    if (authToken) {
      const user = await verifyToken(authToken);
      if (user) {
        return user;
      }
    }
    
    // Fall back to OAuth user if available
    if (ctx.user) {
      return {
        id: ctx.user.id,
        email: ctx.user.email || "",
        name: ctx.user.name,
        role: ctx.user.role,
      };
    }
    
    return null;
  }),
});
