import nodemailer from "nodemailer";
import { EmailSummary } from "../drizzle/schema";

interface NotificationConfig {
  smtpHost: string;
  smtpPort: number;
  smtpUser: string;
  smtpPassword: string;
  fromEmail: string;
}

/**
 * Send notification email with important email summaries
 * Ver 7.0: AI秘書スタイルの通知フォーマット
 */
export async function sendNotificationEmail(
  toEmail: string,
  accountEmail: string,
  summaries: EmailSummary[],
  config?: NotificationConfig
): Promise<{ success: boolean; error?: string }> {
  try {
    // Filter out spam emails
    const nonSpamSummaries = summaries.filter(
      (s) => s.importance !== "spam"
    );

    if (nonSpamSummaries.length === 0) {
      return { success: true }; // No emails to notify
    }

    // Use default SMTP config if not provided
    const smtpConfig = config || {
      smtpHost: process.env.SMTP_HOST || "smtp.gmail.com",
      smtpPort: parseInt(process.env.SMTP_PORT || "587"),
      smtpUser: process.env.SMTP_USER || "",
      smtpPassword: process.env.SMTP_PASSWORD || "",
      fromEmail: process.env.SMTP_FROM || "noreply@automailer.com",
    };

    // Debug log for SMTP config
    console.log(`[Email] SMTP Config: host=${smtpConfig.smtpHost}, port=${smtpConfig.smtpPort}, user=${smtpConfig.smtpUser}, from=${smtpConfig.fromEmail}`);

    // Create transporter
    const transporter = nodemailer.createTransport({
      host: smtpConfig.smtpHost,
      port: smtpConfig.smtpPort,
      secure: smtpConfig.smtpPort === 465,
      auth: {
        user: smtpConfig.smtpUser,
        pass: smtpConfig.smtpPassword,
      },
    });

    // Group summaries by category (AI秘書スタイル)
    const needsReply = nonSpamSummaries.filter(
      (s) => s.needsReply === "yes" && s.importance !== "spam"
    );
    const confirmOnly = nonSpamSummaries.filter(
      (s) => (s.importance === "high" || s.importance === "medium") && s.needsReply !== "yes"
    );
    const lowPriority = nonSpamSummaries.filter(
      (s) => s.importance === "low"
    );

    // Build email content (AI秘書スタイル)
    const subject = `【AI秘書】${accountEmail} - ${nonSpamSummaries.length}件のメールを確認しました`;

    let htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
    .container { background: white; border-radius: 12px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .header { text-align: center; margin-bottom: 30px; }
    .header h1 { margin: 0; font-size: 24px; color: #333; }
    .header .subtitle { color: #666; margin-top: 8px; }
    .account-badge { display: inline-block; background: #667eea; color: white; padding: 5px 15px; border-radius: 20px; font-size: 14px; margin-top: 10px; }
    .section { margin-bottom: 30px; }
    .section-title { font-size: 16px; font-weight: bold; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #eee; }
    .section-title.reply { color: #e74c3c; border-bottom-color: #e74c3c; }
    .section-title.confirm { color: #3498db; border-bottom-color: #3498db; }
    .section-title.low { color: #95a5a6; border-bottom-color: #95a5a6; }
    .email-item { background: #f8f9fa; padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #667eea; }
    .email-item.reply { border-left-color: #e74c3c; }
    .email-item.confirm { border-left-color: #3498db; }
    .email-sender { font-weight: bold; color: #333; font-size: 15px; }
    .email-subject { color: #555; margin: 8px 0; font-size: 14px; }
    .email-summary { color: #666; font-size: 14px; margin: 10px 0; padding: 10px; background: white; border-radius: 5px; }
    .reply-suggestion { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin-top: 10px; }
    .reply-suggestion-title { font-weight: bold; color: #856404; margin-bottom: 8px; }
    .reply-suggestion-text { color: #333; font-size: 13px; white-space: pre-wrap; }
    .footer { text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📧 AI秘書からのご報告</h1>
      <p class="subtitle">本日${nonSpamSummaries.length}件のメールを確認しました</p>
      <span class="account-badge">${accountEmail}</span>
    </div>
`;

    // 【返信をお勧め】セクション
    if (needsReply.length > 0) {
      htmlContent += `
    <div class="section">
      <div class="section-title reply">📝 返信をお勧め (${needsReply.length}件)</div>
`;
      for (const summary of needsReply) {
        const senderName = summary.senderName || summary.sender.split("@")[0];
        const receivedDate = new Date(summary.receivedAt).toLocaleString("ja-JP");
        htmlContent += `
      <div class="email-item reply">
        <div class="email-sender">${senderName}様より</div>
        <div class="email-subject">${summary.subject}</div>
        <div class="email-summary">→ ${summary.summary}</div>
`;
        // 返信例がある場合は表示
        if (summary.replySuggestion) {
          htmlContent += `
        <div class="reply-suggestion">
          <div class="reply-suggestion-title">💡 返信案</div>
          <div class="reply-suggestion-text">${summary.replySuggestion}</div>
        </div>
`;
        }
        htmlContent += `
        <div style="font-size: 12px; color: #999; margin-top: 10px;">${receivedDate}</div>
      </div>
`;
      }
      htmlContent += `    </div>`;
    }

    // 【確認のみ】セクション
    if (confirmOnly.length > 0) {
      htmlContent += `
    <div class="section">
      <div class="section-title confirm">📋 確認のみ (${confirmOnly.length}件)</div>
`;
      for (const summary of confirmOnly) {
        const senderName = summary.senderName || summary.sender.split("@")[0];
        htmlContent += `
      <div class="email-item confirm">
        <div class="email-sender">${senderName}様</div>
        <div class="email-summary">${summary.summary}</div>
      </div>
`;
      }
      htmlContent += `    </div>`;
    }

    // 【低優先度】セクション（件数のみ）
    if (lowPriority.length > 0) {
      htmlContent += `
    <div class="section">
      <div class="section-title low">📁 低優先度 (${lowPriority.length}件)</div>
      <p style="color: #666; font-size: 14px;">詳細はWebで確認できます</p>
    </div>
`;
    }

    htmlContent += `
    <div class="footer">
      <p>このメールはAI Auto Mailer（AI秘書）から自動送信されています</p>
    </div>
  </div>
</body>
</html>
`;

    // Send email
    await transporter.sendMail({
      from: `"AI秘書" <${smtpConfig.fromEmail}>`,
      to: toEmail,
      subject: subject,
      html: htmlContent,
    });

    return { success: true };
  } catch (error) {
    console.error("Error sending notification email:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
