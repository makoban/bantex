import { integer, pgEnum, pgTable, text, timestamp, varchar, boolean } from "drizzle-orm/pg-core";

/**
 * Core user table backing auth flow.
 * Extend this file with additional tables as your product grows.
 * Columns use camelCase to match both database fields and generated types.
 */

// Enums
export const roleEnum = pgEnum("role", ["user", "admin"]);
export const isActiveEnum = pgEnum("is_active", ["active", "inactive"]);
export const importanceEnum = pgEnum("importance", ["high", "medium", "low", "spam"]);
export const isNotifiedEnum = pgEnum("is_notified", ["yes", "no"]);
export const needsReplyEnum = pgEnum("needs_reply", ["yes", "no", "unknown"]);

export const users = pgTable("users", {
  /**
   * Surrogate primary key. Auto-incremented numeric value managed by the database.
   * Use this for relations between tables.
   */
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  /** Manus OAuth identifier (openId) returned from the OAuth callback. Unique per user. */
  openId: varchar("openId", { length: 64 }).unique(),  // Made nullable for local auth
  /** Email address for local authentication */
  email: varchar("email", { length: 320 }).notNull().unique(),
  /** Hashed password for local authentication */
  passwordHash: text("password_hash"),
  name: text("name"),
  loginMethod: varchar("loginMethod", { length: 64 }).default("local"),
  role: roleEnum("role").default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

/**
 * User settings table for AI analysis customization
 */
export const userSettings = pgTable("user_settings", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  userId: integer("user_id"),  // Nullable for prototype
  
  // Chatwork settings (per user, not per email account)
  chatworkRoomId: varchar("chatwork_room_id", { length: 255 }),
  chatworkInterval: integer("chatwork_interval").default(10),  // Notification interval in minutes (10, 20, 60)
  
  // Personal info for AI analysis
  personalName: varchar("personal_name", { length: 255 }),  // User's name for importance detection
  companyName: varchar("company_name", { length: 255 }),    // Company name for importance detection
  additionalKeywords: text("additional_keywords"),          // Comma-separated keywords to mark as important
  
  // AI analysis options
  ignorePromotions: boolean("ignore_promotions").default(true),  // Auto-ignore promotional emails
  ignoreSales: boolean("ignore_sales").default(true),            // Auto-ignore sales emails
  detectReplyNeeded: boolean("detect_reply_needed").default(true), // Detect if reply is needed
  includeReplySuggestion: boolean("include_reply_suggestion").default(false), // Include reply suggestion in Chatwork notification
  
  // Notification filter options
  sendEmptyNotification: boolean("send_empty_notification").default(false), // Send notification even if no important emails
  minimumImportance: varchar("minimum_importance", { length: 20 }).default("medium"), // Minimum importance level to send ("medium" or "high")
  
  // Custom AI prompt (optional override)
  customPrompt: text("custom_prompt"),
  
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export type UserSettings = typeof userSettings.$inferSelect;
export type InsertUserSettings = typeof userSettings.$inferInsert;

/**
 * Ignored senders table for filtering out unwanted emails
 */
export const ignoredSenders = pgTable("ignored_senders", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  userId: integer("user_id"),  // Nullable for prototype
  senderEmail: varchar("sender_email", { length: 320 }).notNull(),
  senderName: varchar("sender_name", { length: 255 }),
  reason: text("reason"),  // Why this sender is ignored
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export type IgnoredSender = typeof ignoredSenders.$inferSelect;
export type InsertIgnoredSender = typeof ignoredSenders.$inferInsert;

/**
 * Email accounts table for storing IMAP configuration
 */
export const emailAccounts = pgTable("email_accounts", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  userId: integer("user_id"),  // Made nullable for prototype (no auth)
  email: varchar("email", { length: 320 }).notNull(),
  imapHost: varchar("imap_host", { length: 255 }).notNull(),
  imapPort: integer("imap_port").notNull().default(993),
  imapUsername: varchar("imap_username", { length: 320 }).notNull(),
  imapPassword: text("imap_password").notNull(),
  notificationEmail: varchar("notification_email", { length: 320 }).notNull(),
  chatworkRoomId: varchar("chatwork_room_id", { length: 255 }),  // Keep for backward compatibility
  isActive: isActiveEnum("is_active").default("active").notNull(),
  lastCheckedAt: timestamp("last_checked_at"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
});

export type EmailAccount = typeof emailAccounts.$inferSelect;
export type InsertEmailAccount = typeof emailAccounts.$inferInsert;

/**
 * Email summaries table for storing analyzed email data
 */
export const emailSummaries = pgTable("email_summaries", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  accountId: integer("account_id").notNull().references(() => emailAccounts.id, { onDelete: "cascade" }),
  messageId: varchar("message_id", { length: 512 }).notNull(),
  sender: varchar("sender", { length: 320 }).notNull(),           // Original email address
  senderName: varchar("sender_name", { length: 255 }),            // Extracted sender name from email content
  subject: text("subject").notNull(),
  summary: text("summary").notNull(),
  importance: importanceEnum("importance").notNull(),
  needsReply: needsReplyEnum("needs_reply").default("unknown"),   // Does user need to reply?
  replyReason: text("reply_reason"),                              // Why reply is needed
  replySuggestion: text("reply_suggestion"),                        // AI-generated reply suggestion
  isNotified: isNotifiedEnum("is_notified").default("no").notNull(),
  receivedAt: timestamp("received_at").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export type EmailSummary = typeof emailSummaries.$inferSelect;
export type InsertEmailSummary = typeof emailSummaries.$inferInsert;
