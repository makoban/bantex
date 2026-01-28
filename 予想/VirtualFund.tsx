/**
 * 仮想投資シミュレーション ページ
 * 
 * 複数の戦略を切り替えて表示できるように拡張
 * - 既存: 11R・12R 1号艇単勝戦略
 * - 新規: 1-3穴バイアス戦略
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, RotateCcw, TrendingUp, TrendingDown, Target, Wallet } from "lucide-react";
import { trpc } from "@/lib/trpc";

// 戦略の定義
const STRATEGIES = {
  win_11_12: {
    id: "win_11_12",
    name: "11R・12R 1号艇単勝",
    description: "11R・12Rの1号艇単勝を購入する戦略",
    betType: "単勝",
    targetRaces: "11R・12R",
    expectedHitRate: { "11R": 66.7, "12R": 71.5 },
    minOdds: 1.6,
    maxOdds: 10.0,
    betAmount: 1000,
  },
  bias_1_3: {
    id: "bias_1_3",
    name: "1-3穴バイアス",
    description: "1号艇当地成績6.5以上で1-3を購入する戦略（慶應論文）",
    betType: "2連複/2連単",
    targetRaces: "全レース",
    expectedReturnRate: "104%〜144%",
    minLocalWinRate: 6.5,
    minOdds: 3.0,
    maxOdds: 30.0,
    betAmount: 1000,
  },
};

type StrategyId = keyof typeof STRATEGIES;

export default function VirtualFund() {
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyId>("win_11_12");
  const [activeTab, setActiveTab] = useState("overview");

  // 仮想資金データを取得（tRPC）
  // 実際のプロジェクトでは trpc.virtualFund.getStats.useQuery() などを使用
  const mockStats = {
    win_11_12: {
      currentFund: 100000,
      initialFund: 100000,
      totalProfit: 0,
      returnRate: 0,
      hitRate: 0,
      totalBets: 0,
      wonBets: 0,
      lostBets: 0,
      pendingBets: 0,
      totalInvested: 0,
      totalReturned: 0,
    },
    bias_1_3: {
      currentFund: 100000,
      initialFund: 100000,
      totalProfit: 0,
      returnRate: 0,
      hitRate: 0,
      totalBets: 0,
      wonBets: 0,
      lostBets: 0,
      pendingBets: 0,
      totalInvested: 0,
      totalReturned: 0,
    },
  };

  const stats = mockStats[selectedStrategy];
  const strategy = STRATEGIES[selectedStrategy];

  const handleRefresh = () => {
    // データを再取得
    console.log("Refreshing data...");
  };

  const handleReset = () => {
    // 仮想資金をリセット
    if (confirm("仮想資金をリセットしますか？")) {
      console.log("Resetting virtual fund...");
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* ヘッダー */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold">仮想投資シミュレーション</h1>
          <p className="text-muted-foreground mt-1">
            {strategy.name}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            更新
          </Button>
          <Button variant="outline" size="sm" onClick={handleReset}>
            <RotateCcw className="w-4 h-4 mr-2" />
            リセット
          </Button>
        </div>
      </div>

      {/* 戦略選択 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">戦略選択</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            {Object.values(STRATEGIES).map((s) => (
              <Button
                key={s.id}
                variant={selectedStrategy === s.id ? "default" : "outline"}
                className="flex-1"
                onClick={() => setSelectedStrategy(s.id as StrategyId)}
              >
                <div className="text-left">
                  <div className="font-medium">{s.name}</div>
                  <div className="text-xs opacity-70">{s.betType}</div>
                </div>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* サマリーカード */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">現在の資金</p>
                <p className="text-2xl font-bold">
                  ¥{stats.currentFund.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  初期: ¥{stats.initialFund.toLocaleString()}
                </p>
              </div>
              <Wallet className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">累計損益</p>
                <p className={`text-2xl font-bold ${stats.totalProfit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                  {stats.totalProfit >= 0 ? '+' : ''}¥{stats.totalProfit.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  {stats.totalProfit >= 0 ? '+' : ''}{stats.returnRate.toFixed(1)}%
                </p>
              </div>
              {stats.totalProfit >= 0 ? (
                <TrendingUp className="w-8 h-8 text-green-500" />
              ) : (
                <TrendingDown className="w-8 h-8 text-red-500" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">回収率</p>
                <p className={`text-2xl font-bold ${stats.returnRate >= 100 ? 'text-green-500' : 'text-yellow-500'}`}>
                  {stats.returnRate.toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground">
                  投資: ¥{stats.totalInvested.toLocaleString()}
                </p>
              </div>
              <Target className="w-8 h-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">的中率</p>
                <p className="text-2xl font-bold">
                  {stats.hitRate.toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground">
                  {stats.wonBets}/{stats.wonBets + stats.lostBets}件
                </p>
              </div>
              <div className="text-right">
                <Badge variant="outline" className="text-green-500">
                  的中 {stats.wonBets}
                </Badge>
                <Badge variant="outline" className="text-red-500 ml-1">
                  不的中 {stats.lostBets}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* タブコンテンツ */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">概要</TabsTrigger>
          <TabsTrigger value="history">購入履歴</TabsTrigger>
          <TabsTrigger value="daily">日別推移</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            {/* 投資戦略 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  投資戦略
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">対象レース</span>
                  <span>{strategy.targetRaces}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">買い目</span>
                  <span>{strategy.betType}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">オッズ条件</span>
                  <span>{strategy.minOdds}〜{strategy.maxOdds}倍</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">1回の賭け金</span>
                  <span>¥{strategy.betAmount.toLocaleString()}</span>
                </div>
                {selectedStrategy === 'bias_1_3' && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">当地成績条件</span>
                    <span>≥ {(strategy as typeof STRATEGIES.bias_1_3).minLocalWinRate}</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 投資統計 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  投資統計
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">総購入回数</span>
                  <span>{stats.totalBets}回</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">的中回数</span>
                  <span className="text-green-500">{stats.wonBets}回</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">不的中回数</span>
                  <span className="text-red-500">{stats.lostBets}回</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">総投資額</span>
                  <span>¥{stats.totalInvested.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">総回収額</span>
                  <span>¥{stats.totalReturned.toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>

            {/* 理論値 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  理論値
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {selectedStrategy === 'win_11_12' ? (
                  <>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">11R勝率</span>
                      <span>{(strategy as typeof STRATEGIES.win_11_12).expectedHitRate["11R"]}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">12R勝率</span>
                      <span>{(strategy as typeof STRATEGIES.win_11_12).expectedHitRate["12R"]}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">必要オッズ(11R)</span>
                      <span>1.50倍以上</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">必要オッズ(12R)</span>
                      <span>1.40倍以上</span>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">期待回収率</span>
                      <span className="text-green-500">
                        {(strategy as typeof STRATEGIES.bias_1_3).expectedReturnRate}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">根拠</span>
                      <span>慶應義塾大学論文</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">戦略タイプ</span>
                      <span>穴バイアス活用</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">対象条件</span>
                      <span>1号艇当地成績6.5↑</span>
                    </div>
                  </>
                )}
                <p className="text-xs text-muted-foreground pt-2">
                  ※過去5年間3万レースから算出
                </p>
              </CardContent>
            </Card>
          </div>

          {/* 直近の購入 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">直近の購入</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center text-muted-foreground py-8">
                購入履歴がありません
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>購入履歴</CardTitle>
              <CardDescription>
                {strategy.name}の購入履歴を表示します
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center text-muted-foreground py-8">
                購入履歴がありません
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="daily">
          <Card>
            <CardHeader>
              <CardTitle>日別推移</CardTitle>
              <CardDescription>
                日別の損益推移を表示します
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center text-muted-foreground py-8">
                データがありません
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
