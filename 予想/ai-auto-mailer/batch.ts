/**
 * Standalone batch script for Render Cron Job
 * This script runs independently from the web server
 * メール送信機能は削除済み（チャットワーク通知のみ使用）
 */

import "dotenv/config";
import * as db from "./server/db";
import * as emailService from "./server/emailService";

async function runBatch() {
  console.log("[Batch] Starting batch process...");
  
  try {
    // Get all active email accounts
    const accounts = await db.getActiveEmailAccounts();
    console.log(`[Batch] Found ${accounts.length} active accounts`);

    if (accounts.length === 0) {
      console.log("[Batch] No active accounts to process");
      return;
    }

    // Process each account
    for (const account of accounts) {
      console.log(`[Batch] Processing account: ${account.email}`);
      
      try {
        const result = await emailService.processAccountEmails(account);
        console.log(`[Batch] Processed ${result.processed} emails, ${result.important} important`);

        if (result.errors.length > 0) {
          console.error(`[Batch] Errors for ${account.email}:`, result.errors);
        }

        // メール送信機能は削除済み（チャットワーク通知はbatchScheduler.tsで処理）
      } catch (error) {
        console.error(`[Batch] Error processing account ${account.email}:`, error);
      }
    }

    console.log("[Batch] Batch process completed successfully");
  } catch (error) {
    console.error("[Batch] Fatal error in batch process:", error);
    process.exit(1);
  }
}

// Run the batch
runBatch()
  .then(() => {
    console.log("[Batch] Exiting...");
    process.exit(0);
  })
  .catch((error) => {
    console.error("[Batch] Unhandled error:", error);
    process.exit(1);
  });
