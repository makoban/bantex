import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { triggerBatchManually } from "../batchScheduler";
import * as db from "../db";

export const batchRouter = router({
  /**
   * Manually trigger batch process (for testing)
   */
  triggerManually: protectedProcedure.mutation(async () => {
    await triggerBatchManually();
    
    return {
      success: true,
      message: "Batch process triggered successfully",
    };
  }),

  /**
   * Reset summaries for a specific account
   */
  resetAccount: protectedProcedure
    .input(z.object({ accountId: z.number() }))
    .mutation(async ({ ctx, input }) => {
      await db.resetAccountSummaries(ctx.user.id, input.accountId);
      
      return {
        success: true,
        message: "Account summaries reset successfully. Next batch will re-analyze all emails.",
      };
    }),

  /**
   * Reset all summaries for all accounts
   */
  resetAll: protectedProcedure.mutation(async ({ ctx }) => {
    await db.resetAllSummaries(ctx.user.id);
    
    return {
      success: true,
      message: "All summaries reset successfully. Next batch will re-analyze all emails.",
    };
  }),

  /**
   * Get summary count
   */
  getSummaryCount: protectedProcedure
    .input(z.object({ accountId: z.number().optional() }).optional())
    .query(async ({ ctx, input }) => {
      const count = await db.getSummaryCount(ctx.user.id, input?.accountId);
      return { count };
    }),
});
