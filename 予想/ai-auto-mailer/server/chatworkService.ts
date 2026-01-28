/**
 * Chatwork API integration for sending email summaries
 * Ver 7.1: より自然な秘書スタイルの通知フォーマット
 */

interface ChatworkMessage {
  body: string;
}

export interface EmailSummaryForNotification {
  sender: string;
  senderName?: string;
  subject: string;
  summary: string;
  importance: "high" | "medium" | "low" | "spam";
  needsReply?: "yes" | "no" | "unknown";
  replyReason?: string;
  replySuggestion?: string;
  receivedAt: Date;
  accountEmail?: string;
}

// Chatworkのメッセージ上限（安全マージンを考慮して3500文字）
const MAX_MESSAGE_LENGTH = 3500;
// 1回の通知で送信する最大メール数
const MAX_EMAILS_PER_NOTIFICATION = 15;

/**
 * AI秘書スタイルのメッセージ本文を生成（Ver 7.1: より自然な文体）
 */
function buildSecretaryMessage(
  emails: EmailSummaryForNotification[],
  accountEmail: string,
  totalCount: number,
  skippedCount: number,
  includeReplySuggestion: boolean = false
): string {
  // カテゴリ別に分類
  const needsReply = emails.filter(e => e.needsReply === "yes" && e.importance !== "spam");
  const confirmOnly = emails.filter(e => 
    (e.importance === "high" || e.importance === "medium") && 
    e.needsReply !== "yes"
  );
  const spamOrLow = emails.filter(e => e.importance === "spam" || e.importance === "low");

  // 必要なメールの件数
  const importantCount = needsReply.length + confirmOnly.length;

  // ヘッダー（より自然な秘書スタイル）
  let messageBody = `[info][title]📧 ${accountEmail}[/title]`;
  messageBody += `ただいま${totalCount}件のメールを受信しました。`;
  
  if (importantCount > 0) {
    messageBody += `必要そうなメールは次の通り${importantCount}件です。\n`;
  } else {
    messageBody += `重要なメールはありませんでした。\n`;
  }

  // 番号付きで返信が必要なメールを表示
  let itemNumber = 1;
  
  if (needsReply.length > 0) {
    needsReply.forEach(email => {
      const sender = email.senderName || email.sender.split("@")[0];
      
      messageBody += `\n${getCircledNumber(itemNumber)}お相手：${sender}様\n`;
      messageBody += `　内容：${email.summary}\n`;
      
      // 返信例がある場合は表示（設定で有効にしている場合のみ）
      if (includeReplySuggestion && email.replySuggestion) {
        const suggestion = email.replySuggestion.replace(/\n/g, " ");
        messageBody += `\n　返信例：${suggestion}\n`;
      }
      
      itemNumber++;
    });
  }

  // 確認のみのメール（件数制限なし）
  if (confirmOnly.length > 0) {
    confirmOnly.forEach(email => {
      const sender = email.senderName || email.sender.split("@")[0];
      
      messageBody += `\n${getCircledNumber(itemNumber)}お相手：${sender}様\n`;
      messageBody += `　内容：${email.summary}\n`;
      messageBody += `\n　※確認のみ（返信不要）\n`;
      
      itemNumber++;
    });
  }

  // 営業・宣伝メール（件数のみ）
  if (spamOrLow.length > 0) {
    messageBody += `\n※営業・宣伝メール${spamOrLow.length}件は省略しました。\n`;
  }

  // スキップした古いメールがある場合
  if (skippedCount > 0) {
    messageBody += `\n※他${skippedCount}件は古いため省略しました。\n`;
  }

  messageBody += `\n以上となります。[/info]`;

  return messageBody;
}

/**
 * 丸数字を取得
 */
function getCircledNumber(num: number): string {
  const circledNumbers = ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩', '⑪', '⑫', '⑬', '⑭', '⑮'];
  if (num >= 1 && num <= 15) {
    return circledNumbers[num - 1];
  }
  return `(${num})`;
}

/**
 * コンパクトなメッセージを生成（緊急時用）
 */
function buildCompactMessage(
  emails: EmailSummaryForNotification[],
  accountEmail: string,
  totalCount: number,
  skippedCount: number
): string {
  const needsReply = emails.filter(e => e.needsReply === "yes" && e.importance !== "spam");
  const confirmOnly = emails.filter(e => 
    (e.importance === "high" || e.importance === "medium") && 
    e.needsReply !== "yes"
  );
  const spamOrLow = emails.filter(e => e.importance === "spam" || e.importance === "low");
  const importantCount = needsReply.length + confirmOnly.length;

  let messageBody = `[info][title]📧 ${accountEmail}[/title]`;
  messageBody += `ただいま${totalCount}件のメールを受信しました。必要そうなメールは${importantCount}件です。\n`;
  
  if (needsReply.length > 0) {
    const top = needsReply[0];
    const sender = top.senderName || top.sender.split("@")[0];
    messageBody += `\n①お相手：${sender}様\n`;
    messageBody += `　内容：${top.subject.substring(0, 40)}...\n`;
    if (needsReply.length > 1) {
      messageBody += `　...他${needsReply.length - 1}件\n`;
    }
  }
  
  if (confirmOnly.length > 0) {
    messageBody += `\n※確認のみ：${confirmOnly.length}件\n`;
  }
  
  if (spamOrLow.length > 0) {
    messageBody += `※営業・宣伝：${spamOrLow.length}件（省略）\n`;
  }
  
  if (skippedCount > 0) {
    messageBody += `\n※他${skippedCount}件は古いため省略\n`;
  }
  
  messageBody += `\n以上となります。詳細はWebで確認してください。[/info]`;
  
  return messageBody;
}

/**
 * Send email summary to Chatwork room (AI秘書スタイル)
 */
export async function sendChatworkNotification(
  apiToken: string,
  roomId: string,
  emails: EmailSummaryForNotification[],
  intervalMinutes: number = 10,
  accountEmail?: string,
  includeReplySuggestion: boolean = false
): Promise<boolean> {
  if (!apiToken || !roomId || emails.length === 0) {
    console.log("[Chatwork] Missing required parameters");
    return false;
  }

  try {
    const accountDisplay = accountEmail || "メール";
    const totalCount = emails.length;
    
    // メールが多すぎる場合は最新のものだけを通知
    const emailsToNotify = emails
      .sort((a, b) => new Date(b.receivedAt).getTime() - new Date(a.receivedAt).getTime())
      .slice(0, MAX_EMAILS_PER_NOTIFICATION);
    
    const skippedCount = totalCount - emailsToNotify.length;
    
    console.log(`[Chatwork] Processing ${emailsToNotify.length} of ${totalCount} emails for ${accountDisplay}`);
    
    // AI秘書スタイルのメッセージを生成
    let messageBody = buildSecretaryMessage(
      emailsToNotify,
      accountDisplay,
      totalCount,
      skippedCount,
      includeReplySuggestion
    );

    // メッセージが長すぎる場合は短縮
    if (messageBody.length > MAX_MESSAGE_LENGTH) {
      console.log(`[Chatwork] Message too long (${messageBody.length} chars), using compact format`);
      messageBody = buildCompactMessage(emailsToNotify, accountDisplay, totalCount, skippedCount);
    }

    // Send to Chatwork API
    const params = new URLSearchParams();
    params.append("body", messageBody);

    const response = await fetch(
      `https://api.chatwork.com/v2/rooms/${roomId}/messages`,
      {
        method: "POST",
        headers: {
          "X-ChatworkToken": apiToken,
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: params.toString(),
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error(
        `[Chatwork] Error sending message: ${response.status} ${errorText}`
      );
      return false;
    }

    console.log(
      `[Chatwork] Successfully sent ${emailsToNotify.length} email summaries to room ${roomId}`
    );
    return true;
  } catch (error) {
    console.error("[Chatwork] Error sending notification:", error);
    return false;
  }
}
