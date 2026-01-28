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
