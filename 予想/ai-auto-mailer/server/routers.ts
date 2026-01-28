import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";
import { emailAccountsRouter } from "./routers/emailAccounts";
import { emailSummariesRouter } from "./routers/emailSummaries";
import { batchRouter } from "./routers/batch";
import { userSettingsRouter } from "./routers/userSettings";
import { localAuthRouter } from "./routers/localAuth";

export const appRouter = router({
    // if you need to use socket.io, read and register route in server/_core/index.ts, all api should start with '/api/' so that the gateway can route correctly
  system: systemRouter,
  // Local authentication (email/password)
  localAuth: localAuthRouter,
  // OAuth authentication (kept for backward compatibility)
  auth: router({
    me: publicProcedure.query(opts => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return {
        success: true,
      } as const;
    }),
  }),

  emailAccounts: emailAccountsRouter,
  emailSummaries: emailSummariesRouter,
  batch: batchRouter,
  userSettings: userSettingsRouter,
});

export type AppRouter = typeof appRouter;
