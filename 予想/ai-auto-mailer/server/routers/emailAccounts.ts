import { z } from "zod";
import { protectedProcedure, publicProcedure, router } from "../_core/trpc";
import * as db from "../db";

export const emailAccountsRouter = router({
  /**
   * Get all email accounts for the current user
   */
  list: protectedProcedure.query(async ({ ctx }) => {
    return db.getEmailAccountsByUserId(ctx.user.id);
  }),

  /**
   * Get a specific email account by ID
   */
  getById: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      const account = await db.getEmailAccountById(input.id);
      return account;
    }),

  /**
   * Create a new email account
   */
  create: protectedProcedure
    .input(
      z.object({
        email: z.string().email(),
        imapHost: z.string().min(1),
        imapPort: z.number().min(1).max(65535).default(993),
        imapUsername: z.string().min(1),
        imapPassword: z.string().min(1),
        notificationEmail: z.string().email().optional(),
        chatworkRoomId: z.string().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      return db.createEmailAccount(ctx.user.id, {
        email: input.email,
        imapHost: input.imapHost,
        imapPort: input.imapPort,
        imapUsername: input.imapUsername,
        imapPassword: input.imapPassword,
        notificationEmail: input.notificationEmail || input.email,
        chatworkRoomId: input.chatworkRoomId,
      });
    }),

  /**
   * Update an email account
   */
  update: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        email: z.string().email().optional(),
        imapHost: z.string().min(1).optional(),
        imapPort: z.number().min(1).max(65535).optional(),
        imapUsername: z.string().min(1).optional(),
        imapPassword: z.string().min(1).optional(),
        notificationEmail: z.string().email().optional(),
        chatworkRoomId: z.string().optional(),
        isActive: z.enum(["active", "inactive"]).optional(),
      })
    )
    .mutation(async ({ input }) => {
      return db.updateEmailAccount(input.id, {
        email: input.email,
        imapHost: input.imapHost,
        imapPort: input.imapPort,
        imapUsername: input.imapUsername,
        imapPassword: input.imapPassword,
        notificationEmail: input.notificationEmail,
        chatworkRoomId: input.chatworkRoomId,
        isActive: input.isActive,
      });
    }),

  /**
   * Delete an email account
   */
  delete: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ ctx, input }) => {
      return db.deleteEmailAccount(ctx.user.id, input.id);
    }),

  /**
   * Test Chatwork notification
   */
  testChatworkNotification: publicProcedure
    .input(
      z.object({
        chatworkRoomId: z.string().min(1),
      })
    )
    .mutation(async ({ input }) => {
      const { sendChatworkNotification } = await import("../chatworkService");
      
      const testEmail = {
        sender: "test@example.com",
        senderName: "テストユーザー",
        subject: "テストメッセージ",
        summary: "これはChatwork通知のテストメッセージです。Room IDが正しく設定されていれば、このメッセージが表示されます。",
        importance: "high" as const,
        needsReply: "no" as const,
        receivedAt: new Date(),
        accountEmail: "test@example.com",
      };
      
      const result = await sendChatworkNotification(
        process.env.CHATWORK_API_TOKEN || "",
        input.chatworkRoomId,
        [testEmail],
        10
      );
      
      return {
        success: result,
        message: result 
          ? "テストメッセージを送信しました！Chatworkを確認してください。" 
          : "送信失敗: APIトークンまたはRoom IDを確認してください。",
      };
    }),

  /**
   * Test IMAP connection
   */
  testConnection: publicProcedure
    .input(
      z.object({
        imapHost: z.string().min(1),
        imapPort: z.number().min(1).max(65535),
        imapUsername: z.string().min(1),
        imapPassword: z.string().min(1),
      })
    )
    .mutation(async ({ input }) => {
      const { fetchNewEmails } = await import("../emailService");
      
      const result = await fetchNewEmails({
        id: 0,
        userId: 0,
        email: "",
        imapHost: input.imapHost,
        imapPort: input.imapPort,
        imapUsername: input.imapUsername,
        imapPassword: input.imapPassword,
        notificationEmail: "",
        chatworkRoomId: null,
        isActive: "active",
        lastCheckedAt: null,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      
      return {
        success: result.success,
        message: result.success 
          ? `接続成功！${result.count}件の新着メールが見つかりました。` 
          : `接続失敗: ${result.error}`,
      };
    }),
});
