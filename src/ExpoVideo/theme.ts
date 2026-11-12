// 展示会用 1分モーション動画のデザイン定数

export const C = {
  bg: "#06070f",
  cyan: "#00E5FF",
  magenta: "#FF2E88",
  yellow: "#FFD400",
  gold: "#FFC23D",
  line: "#06C755",
  violet: "#7B5CFF",
  red: "#FF1744",
  white: "#ffffff",
  ink: "#111318",
};

export const FONT_DISPLAY = '"Dela Gothic One", "Noto Sans JP", sans-serif';
export const FONT_JP = '"Noto Sans JP", sans-serif';
export const FONT_EN = '"Anton", "Dela Gothic One", "Noto Sans JP", sans-serif';

export const FPS = 30;
export const INTRO_LEN = 150;
export const SCENE_LEN = 160;
export const SCENE_COUNT = 9;
export const OUTRO_START = INTRO_LEN + SCENE_LEN * SCENE_COUNT; // 1590
export const OUTRO_LEN = 210;
export const TOTAL = OUTRO_START + OUTRO_LEN; // 1800 = 60秒

export const sceneStart = (i: number) => INTRO_LEN + SCENE_LEN * i;

// 各シーンのアクセントカラー [メイン, サブ]
export const ACCENTS: [string, string][] = [
  [C.yellow, C.magenta], // intro
  [C.magenta, C.yellow], // 01 映画
  [C.cyan, C.violet], // 02 HP採点
  [C.magenta, C.cyan], // 03 エンタメ×AI
  [C.gold, C.magenta], // 04 プロデューサー
  [C.yellow, C.cyan], // 05 早い安い
  [C.line, C.cyan], // 06 LINE
  [C.cyan, C.yellow], // 07 丸一日
  [C.yellow, C.magenta], // 08 価格帯
  [C.cyan, C.line], // 09 運用
  [C.white, C.yellow], // outro
];

// フォント先読み用（使う文字をすべて含める）
export const ALL_TEXT =
  "無料でお試しできます！お気軽に。i&F GROUP × BANTEX ENTERTAINMENT AI SERVICE " +
  "10分であなたが主人公の映画をYouTubeで。STARRING YOU 主演：あなた 00:00/10:00 AI MOVIE " +
  "貴社のHPをAIが採点 デザイン スマホ対応 SEO 集客導線 AI SCORE 点 ※画面はイメージです " +
  "エンタメ×AIのコンセプト会社 CONCEPT COMPANY " +
  "パチンコ開発で販売台数日本一のプロデューサーが伴走 遊技機20機種・200万台プロデュース PRODUCER 777 BAR No.1 ★ " +
  "他社より早い！安い！そのわけは…社員＝AI 人間2名＋AI社員7名で運営中 SPEED COST " +
  "シニアも使えるLINEでシステム構築だから操作はカンタン！ 明日10時に予約したい 承知しました。明日10:00で予約を登録しました ありがとう！どういたしまして。当日お待ちしております AIアシスタント LINE SYSTEM " +
  "AIを始めたいけど、何をしたらいいか分からない方必見！丸一日あなたの仕事場に伺いAI化をご提示 1 DAY " +
  "ココトモSNS・介護システム・制服屋サービスなど小規模店舗が始めやすい価格帯 PRICE CARE " +
  "運用を変えずに、サービスを運用に合わせます。いつもの運用そのまま FIT YOUR WAY PERFECT FIT " +
  "ご用命はアイアンドエフへ HPはこちら www.i-and-f.co.jp POINT ◆ 0123456789/" +
  "BANTEX AI CINEMA ｜ 完成一覧 SITE CHECK ｜ 50社のサイト比較 VOICEVOX:春日部つむぎ " +
  "※実際のサービス画面（QRはぼかし加工）（企業名は匿名化）。点数は当社基準による参考値です";
