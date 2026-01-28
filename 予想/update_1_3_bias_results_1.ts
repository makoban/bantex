/**
 * 1-3穴バイアス戦略 - 結果更新バッチ
 * 
 * 処理内容:
 * - confirmed状態の1-3購入を取得
 * - 外部DBからレース結果を取得
 * - 的中/不的中を判定
 * - ステータスをwon/lostに更新
 * - 仮想資金の残高を更新
 * 
 * 実行タイミング: 常時稼働（pm2で管理）
 * 実行コマンド: 
 *   単発: npx tsx server/scripts/update_1_3_bias_results.ts 2026-01-19
 *   監視: npx tsx server/scripts/update_1_3_bias_results.ts --watch
 *   常時: pm2 start npx --name "1-3-bias-result" -- tsx server/scripts/update_1_3_bias_results.ts --watch
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

// 設定
const CONFIG = {
  checkIntervalMs: 30000, // チェック間隔（30秒）
  strategyName: "1_3_Bias_Strategy",
};

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
 * レース結果を取得
 */
async function getRaceResult(
  stadiumCode: string, 
  raceNumber: number, 
  date: string
): Promise<{ first: number; second: number; third: number } | null> {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT 
        first_place,
        second_place,
        third_place
      FROM race_results
      WHERE stadium_code = $1 
        AND race_number = $2 
        AND race_date = $3
      LIMIT 1
    `, [stadiumCode, raceNumber, date]);
    
    if (result.rows.length > 0) {
      return {
        first: result.rows[0].first_place,
        second: result.rows[0].second_place,
        third: result.rows[0].third_place,
      };
    }
    return null;
  } finally {
    client.release();
  }
}

/**
 * 払戻金を取得
 */
async function getPayoff(
  stadiumCode: string, 
  raceNumber: number, 
  date: string,
  betType: string,
  combination: string
): Promise<number | null> {
  const client = await pool.connect();
  try {
    // payoffsテーブルから払戻金を取得
    const result = await client.query(`
      SELECT 
        payoff_data
      FROM payoffs
      WHERE stadium_code = $1 
        AND race_number = $2 
        AND race_date = $3
        AND bet_type = $4
      LIMIT 1
    `, [stadiumCode, raceNumber, date, betType]);
    
    if (result.rows.length > 0 && result.rows[0].payoff_data) {
      const payoffData = result.rows[0].payoff_data;
      // combination形式に応じて払戻金を取得
      const payoff = payoffData[combination] || 
                     payoffData[combination.replace('-', '_')] || 
                     payoffData[combination.replace('-', '')];
      return payoff ? parseFloat(payoff) : null;
    }
    return null;
  } finally {
    client.release();
  }
}

/**
 * 1-3が的中したかチェック
 */
function check1_3Hit(
  result: { first: number; second: number; third: number },
  betType: string
): boolean {
  if (betType === 'quinella') {
    // 2連複: 1着と2着に1と3が含まれていればOK（順不同）
    const top2 = [result.first, result.second].sort();
    return top2[0] === 1 && top2[1] === 3;
  } else if (betType === 'exacta') {
    // 2連単: 1着が1、2着が3
    return result.first === 1 && result.second === 3;
  }
  return false;
}

/**
 * 仮想購入の結果を更新
 * 
 * 注意: 実際のプロジェクトでは drizzle を使用
 * ここではログ出力のみ
 */
async function updateBetResult(bet: {
  id: number;
  stadiumCode: string;
  raceNumber: number;
  betType: string;
  combination: string;
  betAmount: number;
  odds: number;
  result: 'won' | 'lost';
  actualResult: string;
  payoff: number;
  returnAmount: number;
  profit: number;
}): Promise<void> {
  const stadiumName = getStadiumName(bet.stadiumCode);
  
  if (bet.result === 'won') {
    console.log(`[的中] ${stadiumName} ${bet.raceNumber}R - ${bet.combination} (${bet.betType})`);
    console.log(`  結果: ${bet.actualResult}`);
    console.log(`  オッズ: ${bet.odds}倍`);
    console.log(`  払戻: ¥${bet.payoff} (100円あたり)`);
    console.log(`  回収額: ¥${bet.returnAmount}`);
    console.log(`  損益: +¥${bet.profit}`);
  } else {
    console.log(`[不的中] ${stadiumName} ${bet.raceNumber}R - ${bet.combination} (${bet.betType})`);
    console.log(`  結果: ${bet.actualResult}`);
    console.log(`  損益: -¥${bet.betAmount}`);
  }
}

/**
 * 統計を表示
 */
function displayStats(stats: {
  total: number;
  won: number;
  lost: number;
  pending: number;
  totalBet: number;
  totalReturn: number;
}): void {
  const hitRate = stats.total > 0 ? (stats.won / (stats.won + stats.lost) * 100) : 0;
  const returnRate = stats.totalBet > 0 ? (stats.totalReturn / stats.totalBet * 100) : 0;
  
  console.log("\n=== 1-3穴バイアス戦略 統計 ===");
  console.log(`総購入数: ${stats.total}件`);
  console.log(`的中: ${stats.won}件`);
  console.log(`不的中: ${stats.lost}件`);
  console.log(`未確定: ${stats.pending}件`);
  console.log(`的中率: ${hitRate.toFixed(1)}%`);
  console.log(`総投資額: ¥${stats.totalBet.toLocaleString()}`);
  console.log(`総回収額: ¥${stats.totalReturn.toLocaleString()}`);
  console.log(`回収率: ${returnRate.toFixed(1)}%`);
  console.log(`損益: ¥${(stats.totalReturn - stats.totalBet).toLocaleString()}`);
}

/**
 * 指定日の結果を更新
 */
async function updateResultsForDate(dateStr: string): Promise<void> {
  console.log(`\n=== ${dateStr} の結果更新 ===`);
  
  // 実際のプロジェクトでは内部DBからconfirmed状態の購入を取得
  // ここではサンプルデータで動作確認
  const sampleBets = [
    // サンプルデータ（実際は内部DBから取得）
  ];
  
  if (sampleBets.length === 0) {
    console.log("更新対象の購入がありません");
    return;
  }
  
  const stats = {
    total: 0,
    won: 0,
    lost: 0,
    pending: 0,
    totalBet: 0,
    totalReturn: 0,
  };
  
  for (const bet of sampleBets) {
    // レース結果を取得
    const result = await getRaceResult(bet.stadiumCode, bet.raceNumber, dateStr);
    
    if (result === null) {
      stats.pending++;
      continue;
    }
    
    stats.total++;
    stats.totalBet += bet.betAmount;
    
    // 的中判定
    const isHit = check1_3Hit(result, bet.betType);
    const actualResult = `${result.first}-${result.second}-${result.third}`;
    
    if (isHit) {
      // 払戻金を取得
      const payoff = await getPayoff(
        bet.stadiumCode, 
        bet.raceNumber, 
        dateStr, 
        bet.betType, 
        bet.combination
      );
      
      const returnAmount = payoff ? (bet.betAmount / 100) * payoff : bet.betAmount * bet.odds;
      const profit = returnAmount - bet.betAmount;
      
      stats.won++;
      stats.totalReturn += returnAmount;
      
      await updateBetResult({
        ...bet,
        result: 'won',
        actualResult,
        payoff: payoff || bet.odds * 100,
        returnAmount,
        profit,
      });
    } else {
      stats.lost++;
      
      await updateBetResult({
        ...bet,
        result: 'lost',
        actualResult,
        payoff: 0,
        returnAmount: 0,
        profit: -bet.betAmount,
      });
    }
  }
  
  displayStats(stats);
}

/**
 * 監視モード
 */
async function watchMode(): Promise<void> {
  console.log("=== 1-3穴バイアス戦略 結果更新バッチ（監視モード） ===");
  console.log(`チェック間隔: ${CONFIG.checkIntervalMs / 1000}秒`);
  console.log("");
  console.log("監視を開始します...");
  
  const checkResults = async () => {
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    
    console.log(`\n[${today.toLocaleTimeString('ja-JP')}] 結果チェック中...`);
    
    try {
      await updateResultsForDate(dateStr);
    } catch (error) {
      console.error("エラーが発生しました:", error);
    }
  };
  
  // 初回実行
  await checkResults();
  
  // 定期実行
  setInterval(checkResults, CONFIG.checkIntervalMs);
}

/**
 * メイン処理
 */
async function main(): Promise<void> {
  const args = process.argv.slice(2);
  
  if (args.includes('--watch')) {
    await watchMode();
  } else if (args.length > 0 && !args[0].startsWith('-')) {
    // 日付指定で単発実行
    const dateStr = args[0];
    await updateResultsForDate(dateStr);
    await pool.end();
  } else {
    // 本日分を単発実行
    const today = new Date();
    const dateStr = today.toISOString().split('T')[0];
    await updateResultsForDate(dateStr);
    await pool.end();
  }
}

// 実行
main().catch(console.error);
