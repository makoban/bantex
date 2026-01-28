import { z } from "zod";
import { publicProcedure, router } from "../_core/trpc";
import * as db from "../db";

export const emailSummariesRouter = router({
  /**
   * Get email summaries for a specific account (time series)
   */
  listByAccount: publicProcedure
    .input(
      z.object({
        accountId: z.number(),
        limit: z.number().min(1).max(200).default(50),
      })
    )
    .query(async ({ input }) => {
      return db.getEmailSummariesByAccountId(input.accountId, input.limit);
    }),

  /**
   * Get email summaries grouped by sender
   */
  listBySender: publicProcedure
    .input(
      z.object({
        accountId: z.number(),
      })
    )
    .query(async ({ input }) => {
      // Get all summaries for the account
      const summaries = await db.getEmailSummariesByAccountId(input.accountId, 500);

      // Group by sender
      const grouped = summaries.reduce((acc, summary) => {
        if (!acc[summary.sender]) {
          acc[summary.sender] = [];
        }
        acc[summary.sender].push(summary);
        return acc;
      }, {} as Record<string, typeof summaries>);

      // Convert to array format with sender info
      return Object.entries(grouped).map(([sender, emails]) => ({
        sender,
        count: emails.length,
        emails: emails,
        latestReceivedAt: emails[0]?.receivedAt || new Date(),
      }));
    }),

  /**
   * Get email summaries for a specific sender
   */
  listForSender: publicProcedure
    .input(
      z.object({
        accountId: z.number(),
        sender: z.string(),
      })
    )
    .query(async ({ input }) => {
      return db.getEmailSummariesBySender(input.accountId, input.sender);
    }),

  /**
   * Get statistics for an account
   */
  getStats: publicProcedure
    .input(z.object({ accountId: z.number() }))
    .query(async ({ input }) => {
      const summaries = await db.getEmailSummariesByAccountId(input.accountId, 1000);

      const stats = {
        total: summaries.length,
        high: summaries.filter((s) => s.importance === "high").length,
        medium: summaries.filter((s) => s.importance === "medium").length,
        low: summaries.filter((s) => s.importance === "low").length,
        spam: summaries.filter((s) => s.importance === "spam").length,
        uniqueSenders: new Set(summaries.map((s) => s.sender)).size,
      };

      return stats;
    }),
});
