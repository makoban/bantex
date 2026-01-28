import { exec } from "child_process";
import { promisify } from "util";
import { analyzeEmail as analyzeEmailWithGemini, AnalyzeEmailOptions } from "./llm";
import * as db from "./db";
import { EmailAccount } from "../drizzle/schema";

const execAsync = promisify(exec);

interface FetchedEmail {
  message_id: string;
  sender: string;
  sender_name: string;
  subject: string;
  body: string;
  received_at: number;
}

interface FetchEmailsResult {
  success: boolean;
  emails: FetchedEmail[];
  count: number;
  error?: string;
}

interface EmailAnalysis {
  summary: string;
  importance: "high" | "medium" | "low" | "spam";
  senderName: string;
  needsReply: "yes" | "no" | "unknown";
  replyReason: string;
  replySuggestion: string;
}

/**
 * Fetch new emails from IMAP server using Python script
 */
export async function fetchNewEmails(account: EmailAccount): Promise<FetchEmailsResult> {
  try {
    const pythonPath = "python3";
    const scriptPath = "./server/imap_client.py";
    
    const lastChecked = account.lastCheckedAt 
      ? new Date(account.lastCheckedAt).getTime() 
      : 0;
    
    console.log(`[IMAP] Fetching emails for ${account.email}, lastChecked: ${lastChecked} (${account.lastCheckedAt || 'never'})`);
    
    const command = `${pythonPath} ${scriptPath} "${account.imapHost}" ${account.imapPort} "${account.imapUsername}" "${account.imapPassword}" ${lastChecked}`;
    
    const { stdout, stderr } = await execAsync(command, { maxBuffer: 10 * 1024 * 1024 });
    
    // Log Python stderr output for debugging
    if (stderr) {
      console.log(`[IMAP Python] ${stderr}`);
    }
    
    const result: FetchEmailsResult = JSON.parse(stdout);
    
    console.log(`[IMAP] Fetched ${result.count} emails from ${account.email}, success: ${result.success}`);
    if (result.error) {
      console.log(`[IMAP] Error: ${result.error}`);
    }
    
    return result;
  } catch (error) {
    console.error("[IMAP] Error fetching emails:", error);
    return {
      success: false,
      emails: [],
      count: 0,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

/**
 * Analyze email content using AI to determine importance and generate summary
 * Ver 7.0: 返信例生成を追加
 */
export async function analyzeEmail(email: FetchedEmail, options: AnalyzeEmailOptions = {}): Promise<EmailAnalysis> {
  try {
    console.log(`[AI] Analyzing email: ${email.subject} from ${email.sender}`);
    const result = await analyzeEmailWithGemini(email.sender, email.subject, email.body, options);
    console.log(`[AI] Analysis result: importance=${result.importance}, needsReply=${result.needsReply}, senderName=${result.senderName}`);
    if (result.replySuggestion) {
      console.log(`[AI] Reply suggestion generated (${result.replySuggestion.length} chars)`);
    }
    return {
      summary: result.summary,
      importance: result.importance,
      senderName: result.senderName,
      needsReply: result.needsReply,
      replyReason: result.replyReason,
      replySuggestion: result.replySuggestion,
    };
  } catch (error) {
    console.error("[AI] Error analyzing email:", error);
    // Fallback to medium importance if analysis fails
    return {
      summary: `${email.sender}から「${email.subject}」についてのメール`,
      importance: "medium",
      senderName: email.sender.split("@")[0],
      needsReply: "unknown",
      replyReason: "",
      replySuggestion: "",
    };
  }
}

/**
 * Process new emails for an account: fetch, analyze, and store
 */
export async function processAccountEmails(account: EmailAccount): Promise<{
  processed: number;
  important: number;
  errors: string[];
}> {
  const errors: string[] = [];
  let processed = 0;
  let important = 0;

  try {
    // Get user settings for AI analysis (if user_id exists)
    let userSettings = null;
    let ignoredSenderEmails: string[] = [];
    
    if (account.userId) {
      try {
        userSettings = await db.getUserSettings(account.userId);
        const ignoredSenders = await db.getIgnoredSenders(account.userId);
        ignoredSenderEmails = ignoredSenders.map(s => s.senderEmail);
      } catch (error) {
        console.error(`[Process] Error getting user settings for user ${account.userId}:`, error);
      }
    }

    // Fetch new emails
    const fetchResult = await fetchNewEmails(account);
    
    if (!fetchResult.success) {
      errors.push(`Failed to fetch emails: ${fetchResult.error}`);
      return { processed, important, errors };
    }

    console.log(`[Process] Processing ${fetchResult.emails.length} emails for ${account.email}`);

    // Process each email
    for (const email of fetchResult.emails) {
      try {
        // Check if email already exists
        const exists = await db.checkEmailExists(account.id, email.message_id);
        if (exists) {
          console.log(`[Process] Skipping existing email: ${email.message_id}`);
          continue;
        }

        // Check if sender is ignored (only if user_id exists)
        if (account.userId) {
          const isIgnored = await db.isIgnoredSender(account.userId, email.sender);
          if (isIgnored) {
            console.log(`[Process] Skipping ignored sender: ${email.sender}`);
            continue;
          }
        }

        console.log(`[Process] Processing new email: ${email.subject}`);

        // Analyze email with AI (with user settings)
        const analysis = await analyzeEmail(email, {
          userSettings,
          ignoredSenders: ignoredSenderEmails,
        });

        // Store email summary with extended fields (including replySuggestion)
        await db.createEmailSummary({
          accountId: account.id,
          messageId: email.message_id,
          sender: email.sender,
          senderName: analysis.senderName,
          subject: email.subject,
          summary: analysis.summary,
          importance: analysis.importance,
          needsReply: analysis.needsReply,
          replyReason: analysis.replyReason,
          replySuggestion: analysis.replySuggestion,
          isNotified: "no",
          receivedAt: new Date(email.received_at),
        });

        processed++;
        
        // Count important emails (not spam or low priority)
        if (analysis.importance === "high" || analysis.importance === "medium") {
          important++;
        }
      } catch (error) {
        console.error(`[Process] Error processing email ${email.message_id}:`, error);
        errors.push(`Error processing email ${email.message_id}: ${error}`);
      }
    }

    // Update last checked timestamp
    await db.updateEmailAccount(account.id, {
      lastCheckedAt: new Date(),
    });

    return { processed, important, errors };
  } catch (error) {
    console.error(`[Process] Error processing account ${account.email}:`, error);
    errors.push(`Error processing account: ${error}`);
    return { processed, important, errors };
  }
}
