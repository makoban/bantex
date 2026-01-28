import { eq, desc, and, sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import { InsertUser, users, emailAccounts, EmailAccount, InsertEmailAccount, emailSummaries, EmailSummary, InsertEmailSummary, userSettings, UserSettings, InsertUserSettings, ignoredSenders, IgnoredSender, InsertIgnoredSender } from "../drizzle/schema";
import { ENV } from './_core/env';

let _db: ReturnType<typeof drizzle> | null = null;
let _client: ReturnType<typeof postgres> | null = null;

// Reset database connection
export function resetDbConnection() {
  console.log("[Database] Resetting connection...");
  _db = null;
  _client = null;
}

// Lazily create the drizzle instance so local tooling can run without a DB.
export async function getDb() {
  if (!_db && process.env.DATABASE_URL) {
    try {
      _client = postgres(process.env.DATABASE_URL, {
        ssl: 'require',
        max: 20,
        idle_timeout: 60,
        connect_timeout: 30,
        max_lifetime: 60 * 30,
        onnotice: () => {}, // Suppress notices
      });
      _db = drizzle(_client);
      console.log("[Database] Connection established");
    } catch (error) {
      console.warn("[Database] Failed to connect:", error);
      _db = null;
    }
  }
  return _db;
}

// Get raw postgres client for raw SQL queries
export async function getRawClient() {
  // Ensure database is initialized first
  await getDb();
  return _client;
}

export async function upsertUser(user: InsertUser): Promise<void> {
  if (!user.openId) {
    throw new Error("User openId is required for upsert");
  }

  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot upsert user: database not available");
    return;
  }

  try {
    const values: InsertUser = {
      email: user.email || `${user.openId}@oauth.local`,  // Fallback email for OAuth users
      openId: user.openId || null,
    };
    const updateSet: Record<string, unknown> = {};

    const textFields = ["name", "loginMethod"] as const;
    type TextField = (typeof textFields)[number];

    const assignNullable = (field: TextField) => {
      const value = user[field];
      if (value === undefined) return;
      const normalized = value ?? null;
      values[field] = normalized;
      updateSet[field] = normalized;
    };

    textFields.forEach(assignNullable);

    // Handle email separately (required field)
    if (user.email !== undefined) {
      values.email = user.email;
      updateSet.email = user.email;
    }

    if (user.lastSignedIn !== undefined) {
      values.lastSignedIn = user.lastSignedIn;
      updateSet.lastSignedIn = user.lastSignedIn;
    }
    if (user.role !== undefined) {
      values.role = user.role;
      updateSet.role = user.role;
    } else if (user.openId === ENV.ownerOpenId) {
      values.role = 'admin';
      updateSet.role = 'admin';
    }

    if (!values.lastSignedIn) {
      values.lastSignedIn = new Date();
    }

    if (Object.keys(updateSet).length === 0) {
      updateSet.lastSignedIn = new Date();
    }

    await db.insert(users).values(values)
      .onConflictDoUpdate({
        target: users.openId,
        set: updateSet,
      });
  } catch (error) {
    console.error("[Database] Failed to upsert user:", error);
    throw error;
  }
}

export async function getUserByOpenId(openId: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.openId, openId)).limit(1);

  return result.length > 0 ? result[0] : undefined;
}

// ==================== User Settings ====================

export async function getUserSettings(userId: number): Promise<UserSettings | null> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM user_settings WHERE user_id = ${userId} LIMIT 1
  `;
  
  if (result.length === 0) return null;
  
  const row = result[0] as any;
  return {
    id: row.id,
    userId: row.user_id,
    chatworkRoomId: row.chatwork_room_id,
    chatworkInterval: row.chatwork_interval || 10,
    personalName: row.personal_name,
    companyName: row.company_name,
    additionalKeywords: row.additional_keywords,
    ignorePromotions: row.ignore_promotions,
    ignoreSales: row.ignore_sales,
    detectReplyNeeded: row.detect_reply_needed,
    includeReplySuggestion: row.include_reply_suggestion,
    sendEmptyNotification: row.send_empty_notification,
    minimumImportance: row.minimum_importance,
    customPrompt: row.custom_prompt,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  } as UserSettings;
}

export async function upsertUserSettings(userId: number, settings: Partial<InsertUserSettings>): Promise<UserSettings> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Check if settings exist for this user
  const existing = await getUserSettings(userId);
  
  if (existing) {
    // Update existing
    await client`
      UPDATE user_settings SET
        chatwork_room_id = ${settings.chatworkRoomId ?? existing.chatworkRoomId},
        chatwork_interval = ${settings.chatworkInterval ?? existing.chatworkInterval ?? 10},
        personal_name = ${settings.personalName ?? existing.personalName},
        company_name = ${settings.companyName ?? existing.companyName},
        additional_keywords = ${settings.additionalKeywords ?? existing.additionalKeywords},
        ignore_promotions = ${settings.ignorePromotions ?? existing.ignorePromotions},
        ignore_sales = ${settings.ignoreSales ?? existing.ignoreSales},
        detect_reply_needed = ${settings.detectReplyNeeded ?? existing.detectReplyNeeded},
        include_reply_suggestion = ${settings.includeReplySuggestion ?? existing.includeReplySuggestion},
        send_empty_notification = ${settings.sendEmptyNotification ?? existing.sendEmptyNotification},
        minimum_importance = ${settings.minimumImportance ?? existing.minimumImportance},
        custom_prompt = ${settings.customPrompt ?? existing.customPrompt},
        updated_at = NOW()
      WHERE id = ${existing.id}
    `;
  } else {
    // Insert new with user_id
    await client`
      INSERT INTO user_settings (
        user_id, chatwork_room_id, chatwork_interval, personal_name, company_name, additional_keywords,
        ignore_promotions, ignore_sales, detect_reply_needed, include_reply_suggestion,
        send_empty_notification, minimum_importance, custom_prompt
      ) VALUES (
        ${userId},
        ${settings.chatworkRoomId || null},
        ${settings.chatworkInterval || 10},
        ${settings.personalName || null},
        ${settings.companyName || null},
        ${settings.additionalKeywords || null},
        ${settings.ignorePromotions ?? true},
        ${settings.ignoreSales ?? true},
        ${settings.detectReplyNeeded ?? true},
        ${settings.includeReplySuggestion ?? false},
        ${settings.sendEmptyNotification ?? false},
        ${settings.minimumImportance || 'medium'},
        ${settings.customPrompt || null}
      )
    `;
  }
  
  return (await getUserSettings(userId))!;
}

// ==================== Ignored Senders ====================

export async function getIgnoredSenders(userId: number): Promise<IgnoredSender[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM ignored_senders WHERE user_id = ${userId} ORDER BY created_at DESC
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    userId: row.user_id,
    senderEmail: row.sender_email,
    senderName: row.sender_name,
    reason: row.reason,
    createdAt: row.created_at,
  })) as IgnoredSender[];
}

export async function addIgnoredSender(userId: number, sender: InsertIgnoredSender): Promise<IgnoredSender> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  await client`
    INSERT INTO ignored_senders (user_id, sender_email, sender_name, reason)
    VALUES (${userId}, ${sender.senderEmail}, ${sender.senderName || null}, ${sender.reason || null})
  `;
  
  const result = await client`
    SELECT * FROM ignored_senders WHERE user_id = ${userId} AND sender_email = ${sender.senderEmail} ORDER BY id DESC LIMIT 1
  `;
  
  const row = result[0] as any;
  return {
    id: row.id,
    userId: row.user_id,
    senderEmail: row.sender_email,
    senderName: row.sender_name,
    reason: row.reason,
    createdAt: row.created_at,
  } as IgnoredSender;
}

export async function removeIgnoredSender(userId: number, id: number): Promise<void> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  await client`DELETE FROM ignored_senders WHERE id = ${id} AND user_id = ${userId}`;
}

export async function isIgnoredSender(userId: number, senderEmail: string): Promise<boolean> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT 1 FROM ignored_senders WHERE user_id = ${userId} AND sender_email = ${senderEmail} LIMIT 1
  `;
  
  return result.length > 0;
}

// ==================== Email Accounts ====================

export async function createEmailAccount(userId: number, account: Omit<InsertEmailAccount, 'userId'>): Promise<EmailAccount> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const { email, imapHost, imapPort, imapUsername, imapPassword, notificationEmail, chatworkRoomId } = account as any;
  
  // Use raw SQL to avoid Drizzle's PostgreSQL-style quoting
  const result = await client`
    INSERT INTO email_accounts (user_id, email, imap_host, imap_port, imap_username, imap_password, notification_email, chatwork_room_id)
    VALUES (${userId}, ${email}, ${imapHost}, ${imapPort || 993}, ${imapUsername}, ${imapPassword}, ${notificationEmail}, ${chatworkRoomId || null})
  `;
  
  // Get the last inserted record
  const inserted = await client`
    SELECT * FROM email_accounts WHERE user_id = ${userId} AND email = ${email} ORDER BY id DESC LIMIT 1
  `;
  
  return inserted[0] as EmailAccount;
}

export async function getEmailAccountById(id: number): Promise<EmailAccount> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  const result = await db.select().from(emailAccounts).where(eq(emailAccounts.id, id)).limit(1);
  if (result.length === 0) throw new Error("Email account not found");
  return result[0];
}

export async function getEmailAccountsByUserId(userId: number): Promise<EmailAccount[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM email_accounts WHERE user_id = ${userId} ORDER BY created_at DESC
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    userId: row.user_id,
    email: row.email,
    imapHost: row.imap_host,
    imapPort: row.imap_port,
    imapUsername: row.imap_username,
    imapPassword: row.imap_password,
    notificationEmail: row.notification_email,
    chatworkRoomId: row.chatwork_room_id,
    isActive: row.is_active,
    lastCheckedAt: row.last_checked_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  })) as EmailAccount[];
}

export async function getAllEmailAccounts(): Promise<EmailAccount[]> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  return db.select().from(emailAccounts);
}

export async function getActiveEmailAccounts(): Promise<EmailAccount[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Use raw SQL to avoid Drizzle's PostgreSQL-style quoting
  const result = await client`
    SELECT * FROM email_accounts WHERE is_active = 'active'
  `;
  
  // Map snake_case column names to camelCase property names
  return (result as any[]).map(row => ({
    id: row.id,
    userId: row.user_id,
    email: row.email,
    imapHost: row.imap_host,
    imapPort: row.imap_port,
    imapUsername: row.imap_username,
    imapPassword: row.imap_password,
    notificationEmail: row.notification_email,
    chatworkRoomId: row.chatwork_room_id,
    isActive: row.is_active,
    lastCheckedAt: row.last_checked_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  })) as EmailAccount[];
}

export async function getActiveEmailAccountsByUserId(userId: number): Promise<EmailAccount[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM email_accounts WHERE user_id = ${userId} AND is_active = 'active'
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    userId: row.user_id,
    email: row.email,
    imapHost: row.imap_host,
    imapPort: row.imap_port,
    imapUsername: row.imap_username,
    imapPassword: row.imap_password,
    notificationEmail: row.notification_email,
    chatworkRoomId: row.chatwork_room_id,
    isActive: row.is_active,
    lastCheckedAt: row.last_checked_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  })) as EmailAccount[];
}

export async function updateEmailAccount(id: number, updates: Partial<InsertEmailAccount>): Promise<void> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  await db.update(emailAccounts).set(updates).where(eq(emailAccounts.id, id));
}

export async function deleteEmailAccount(userId: number, id: number): Promise<void> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Only delete if the account belongs to the user
  await client`DELETE FROM email_accounts WHERE id = ${id} AND user_id = ${userId}`;
}

// ==================== Email Summaries ====================

export async function createEmailSummary(summary: InsertEmailSummary & { senderName?: string; needsReply?: string; replyReason?: string; replySuggestion?: string }): Promise<EmailSummary> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Convert Date to ISO string for PostgreSQL
  const receivedAtStr = summary.receivedAt instanceof Date 
    ? summary.receivedAt.toISOString() 
    : summary.receivedAt;
  
  // Try with reply_suggestion column first, fallback without it
  try {
    await client`
      INSERT INTO email_summaries (account_id, message_id, sender, sender_name, subject, summary, importance, needs_reply, reply_reason, reply_suggestion, received_at)
      VALUES (
        ${summary.accountId}, 
        ${summary.messageId}, 
        ${summary.sender}, 
        ${summary.senderName || null},
        ${summary.subject}, 
        ${summary.summary}, 
        ${summary.importance}, 
        ${summary.needsReply || 'unknown'},
        ${summary.replyReason || null},
        ${summary.replySuggestion || null},
        ${receivedAtStr}
      )
    `;
  } catch (error: any) {
    // If reply_suggestion column doesn't exist, insert without it
    if (error?.message?.includes('reply_suggestion') || error?.cause?.message?.includes('reply_suggestion')) {
      console.log('[DB] reply_suggestion column not found, inserting without it');
      await client`
        INSERT INTO email_summaries (account_id, message_id, sender, sender_name, subject, summary, importance, needs_reply, reply_reason, received_at)
        VALUES (
          ${summary.accountId}, 
          ${summary.messageId}, 
          ${summary.sender}, 
          ${summary.senderName || null},
          ${summary.subject}, 
          ${summary.summary}, 
          ${summary.importance}, 
          ${summary.needsReply || 'unknown'},
          ${summary.replyReason || null},
          ${receivedAtStr}
        )
      `;
    } else {
      throw error;
    }
  }
  
  // Get the last inserted record by messageId
  const result = await client`
    SELECT id, account_id, message_id, sender, sender_name, subject, summary, 
           importance, needs_reply, reply_reason, is_notified, received_at, created_at
    FROM email_summaries WHERE message_id = ${summary.messageId} LIMIT 1
  `;
  return result[0] as EmailSummary;
}

export async function getEmailSummariesByAccountId(accountId: number, limit: number = 50): Promise<EmailSummary[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM email_summaries 
    WHERE account_id = ${accountId}
    ORDER BY received_at DESC
    LIMIT ${limit}
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    accountId: row.account_id,
    messageId: row.message_id,
    sender: row.sender,
    senderName: row.sender_name,
    subject: row.subject,
    summary: row.summary,
    importance: row.importance,
    needsReply: row.needs_reply,
    replyReason: row.reply_reason,
    replySuggestion: row.reply_suggestion,
    isNotified: row.is_notified,
    receivedAt: row.received_at,
    createdAt: row.created_at,
  })) as EmailSummary[];
}

export async function getEmailSummariesByUserId(userId: number, limit: number = 100): Promise<EmailSummary[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Get summaries for all accounts belonging to the user
  const result = await client`
    SELECT es.* FROM email_summaries es
    INNER JOIN email_accounts ea ON es.account_id = ea.id
    WHERE ea.user_id = ${userId}
    ORDER BY es.received_at DESC
    LIMIT ${limit}
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    accountId: row.account_id,
    messageId: row.message_id,
    sender: row.sender,
    senderName: row.sender_name,
    subject: row.subject,
    summary: row.summary,
    importance: row.importance,
    needsReply: row.needs_reply,
    replyReason: row.reply_reason,
    replySuggestion: row.reply_suggestion,
    isNotified: row.is_notified,
    receivedAt: row.received_at,
    createdAt: row.created_at,
  })) as EmailSummary[];
}

export async function getEmailSummariesBySender(accountId: number, sender: string): Promise<EmailSummary[]> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  return db.select().from(emailSummaries)
    .where(and(eq(emailSummaries.accountId, accountId), eq(emailSummaries.sender, sender)))
    .orderBy(desc(emailSummaries.receivedAt));
}

export async function checkEmailExists(accountId: number, messageId: string): Promise<boolean> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Use raw SQL to avoid schema mismatch issues with new columns
  const result = await client`
    SELECT id FROM email_summaries 
    WHERE account_id = ${accountId} AND message_id = ${messageId}
    LIMIT 1
  `;
  
  return result.length > 0;
}

export async function getUnnotifiedSummaries(accountId: number): Promise<EmailSummary[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Use explicit column list to handle schema differences between environments
  const result = await client`
    SELECT id, account_id, message_id, sender, sender_name, subject, summary, 
           importance, needs_reply, reply_reason, is_notified, received_at, created_at,
           COALESCE(reply_suggestion, '') as reply_suggestion
    FROM email_summaries 
    WHERE account_id = ${accountId} AND is_notified = 'no'
    ORDER BY received_at DESC
  `.catch(async () => {
    // Fallback if reply_suggestion column doesn't exist
    return await client`
      SELECT id, account_id, message_id, sender, sender_name, subject, summary, 
             importance, needs_reply, reply_reason, is_notified, received_at, created_at
      FROM email_summaries 
      WHERE account_id = ${accountId} AND is_notified = 'no'
      ORDER BY received_at DESC
    `;
  });
  
  return (result as any[]).map(row => ({
    id: row.id,
    accountId: row.account_id,
    messageId: row.message_id,
    sender: row.sender,
    senderName: row.sender_name,
    subject: row.subject,
    summary: row.summary,
    importance: row.importance,
    needsReply: row.needs_reply,
    replyReason: row.reply_reason,
    replySuggestion: row.reply_suggestion || null,
    isNotified: row.is_notified,
    receivedAt: row.received_at,
    createdAt: row.created_at,
  })) as EmailSummary[];
}

export async function markAsNotified(ids: number[]): Promise<void> {
  const db = await getDb();
  if (!db) throw new Error("Database not available");
  
  for (const id of ids) {
    await db.update(emailSummaries).set({ isNotified: "yes" }).where(eq(emailSummaries.id, id));
  }
}

// Get all email summaries (for display) - kept for backward compatibility
export async function getAllEmailSummaries(limit: number = 100): Promise<EmailSummary[]> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  const result = await client`
    SELECT * FROM email_summaries 
    ORDER BY received_at DESC
    LIMIT ${limit}
  `;
  
  return (result as any[]).map(row => ({
    id: row.id,
    accountId: row.account_id,
    messageId: row.message_id,
    sender: row.sender,
    senderName: row.sender_name,
    subject: row.subject,
    summary: row.summary,
    importance: row.importance,
    needsReply: row.needs_reply,
    replyReason: row.reply_reason,
    replySuggestion: row.reply_suggestion,
    isNotified: row.is_notified,
    receivedAt: row.received_at,
    createdAt: row.created_at,
  })) as EmailSummary[];
}

// ==================== Reset & Re-analyze ====================

/**
 * Reset all email summaries for an account (delete all summaries and reset last_checked_at)
 */
export async function resetAccountSummaries(userId: number, accountId: number): Promise<void> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Verify the account belongs to the user
  const account = await client`SELECT id FROM email_accounts WHERE id = ${accountId} AND user_id = ${userId}`;
  if (account.length === 0) throw new Error("Account not found or access denied");
  
  // Delete all summaries for this account
  await client`DELETE FROM email_summaries WHERE account_id = ${accountId}`;
  
  // Reset last_checked_at to null so all emails will be re-fetched
  await client`UPDATE email_accounts SET last_checked_at = NULL WHERE id = ${accountId}`;
}

/**
 * Reset all email summaries for all accounts of a user
 */
export async function resetAllSummaries(userId: number): Promise<void> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  // Delete all summaries for accounts belonging to this user
  await client`
    DELETE FROM email_summaries 
    WHERE account_id IN (SELECT id FROM email_accounts WHERE user_id = ${userId})
  `;
  
  // Reset last_checked_at for all accounts of this user
  await client`UPDATE email_accounts SET last_checked_at = NULL WHERE user_id = ${userId}`;
}

/**
 * Get summary count for an account
 */
export async function getSummaryCount(userId: number, accountId?: number): Promise<number> {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  if (accountId) {
    const result = await client`
      SELECT COUNT(*) as count FROM email_summaries es
      INNER JOIN email_accounts ea ON es.account_id = ea.id
      WHERE es.account_id = ${accountId} AND ea.user_id = ${userId}
    `;
    return parseInt((result[0] as any).count, 10);
  } else {
    const result = await client`
      SELECT COUNT(*) as count FROM email_summaries es
      INNER JOIN email_accounts ea ON es.account_id = ea.id
      WHERE ea.user_id = ${userId}
    `;
    return parseInt((result[0] as any).count, 10);
  }
}

// ==================== User Management ====================

export async function getUserByEmail(email: string) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.email, email)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function getUserById(id: number) {
  const db = await getDb();
  if (!db) {
    console.warn("[Database] Cannot get user: database not available");
    return undefined;
  }

  const result = await db.select().from(users).where(eq(users.id, id)).limit(1);
  return result.length > 0 ? result[0] : undefined;
}

export async function createLocalUser(user: { email: string; passwordHash: string; name?: string }) {
  const client = await getRawClient();
  if (!client) throw new Error("Database not available");
  
  await client`
    INSERT INTO users (email, password_hash, name, "loginMethod", role)
    VALUES (${user.email}, ${user.passwordHash}, ${user.name || null}, 'local', 'user')
  `;
  
  const result = await client`
    SELECT * FROM users WHERE email = ${user.email} LIMIT 1
  `;
  
  return result[0];
}
