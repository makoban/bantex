ALTER TABLE "user_settings" ADD COLUMN "include_reply_suggestion" boolean DEFAULT false;--> statement-breakpoint
ALTER TABLE "user_settings" ADD COLUMN "send_empty_notification" boolean DEFAULT false;--> statement-breakpoint
ALTER TABLE "user_settings" ADD COLUMN "minimum_importance" varchar(20) DEFAULT 'medium';