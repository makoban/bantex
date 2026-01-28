import * as cron from "node-cron";
import * as db from "./db";
import { resetDbConnection } from "./db";
import { processAccountEmails } from "./emailService";
// メール送信機能は削除済み（さくらインターネットSMTP非対応のため）
import { sendChatworkNotification, EmailSummaryForNotification } from "./chatworkService";

let isRunning = false;

// 1回の通知で処理する最大メール数（chatworkServiceと同じ値）
const MAX_EMAILS_PER_NOTIFICATION = 15;

/**
 * Process all active email accounts (for all users)
 */
async function processAllAccounts() {
  if (isRunning) {
    console.log("[Batch] Previous batch still running, skipping...");
    return;
  }

  isRunning = true;
  console.log("[Batch] Starting email check batch process...");

  try {
    // Get active accounts (with retry) - this gets all active accounts from all users
    let activeAccounts = [];
    try {
      activeAccounts = await db.getActiveEmailAccounts();
    } catch (error) {
      console.error("[Batch] Error getting active accounts, resetting connection:", error);
      resetDbConnection();
      // Retry after reset
      try {
        activeAccounts = await db.getActiveEmailAccounts();
      } catch (retryError) {
        console.error("[Batch] Retry failed:", retryError);
        return;
      }
    }
    console.log(`[Batch] Found ${activeAccounts.length} active accounts`);

    // Process each account individually
    for (const account of activeAccounts) {
      try {
        console.log(`[Batch] Processing account: ${account.email} (user_id: ${account.userId})`);

        // Get user settings for this account's owner
        let userSettings = null;
        let defaultChatworkInterval = 10;
        let includeReplySuggestion = false;
        let sendEmptyNotification = false;
        let minimumImportance = "medium";
        if (account.userId) {
          try {
            userSettings = await db.getUserSettings(account.userId);
            defaultChatworkInterval = userSettings?.chatworkInterval || 10;
            includeReplySuggestion = userSettings?.includeReplySuggestion ?? false;
            sendEmptyNotification = userSettings?.sendEmptyNotification ?? false;
            minimumImportance = userSettings?.minimumImportance || "medium";
          } catch (error) {
            console.error(`[Batch] Error getting user settings for user ${account.userId}:`, error);
          }
        }

        // Process emails for this account
        const result = await processAccountEmails(account);
        console.log(
          `[Batch] Account ${account.email}: processed ${result.processed} emails, ${result.important} important`
        );

        if (result.errors.length > 0) {
          console.error(`[Batch] Errors for ${account.email}:`, result.errors);
        }

        // Get unnotified summaries (exclude spam/ads)
        let unnotified = [];
        try {
          unnotified = await db.getUnnotifiedSummaries(account.id);
        } catch (error) {
          console.error(`[Batch] Error getting unnotified summaries for ${account.email}:`, error);
          continue;
        }
        // Filter out spam emails and apply importance filter
        const toNotify = unnotified.filter(
          (s) => {
            // Always exclude spam
            if (s.importance === "spam") return false;
            
            // Apply minimum importance filter
            if (minimumImportance === "high") {
              // Only high importance emails
              return s.importance === "high";
            } else {
              // Medium and high importance emails (exclude low)
              return s.importance === "high" || s.importance === "medium";
            }
          }
        );

        // Check if we should send notification
        const shouldSendNotification = toNotify.length > 0 || sendEmptyNotification;
        
        if (shouldSendNotification && toNotify.length > 0) {
          console.log(
            `[Batch] Found ${toNotify.length} unnotified emails for ${account.email} (excluding spam)`
          );

          // 日付でソート（新しい順）
          const sortedEmails = toNotify.sort((a, b) => 
            new Date(b.receivedAt).getTime() - new Date(a.receivedAt).getTime()
          );

          // 最新のメールのみ通知対象（残りは通知済みにマーク）
          const emailsToNotify = sortedEmails.slice(0, MAX_EMAILS_PER_NOTIFICATION);
          const emailsToSkip = sortedEmails.slice(MAX_EMAILS_PER_NOTIFICATION);

          console.log(
            `[Batch] Will notify ${emailsToNotify.length} emails, skip ${emailsToSkip.length} old emails`
          );

          // Prepare emails for notification (Ver 7.0: replySuggestion追加)
          const emailsForNotification: EmailSummaryForNotification[] = emailsToNotify.map(summary => ({
            sender: summary.sender,
            senderName: summary.senderName || undefined,
            subject: summary.subject,
            summary: summary.summary,
            importance: summary.importance,
            needsReply: summary.needsReply || undefined,
            replyReason: summary.replyReason || undefined,
            replySuggestion: summary.replySuggestion || undefined,
            receivedAt: new Date(summary.receivedAt),
            accountEmail: account.email,
          }));

          // 全てのメールIDを通知済みにマーク（スキップしたものも含む）
          const allEmailIds = sortedEmails.map(s => s.id);

          let chatworkSent = false;
          let emailSent = false;

          // Send Chatwork notification (if configured)
          if (account.chatworkRoomId) {
            console.log(`[Batch] Sending Chatwork notification to room ${account.chatworkRoomId} for ${account.email}`);
            const chatworkResult = await sendChatworkNotification(
              process.env.CHATWORK_API_TOKEN || "",
              account.chatworkRoomId,
              emailsForNotification,
              defaultChatworkInterval,
              account.email,  // アカウント名を渡す
              includeReplySuggestion  // 返信案を含めるかどうか
            );

            if (chatworkResult) {
              chatworkSent = true;
              console.log(`[Batch] Chatwork notification sent successfully to ${account.chatworkRoomId}`);
            } else {
              console.error(`[Batch] Failed to send Chatwork notification to ${account.chatworkRoomId}`);
            }
          } else {
            console.log(`[Batch] No Chatwork Room ID configured for account ${account.email}`);
          }

          // メール送信機能は削除済み（チャットワーク通知のみ使用）

          const notificationSent = chatworkSent;

          // Mark ALL as notified if any notification was sent (including skipped old emails)
          if (notificationSent && allEmailIds.length > 0) {
            await db.markAsNotified(allEmailIds);
            console.log(`[Batch] Marked ${allEmailIds.length} emails as notified (including ${emailsToSkip.length} skipped)`);
          }
        } else if (toNotify.length === 0 && sendEmptyNotification) {
          // Send empty notification if configured
          console.log(
            `[Batch] No important emails for ${account.email}, but sending empty notification as configured`
          );
          
          if (account.chatworkRoomId) {
            // Send empty notification
            const emptyMessage = `[info][title]📧 ${account.email}[/title]現在、重要なメールはありません。[/info]`;
            
            try {
              const params = new URLSearchParams();
              params.append("body", emptyMessage);
              
              const response = await fetch(
                `https://api.chatwork.com/v2/rooms/${account.chatworkRoomId}/messages`,
                {
                  method: "POST",
                  headers: {
                    "X-ChatworkToken": process.env.CHATWORK_API_TOKEN || "",
                    "Content-Type": "application/x-www-form-urlencoded",
                  },
                  body: params.toString(),
                }
              );
              
              if (response.ok) {
                console.log(`[Batch] Empty notification sent successfully to ${account.chatworkRoomId}`);
              } else {
                console.error(`[Batch] Failed to send empty notification: ${response.status}`);
              }
            } catch (error) {
              console.error(`[Batch] Error sending empty notification:`, error);
            }
          }
          
          // Mark all unnotified emails as notified (even if they were filtered out)
          if (unnotified.length > 0) {
            const allEmailIds = unnotified.map(s => s.id);
            await db.markAsNotified(allEmailIds);
            console.log(`[Batch] Marked ${allEmailIds.length} filtered emails as notified`);
          }
        } else {
          console.log(
            `[Batch] No important emails for ${account.email} and empty notification is disabled`
          );
          
          // Mark all unnotified emails as notified (even if they were filtered out)
          if (unnotified.length > 0) {
            const allEmailIds = unnotified.map(s => s.id);
            await db.markAsNotified(allEmailIds);
            console.log(`[Batch] Marked ${allEmailIds.length} filtered emails as notified without sending notification`);
          }
        }
      } catch (error) {
        console.error(`[Batch] Error processing account ${account.email}:`, error);
      }
    }

    console.log("[Batch] Batch process completed");
  } catch (error) {
    console.error("[Batch] Fatal error in batch process:", error);
  } finally {
    isRunning = false;
  }
}

/**
 * Start the batch scheduler (runs every 5 minutes)
 */
export function startBatchScheduler() {
  // Run every 5 minutes: */5 * * * *
  const schedule = "*/5 * * * *";

  console.log(`[Batch] Starting scheduler with cron pattern: ${schedule}`);

  cron.schedule(schedule, () => {
    processAllAccounts();
  });

  // Run once immediately on startup
  setTimeout(() => {
    console.log("[Batch] Running initial batch process...");
    processAllAccounts();
  }, 5000); // Wait 5 seconds after server start

  console.log("[Batch] Scheduler started successfully");
}

/**
 * Manually trigger batch process (for testing)
 */
export async function triggerBatchManually() {
  await processAllAccounts();
}
