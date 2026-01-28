/**
 * 1-3穴バイアス戦略 - 購入予定登録バッチ
 * 
 * 戦略概要:
 * - 1号艇の当地成績が6.5以上のレースで1-3（2連複または2連単）を購入
 * - 慶應義塾大学の論文で実証された戦略（回収率104%〜144%）
 * 
 * 実行タイミング: 毎朝（レース開始前）
 * 実行コマンド: npx tsx server/scripts/register_1_3_bias_bets.ts
 */

import { Pool } from "pg";

// 外部DB接続（競艇データ）
const EXTERNAL_DB_URL = process.env.EXTERNAL_DATABASE_URL || 
  "postgresql://kokotomo_staging_user:PASSWORD@dpg-d52du3nfte5s73d3ni6g-a.singapore-postgres.render.com/kokotomo_staging";

const pool = new Pool({
  connectionString: EXTERNAL_DB_URL,
  ssl: { rejectUnauthorized: false },
  max: 10,
  idleTimeoutMillis: 60000,
  connectionTimeoutMillis: 60000,
});

// 戦略設定
const STRATEGY = {
  name: "1_3_Bias_Strategy",
  description: "1-3穴バイアス戦略（1号艇当地成績6.5以上）",
  betType: "quinella",  // 2連複（exactaは2連単）
  combination: "1-3",
  minLocalWinRate: 6.5,  // 1号艇の当地成績の最低値
  minOdds: 3.0,          // 最低オッズ（低すぎると期待値が低い）
  maxOdds: 30.0,         // 最高オッズ（高すぎるとリスクが高い）
  betAmount: 1000,       // 1回あたりの賭け金
};

// 内部DB接続（アプリデータ）
// 注意: 実際の環境では drizzle を使用
async function getInternalDb() {
  // ここでは仮の実装
  // 実際のプロジェクトでは import { getDb } from "../db"; を使用
  return null;
}

/**
 * 本日のレース一覧を取得
 */
async function getTodayRaces(date: string): Promise<any[]> {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT 
        r.stadium_code,
        r.race_number,
        r.race_name,
        r.deadline,
        r.race_date
      FROM races r
      WHERE r.race_date = $1
      ORDER BY r.stadium_code, r.race_number
    `, [date]);
    return result.rows;
  } finally {
    client.release();
  }
}

/**
 * 1号艇の当地成績を取得
 */
async function getBoat1LocalWinRate(
  stadiumCode: string, 
  raceNumber: number, 
  date: string
): Promise<number | null> {
  const client = await pool.connect();
  try {
    // boatrace_entriesまたはhistorical_programsから1号艇の情報を取得
    const result = await client.query(`
      SELECT 
        be.local_win_rate,
        be.racer_no
      FROM boatrace_entries be
      WHERE be.stadium_code = $1 
        AND be.race_number = $2 
        AND be.race_date = $3
        AND be.boat_number = 1
      LIMIT 1
    `, [stadiumCode, raceNumber, date]);
    
    if (result.rows.length > 0 && result.rows[0].local_win_rate) {
      return parseFloat(result.rows[0].local_win_rate);
    }
    
    // boatrace_entriesにない場合はhistorical_programsから取得を試みる
    // （当日データがまだない場合のフォールバック）
    return null;
  } finally {
    client.release();
  }
}

/**
 * 1-3のオッズを取得
 */
async function get1_3Odds(
  stadiumCode: string, 
  raceNumber: number, 
  date: string
): Promise<{ quinella: number | null; exacta: number | null }> {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT 
        odds_type,
        odds_data
      FROM odds
      WHERE stadium_code = $1 
        AND race_number = $2 
        AND race_date = $3
        AND odds_type IN ('quinella', 'exacta')
    `, [stadiumCode, raceNumber, date]);
    
    let quinella: number | null = null;
    let exacta: number | null = null;
    
    for (const row of result.rows) {
      const oddsData = row.odds_data;
      if (row.odds_type === 'quinella' && oddsData) {
        // 1-3の2連複オッズを取得
        quinella = oddsData['1-3'] || oddsData['1_3'] || null;
      }
      if (row.odds_type === 'exacta' && oddsData) {
        // 1-3の2連単オッズを取得
        exacta = oddsData['1-3'] || oddsData['1_3'] || null;
      }
    }
    
    return { quinella, exacta };
  } finally {
    client.release();
  }
}

/**
 * 競艇場コードから競艇場名を取得
 */
function getStadiumName(code: string): string {
  const stadiums: Record<string, string> = {
    '01': '桐生', '02': '戸田', '03': '江戸川', '04': '平和島',
    '05': '多摩川', '06': '浜名湖', '07': '蒲郡', '08': '常滑',
    '09': '津', '10': '三国', '11': 'びわこ', '12': '住之江',
    '13': '尼崎', '14': '鳴門', '15': '丸亀', '16': '児島',
    '17': '宮島', '18': '徳山', '19': '下関', '20': '若松',
    '21': '芦屋', '22': '福岡', '23': '唐津', '24': '大村',
  };
  return stadiums[code] || `場${code}`;
}

/**
 * 仮想購入を登録（pending状態）
 */
async function registerPendingBet(bet: {
  raceDate: string;
  stadiumCode: string;
  raceNumber: number;
  stadiumName: string;
  betType: string;
  combination: string;
  betAmount: number;
  scheduledDeadline: Date;
  reason: object;
}): Promise<void> {
  // 実際のプロジェクトでは drizzle を使用して virtualBets テーブルに挿入
  // ここではログ出力のみ
  console.log(`[登録] ${bet.stadiumName} ${bet.raceNumber}R - 締切: ${bet.scheduledDeadline.toLocaleTimeString('ja-JP')} - ${bet.combination} ${bet.betType} ¥${bet.betAmount} (購入予定)`);
  console.log(`  理由: ${JSON.stringify(bet.reason)}`);
}

/**
 * メイン処理
 */
async function main() {
  const today = new Date();
  const dateStr = today.toISOString().split('T')[0]; // YYYY-MM-DD形式
  
  console.log("=== 1-3穴バイアス戦略 購入予定登録バッチ ===");
  console.log(`実行時刻: ${today.toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })} (JST)`);
  console.log(`対象日: ${dateStr}`);
  console.log(`戦略: ${STRATEGY.description}`);
  console.log(`条件: 1号艇当地成績 >= ${STRATEGY.minLocalWinRate}`);
  console.log(`オッズ範囲: ${STRATEGY.minOdds}〜${STRATEGY.maxOdds}倍`);
  console.log(`1回あたりの賭け金: ¥${STRATEGY.betAmount}`);
  console.log("");
  
  try {
    // 本日のレースを取得
    const races = await getTodayRaces(dateStr);
    console.log(`本日の総レース数: ${races.length}件`);
    console.log("");
    
    let registeredCount = 0;
    let skippedCount = 0;
    
    for (const race of races) {
      const { stadium_code, race_number, deadline } = race;
      const stadiumName = getStadiumName(stadium_code);
      
      // 1号艇の当地成績を取得
      const localWinRate = await getBoat1LocalWinRate(stadium_code, race_number, dateStr);
      
      if (localWinRate === null) {
        // 当地成績が取得できない場合はスキップ
        skippedCount++;
        continue;
      }
      
      // 条件チェック: 当地成績が6.5以上
      if (localWinRate < STRATEGY.minLocalWinRate) {
        skippedCount++;
        continue;
      }
      
      // 購入予定を登録
      await registerPendingBet({
        raceDate: dateStr,
        stadiumCode: stadium_code,
        raceNumber: race_number,
        stadiumName: stadiumName,
        betType: STRATEGY.betType,
        combination: STRATEGY.combination,
        betAmount: STRATEGY.betAmount,
        scheduledDeadline: new Date(deadline),
        reason: {
          strategy: STRATEGY.name,
          boat1LocalWinRate: localWinRate,
          threshold: STRATEGY.minLocalWinRate,
          expectedReturnRate: "104%〜144%（慶應論文）",
        },
      });
      
      registeredCount++;
    }
    
    console.log("");
    console.log("=== 登録結果 ===");
    console.log(`登録済み: ${registeredCount}件`);
    console.log(`スキップ: ${skippedCount}件`);
    
  } catch (error) {
    console.error("エラーが発生しました:", error);
    throw error;
  } finally {
    await pool.end();
  }
}

// 実行
main().catch(console.error);
