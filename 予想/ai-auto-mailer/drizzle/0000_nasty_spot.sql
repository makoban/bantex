CREATE TYPE "public"."importance" AS ENUM('high', 'medium', 'low', 'spam');--> statement-breakpoint
CREATE TYPE "public"."is_active" AS ENUM('active', 'inactive');--> statement-breakpoint
CREATE TYPE "public"."is_notified" AS ENUM('yes', 'no');--> statement-breakpoint
CREATE TYPE "public"."needs_reply" AS ENUM('yes', 'no', 'unknown');--> statement-breakpoint
CREATE TYPE "public"."role" AS ENUM('user', 'admin');--> statement-breakpoint
CREATE TABLE "email_accounts" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "email_accounts_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"user_id" integer,
	"email" varchar(320) NOT NULL,
	"imap_host" varchar(255) NOT NULL,
	"imap_port" integer DEFAULT 993 NOT NULL,
	"imap_username" varchar(320) NOT NULL,
	"imap_password" text NOT NULL,
	"notification_email" varchar(320) NOT NULL,
	"chatwork_room_id" varchar(255),
	"is_active" "is_active" DEFAULT 'active' NOT NULL,
	"last_checked_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "email_summaries" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "email_summaries_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"account_id" integer NOT NULL,
	"message_id" varchar(512) NOT NULL,
	"sender" varchar(320) NOT NULL,
	"sender_name" varchar(255),
	"subject" text NOT NULL,
	"summary" text NOT NULL,
	"importance" "importance" NOT NULL,
	"needs_reply" "needs_reply" DEFAULT 'unknown',
	"reply_reason" text,
	"is_notified" "is_notified" DEFAULT 'no' NOT NULL,
	"received_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ignored_senders" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "ignored_senders_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"user_id" integer,
	"sender_email" varchar(320) NOT NULL,
	"sender_name" varchar(255),
	"reason" text,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "user_settings" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "user_settings_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"user_id" integer,
	"chatwork_room_id" varchar(255),
	"personal_name" varchar(255),
	"company_name" varchar(255),
	"additional_keywords" text,
	"ignore_promotions" boolean DEFAULT true,
	"ignore_sales" boolean DEFAULT true,
	"detect_reply_needed" boolean DEFAULT true,
	"custom_prompt" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "users_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"openId" varchar(64) NOT NULL,
	"name" text,
	"email" varchar(320),
	"loginMethod" varchar(64),
	"role" "role" DEFAULT 'user' NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	"lastSignedIn" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_openId_unique" UNIQUE("openId")
);
--> statement-breakpoint
ALTER TABLE "email_summaries" ADD CONSTRAINT "email_summaries_account_id_email_accounts_id_fk" FOREIGN KEY ("account_id") REFERENCES "public"."email_accounts"("id") ON DELETE cascade ON UPDATE no action;