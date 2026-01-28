/**
 * 1-3穴バイアス戦略 - リアルタイム仮想投資バッチ（締切1分前判断）
 * 
 * 戦略概要:
 * - 1号艇の当地成績が6.5以上のレースで1-3（2連複または2連単）を購入
 * - 締切1分前に最終オッズを確認して購入判断
 * - 2連複と2連単のオッズを比較し、期待値が高い方を選択
 * 
 * 実行タイミング: 常時稼働（pm2で管理）
 * 実行コマンド: 
 *   単発: npx tsx server/scripts/realtime_1_3_bias_betting.ts
 *   常時: pm2 start npx --name "1-3-bias-betting" -- tsx server/scripts/realtime_1_3_bias_betting.ts
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
  minLocalWinRate: 6.5,  // 1号艇の当地成績の最低値
  minOdds: 3.0,          // 最低オッズ
  maxOdds: 30.0,         // 最高オッズ
  betAmount: 1000,       // 1回あたりの賭け金
  checkIntervalMs: 10000, // チェック間隔（10秒）
  decisionWindowMinutes: 1, // 締切何分前に判断するか
};

// 処理済みレースを記録（重複購入防止）
const processedRaces = new Set<string>();

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
 * 締切1分前〜0分前のレースを取得
 */
async function getRacesNearDeadline(date: string): Promise<any[]> {
  const client = await pool.connect();
  try {
    const now = new Date();
    const oneMinuteLater = new Date(now.getTime() + STRATEGY.decisionWindowMinutes * 60 * 1000);
    
    const result = await client.query(`
      SELECT 
        r.stadium_code,
        r.race_number,
        r.race_name,
        r.deadline,
        r.race_date
      FROM races r
      WHERE r.race_date = $1
        AND r.deadline > $2
        AND r.deadline <= $3
      ORDER BY r.deadline
    `, [date, now.toISOString(), oneMinuteLater.toISOString()]);
    
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
    return null;
  } finally {
    client.release();
  }
}

/**
 * 最新の1-3オッズを取得（odds_historyから締切直前のデータ）
 */
async function getLatest1_3Odds(
  stadiumCode: string, 
  raceNumber: number, 
  date: string
): Promise<{ quinella: number | null; exacta: number | null }> {
  const client = await pool.connect();
  try {
    // odds_historyから最新のオッズを取得
    const result = await client.query(`
      SELECT 
        odds_type,
        odds_data,
        recorded_at
      FROM odds_history
      WHERE stadium_code = $1 
        AND race_number = $2 
        AND race_date = $3
        AND odds_type IN ('quinella', 'exacta')
      ORDER BY recorded_at DESC
      LIMIT 2
    `, [stadiumCode, raceNumber, date]);
    
    let quinella: number | null = null;
    let exacta: number | null = null;
    
    for (const row of result.rows) {
      const oddsData = row.odds_data;
      if (row.odds_type === 'quinella' && oddsData && quinella === null) {
        quinella = oddsData['1-3'] || oddsData['1_3'] || oddsData['13'] || null;
      }
      if (row.odds_type === 'exacta' && oddsData && exacta === null) {
        exacta = oddsData['1-3'] || oddsData['1_3'] || oddsData['13'] || null;
      }
    }
    
    // odds_historyにない場合はoddsテーブルから取得
    if (quinella === null || exacta === null) {
      const fallbackResult = await client.query(`
        SELECT 
          odds_type,
          odds_data
        FROM odds
        WHERE stadium_code = $1 
          AND race_number = $2 
          AND race_date = $3
          AND odds_type IN ('quinella', 'exacta')
      `, [stadiumCode, raceNumber, date]);
      
      for (const row of fallbackResult.rows) {
        const oddsData = row.odds_data;
        if (row.odds_type === 'quinella' && oddsData && quinella === null) {
          quinella = oddsData['1-3'] || oddsData['1_3'] || oddsData['13'] || null;
        }
        if (row.odds_type === 'exacta' && oddsData && exacta === null) {
          exacta = oddsData['1-3'] || oddsData['1_3'] || oddsData['13'] || null;
        }
      }
    }
    
    return { quinella, exacta };
  } finally {
    client.release();
  }
}

/**
 * 仮想購入を実行（confirmed状態で登録）
 */
async function executeVirtualBet(bet: {
  raceDate: string;
  stadiumCode: string;
  raceNumber: number;
  stadiumName: string;
  betType: string;
  combination: string;
  betAmount: number;
  odds: number;
  reason: object;
}): Promise<void> {
  // 実際のプロジェクトでは drizzle を使用して virtualBets テーブルに挿入
  // status: 'confirmed' で登録
  const now = new Date();
  console.log(`[購入確定] ${now.toLocaleTimeString('ja-JP')} ${bet.stadiumName} ${bet.raceNumber}R`);
  console.log(`  買い目: ${bet.combination} (${bet.betType})`);
  console.log(`  オッズ: ${bet.odds}倍`);
  console.log(`  賭け金: ¥${bet.betAmount}`);
  console.log(`  期待払戻: ¥${(bet.betAmount * bet.odds).toFixed(0)}`);
  console.log(`  理由: ${JSON.stringify(bet.reason)}`);
}

/**
 * 購入をスキップ（skipped状態で記録）
 */
async function skipBet(
  stadiumCode: string,
  raceNumber: number,
  stadiumName: string,
  reason: string
): Promise<void> {
  console.log(`[スキップ] ${stadiumName} ${raceNumber}R - ${reason}`);
}

/**
 * 1レースの購入判断を実行
 */
async function processRace(race: any, dateStr: string): Promise<void> {
  const { stadium_code, race_number, deadline } = race;
  const raceKey = `${dateStr}-${stadium_code}-${race_number}`;
  const stadiumName = getStadiumName(stadium_code);
  
  // 既に処理済みの場合はスキップ
  if (processedRaces.has(raceKey)) {
    return;
  }
  
  console.log(`\n--- ${stadiumName} ${race_number}R 判断開始 ---`);
  
  // 1号艇の当地成績を取得
  const localWinRate = await getBoat1LocalWinRate(stadium_code, race_number, dateStr);
  
  if (localWinRate === null) {
    await skipBet(stadium_code, race_number, stadiumName, "1号艇の当地成績が取得できません");
    processedRaces.add(raceKey);
    return;
  }
  
  console.log(`  1号艇当地成績: ${localWinRate.toFixed(2)}`);
  
  // 条件チェック: 当地成績が6.5以上
  if (localWinRate < STRATEGY.minLocalWinRate) {
    await skipBet(stadium_code, race_number, stadiumName, 
      `1号艇当地成績 ${localWinRate.toFixed(2)} < ${STRATEGY.minLocalWinRate}`);
    processedRaces.add(raceKey);
    return;
  }
  
  // 最新の1-3オッズを取得
  const odds = await getLatest1_3Odds(stadium_code, race_number, dateStr);
  console.log(`  1-3オッズ: 2連複=${odds.quinella || 'N/A'}倍, 2連単=${odds.exacta || 'N/A'}倍`);
  
  // オッズが取得できない場合はスキップ
  if (odds.quinella === null && odds.exacta === null) {
    await skipBet(stadium_code, race_number, stadiumName, "1-3のオッズが取得できません");
    processedRaces.add(raceKey);
    return;
  }
  
  // 2連複と2連単のオッズを比較し、高い方を選択
  let selectedBetType: string;
  let selectedOdds: number;
  
  if (odds.quinella !== null && odds.exacta !== null) {
    // 両方ある場合は高い方を選択（ただし2連複の方が的中率が高いので調整）
    // 2連複の的中率は2連単の2倍なので、期待値で比較
    const quinellaExpected = odds.quinella * 2; // 的中率2倍を考慮
    const exactaExpected = odds.exacta;
    
    if (quinellaExpected >= exactaExpected) {
      selectedBetType = "quinella";
      selectedOdds = odds.quinella;
    } else {
      selectedBetType = "exacta";
      selectedOdds = odds.exacta;
    }
  } else if (odds.quinella !== null) {
    selectedBetType = "quinella";
    selectedOdds = odds.quinella;
  } else {
    selectedBetType = "exacta";
    selectedOdds = odds.exacta!;
  }
  
  // オッズ範囲チェック
  if (selectedOdds < STRATEGY.minOdds) {
    await skipBet(stadium_code, race_number, stadiumName, 
      `オッズ ${selectedOdds}倍 < 最低オッズ ${STRATEGY.minOdds}倍`);
    processedRaces.add(raceKey);
    return;
  }
  
  if (selectedOdds > STRATEGY.maxOdds) {
    await skipBet(stadium_code, race_number, stadiumName, 
      `オッズ ${selectedOdds}倍 > 最高オッズ ${STRATEGY.maxOdds}倍`);
    processedRaces.add(raceKey);
    return;
  }
  
  // 購入実行
  await executeVirtualBet({
    raceDate: dateStr,
    stadiumCode: stadium_code,
    raceNumber: race_number,
    stadiumName: stadiumName,
    betType: selectedBetType,
    combination: "1-3",
    betAmount: STRATEGY.betAmount,
    odds: selectedOdds,
    reason: {
      strategy: STRATEGY.name,
      boat1LocalWinRate: localWinRate,
      threshold: STRATEGY.minLocalWinRate,
      quinellaOdds: odds.quinella,
      exactaOdds: odds.exacta,
      selectedBetType: selectedBetType,
    },
  });
  
  processedRaces.add(raceKey);
}

/**
 * メインループ
 */
async function mainLoop(): Promise<void> {
  const today = new Date();
  const dateStr = today.toISOString().split('T')[0];
  
  console.log(`[${today.toLocaleTimeString('ja-JP')}] チェック中...`);
  
  try {
    // 締切1分前〜0分前のレースを取得
    const races = await getRacesNearDeadline(dateStr);
    
    if (races.length > 0) {
      console.log(`  締切間近のレース: ${races.length}件`);
      
      for (const race of races) {
        await processRace(race, dateStr);
      }
    }
  } catch (error) {
    console.error("エラーが発生しました:", error);
  }
}

/**
 * メイン処理
 */
async function main(): Promise<void> {
  console.log("=== 1-3穴バイアス戦略 リアルタイム仮想投資バッチ ===");
  console.log(`戦略: ${STRATEGY.description}`);
  console.log(`条件: 1号艇当地成績 >= ${STRATEGY.minLocalWinRate}`);
  console.log(`オッズ範囲: ${STRATEGY.minOdds}〜${STRATEGY.maxOdds}倍`);
  console.log(`チェック間隔: ${STRATEGY.checkIntervalMs / 1000}秒`);
  console.log(`判断タイミング: 締切${STRATEGY.decisionWindowMinutes}分前`);
  console.log("");
  console.log("監視を開始します...");
  console.log("");
  
  // 初回実行
  await mainLoop();
  
  // 定期実行
  setInterval(async () => {
    await mainLoop();
  }, STRATEGY.checkIntervalMs);
}

// 実行
main().catch(console.error);
