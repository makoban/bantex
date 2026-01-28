import { GoogleGenerativeAI } from "@google/generative-ai";
import { UserSettings } from "../drizzle/schema";

export interface AnalyzeEmailResult {
  summary: string;
  importance: "high" | "medium" | "low" | "spam";
  senderName: string;
  needsReply: "yes" | "no" | "unknown";
  replyReason: string;
  replySuggestion: string;
}

export interface AnalyzeEmailOptions {
  userSettings?: UserSettings | null;
  ignoredSenders?: string[];
}

/**
 * Analyze email content using Gemini API with user settings
 * Ver 7.0: AI秘書機能 - 返信例生成を追加
 */
export async function analyzeEmail(
  sender: string,
  subject: string,
  body: string,
  options: AnalyzeEmailOptions = {}
): Promise<AnalyzeEmailResult> {
  try {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      throw new Error("GEMINI_API_KEY is not set");
    }

    const { userSettings, ignoredSenders = [] } = options;

    // Check if sender is in ignored list
    if (ignoredSenders.includes(sender)) {
      return {
        summary: "無視リストの送信者",
        importance: "spam",
        senderName: sender,
        needsReply: "no",
        replyReason: "",
        replySuggestion: "",
      };
    }

    // Check if sender is AImail (this app's notification)
    if (sender.toLowerCase().includes("aimail") || 
        sender.toLowerCase().includes("ai-mail") ||
        sender.toLowerCase().includes("auto-mailer")) {
      return {
        summary: "AIメール通知（自動無視）",
        importance: "spam",
        senderName: "AImail",
        needsReply: "no",
        replyReason: "",
        replySuggestion: "",
      };
    }

    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ 
      model: "gemini-2.0-flash",
      generationConfig: {
        responseMimeType: "application/json",
      },
    });

    // Build custom instructions based on user settings
    let customInstructions = "";
    let userName = userSettings?.personalName || "ユーザー";
    let companyName = userSettings?.companyName || "";
    
    if (userSettings) {
      if (userSettings.personalName) {
        customInstructions += `\n- 「${userSettings.personalName}」という名前が含まれている場合は重要度を「high」にしてください`;
      }
      if (userSettings.companyName) {
        customInstructions += `\n- 「${userSettings.companyName}」という会社名が含まれている場合は重要度を上げてください`;
      }
      if (userSettings.additionalKeywords) {
        const keywords = userSettings.additionalKeywords.split(",").map(k => k.trim()).filter(k => k);
        if (keywords.length > 0) {
          customInstructions += `\n- 以下のキーワードが含まれている場合は重要度を上げてください: ${keywords.join(", ")}`;
        }
      }
      if (userSettings.ignorePromotions) {
        customInstructions += `\n- プロモーション、ニュースレター、広告メールは「spam」として判定してください`;
      }
      if (userSettings.ignoreSales) {
        customInstructions += `\n- 営業メール、セールス、勧誘メールは「spam」として判定してください`;
      }
      if (userSettings.customPrompt) {
        customInstructions += `\n\n追加の指示:\n${userSettings.customPrompt}`;
      }
    }

    const detectReplyNeeded = userSettings?.detectReplyNeeded ?? true;

    const prompt = `あなたは優秀なビジネス秘書AIです。以下のメールを分析し、ユーザーのために必要な情報と対応案を提供してください。

送信者メールアドレス: ${sender}
件名: ${subject}
本文:
${body.substring(0, 3000)} ${body.length > 3000 ? "..." : ""}

以下のJSON形式で回答してください：
{
  "summary": "メールの要約（秘書として報告するスタイル）",
  "importance": "high/medium/low/spam",
  "senderName": "送信者の人名（必ずメール本文から抽出）",
  "needsReply": "yes/no/unknown",
  "replyReason": "返信が必要な理由",
  "replySuggestion": "返信例（needsReplyがyesの場合のみ）"
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【あなたの役割 - AI秘書】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
あなたはユーザー「${userName}」${companyName ? `（${companyName}）` : ""}の優秀な秘書です。
メールの内容を読み解き、ユーザーが取るべきアクションを判断してください。

秘書として：
- 重要なメールを見逃さない
- 営業・広告メールは簡潔に処理
- 返信が必要なメールには返信案を提案
- ユーザーの時間を節約する

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【送信者名の抽出 - 最重要】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
メールアドレスではなく、必ずメール本文から人名を抽出してください。

抽出の優先順位：
1. 署名部分から人名を探す（例：「山田太郎」「田中 花子」「Yamada Taro」）
2. 本文冒頭の「○○です」「○○と申します」から人名を探す
3. 本文末尾の「○○より」「○○拝」から人名を探す
4. 上記で見つからない場合のみ、メールアドレスの@より前の部分を使用

注意：
- 会社名やサービス名ではなく、個人名を抽出
- 日本語名は「姓名」の順で（例：「山田太郎」）
- 敬称（様、さん等）は除外

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【要約の書き方 - 秘書スタイル】★最重要★
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ 絶対に守るルール：
- 「確認」「依頼」「連絡」のような1〜2語だけの要約は禁止
- 必ず「何についての」「何をすべきか」を具体的に書く
- メールに含まれる具体的な情報（年度、日付、金額、製品名など）は必ず要約に含める

■ 営業・広告・プロモーションメール（importance: spam/low）
→ 20〜30文字の簡潔な要約
例：「○○製品のセール案内（50%オフ）」「△△サービスの新機能紹介」「週刊メルマガ」

■ 業務メール（importance: high/medium）
→ 秘書が上司に報告するような文体で要約
→ 80〜150文字程度（短すぎは禁止）
→ メールに書かれている具体的な情報をすべて含める：
  1. 具体的な日付・期限（「22日」「来週月曜」など）
  2. 具体的な依頼内容をすべて列挙（「返却」と「見積もり」など複数あれば両方書く）
  3. 年度・金額・製品名など数字や固有名詞
  4. 相手が求めているアクション

業務メールの要約例：
✅ 良い例：「山田様より22日の書類の返却依頼と見積もりのお願いです。」
✅ 良い例：「ABC社の田中様より2024年度の契約更新書類の確認依頼です。今週金曜日までにご返信をお願いされています。」
✅ 良い例：「経理部より2020年の書類確認依頼です。確認後にお電話をお願いされています。」
❌ 悪い例：「書類を返却」「確認」「連絡」←具体的な日付や複数の依頼が抜けている

■ 要約が短くなりそうな場合のチェックリスト：
- 何年の書類/案件か記載したか？
- 何をすべきか（確認、返信、電話など）記載したか？
- 期限はあるか？あれば記載したか？
- 相手が求めているアクションは明確か？

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【重要度の判定基準】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- high: 緊急対応が必要、重要な取引先、契約関連、直接依頼、返信期限あり
- medium: 通常の業務連絡、情報共有、一般的な問い合わせ
- low: 参考情報、社内の一般的なお知らせ、CCで送られてきた情報
- spam: 営業メール、広告、迷惑メール、自動通知、メルマガ、フィッシングメール

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【フィッシング・迷惑メール判定 - 重要】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
送信者アドレスや件名から、これが迷惑メール・フィッシングメールかどうかを判断してください。

■ 以下の特徴があれば「spam」と判定：

1. フィッシングメールの特徴：
   - 「アカウント停止」「緊急」「本人確認が必要」「24時間以内」などの煽り文句
   - 送信者ドメインが公式と異なる（例: jcb.co.jp ではなく jcb-security.com）
   - 不自然な日本語、文法ミス
   - 「こちらをクリック」でログインを促す

2. 自動通知メール（返信不要）：
   - カード利用通知（JCB、三菱UFJ、楽天カード等）
   - 請求確定・引き落とし通知
   - ログイン通知、パスワードリセット通知
   - サービスからの自動送信メール（no-reply@など）

3. 判断基準：
   - 送信者アドレスが「no-reply」「noreply」「info」「support」など一般的なものは自動通知の可能性大
   - 本文に「このメールに返信しないでください」があれば自動通知
   - 企業からの一方的な通知で、ユーザーのアクションを求めていないものはspam/low

■ 本当に重要なメール（spam判定しない）：
- 個人名で送られてきた業務メール
- 具体的な案件・プロジェクトについての連絡
- 返信や対応を明確に求められているメール
- 取引先からの直接の連絡${customInstructions}

${detectReplyNeeded ? `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【返信要否の判定】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
相手が何かを求めている場合は「yes」：
- 質問されている（「〜でしょうか？」「〜ですか？」）
- 依頼されている（「〜してください」「〜をお願いします」）
- 確認を求められている（「ご確認ください」「ご検討ください」）
- 返信期限がある（「○日までにご返信ください」）
- 出欠確認を求められている
- 承認・決裁を求められている
- 見積もり・価格の問い合わせ

返信不要の場合は「no」：
- 情報共有のみ（「ご報告まで」「FYI」）
- CCで送られてきた
- 自動通知
- 「返信不要」と明記
- 営業・広告メール

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【返信例の生成 - 重要】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
needsReplyが「yes」の場合のみ、replySuggestionに返信例を生成してください。

返信例のルール：
- 必ず「${userName}です。」で始める（「ユーザーです」は禁止）
- メールに書かれている具体的な日付・内容をそのまま使う（「22日の書類」など）
- 複数の依頼があればすべてに言及する
- ビジネスメールとして適切な文体
- 100〜200文字程度

返信例のフォーマット：
「${userName}です。

[本文：具体的な日付や内容を含める]

よろしくお願いいたします。」

返信例の例：
「${userName}です。

22日の書類の件、承知いたしました。ご返却の準備をいたします。
また、お見積もりについて、対象製品・数量・納期など詳細を教えていただけますでしょうか。

よろしくお願いいたします。」

「${userName}です。

2024年度の契約更新書類の件、確認いたしました。
金曜日までにご返信いたします。

よろしくお願いいたします。」

needsReplyが「no」または「unknown」の場合は、replySuggestionは空文字列にしてください。
` : "needsReplyは常に\"unknown\"、replySuggestionは空文字列としてください。"}

JSON形式のみで回答してください。`;

    const result = await model.generateContent(prompt);
    const response = result.response;
    const text = response.text();

    const parsed = JSON.parse(text);

    return {
      summary: parsed.summary || "要約を生成できませんでした",
      importance: parsed.importance || "medium",
      senderName: parsed.senderName || sender.split("@")[0],
      needsReply: parsed.needsReply || "unknown",
      replyReason: parsed.replyReason || "",
      replySuggestion: parsed.replySuggestion || "",
    };
  } catch (error) {
    console.error("[LLM] Error analyzing email:", error);
    // Fallback to basic analysis
    return {
      summary: `${sender}からの「${subject}」に関するメール`,
      importance: "medium",
      senderName: sender.split("@")[0],
      needsReply: "unknown",
      replyReason: "",
      replySuggestion: "",
    };
  }
}
