import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import * as db from "../db";

export const userSettingsRouter = router({
  // Get user settings
  get: protectedProcedure.query(async ({ ctx }) => {
    const settings = await db.getUserSettings(ctx.user.id);
    return settings;
  }),

  // Update user settings
  update: protectedProcedure
    .input(
      z.object({
        chatworkRoomId: z.string().optional(),
        chatworkInterval: z.number().optional(),
        personalName: z.string().optional(),
        companyName: z.string().optional(),
        additionalKeywords: z.string().optional(),
        ignorePromotions: z.boolean().optional(),
        ignoreSales: z.boolean().optional(),
        detectReplyNeeded: z.boolean().optional(),
        includeReplySuggestion: z.boolean().optional(),
        sendEmptyNotification: z.boolean().optional(),
        minimumImportance: z.enum(["medium", "high"]).optional(),
        customPrompt: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      const settings = await db.upsertUserSettings(ctx.user.id, input);
      return settings;
    }),

  // Get ignored senders list
  getIgnoredSenders: protectedProcedure.query(async ({ ctx }) => {
    const senders = await db.getIgnoredSenders(ctx.user.id);
    return senders;
  }),

  // Add sender to ignore list
  addIgnoredSender: protectedProcedure
    .input(
      z.object({
        senderEmail: z.string().email(),
        senderName: z.string().optional(),
        reason: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      const sender = await db.addIgnoredSender(ctx.user.id, input);
      return sender;
    }),

  // Remove sender from ignore list
  removeIgnoredSender: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ ctx, input }) => {
      await db.removeIgnoredSender(ctx.user.id, input.id);
      return { success: true };
    }),
});
