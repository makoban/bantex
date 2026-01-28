// import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trpc } from "@/lib/trpc";
import { AlertCircle, Clock, Inbox, Loader2, Mail, MessageSquare, RefreshCw, TrendingUp, User } from "lucide-react";
import { APP_VERSION } from "../../../shared/version";
import { useState } from "react";
import { useLocation } from "wouter";

export default function Summaries() {
  // const { user, loading: authLoading } = useAuth();
  const [, setLocation] = useLocation();
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [selectedImportance, setSelectedImportance] = useState<Set<string>>(new Set());

  const { data: accounts, isLoading: accountsLoading } = trpc.emailAccounts.list.useQuery();

  const { data: summaries, isLoading: summariesLoading } = trpc.emailSummaries.listByAccount.useQuery(
    { accountId: selectedAccountId!, limit: 100 },
    { enabled: !!selectedAccountId }
  );

  const { data: bySender, isLoading: bySenderLoading } = trpc.emailSummaries.listBySender.useQuery(
    { accountId: selectedAccountId! },
    { enabled: !!selectedAccountId }
  );

  const { data: stats, isLoading: statsLoading } = trpc.emailSummaries.getStats.useQuery(
    { accountId: selectedAccountId! },
    { enabled: !!selectedAccountId }
  );

  const triggerBatch = trpc.batch.triggerManually.useMutation({
    onSuccess: () => {
      // Refetch data after batch completes
      setTimeout(() => {
        window.location.reload();
      }, 3000);
    },
  });

  // Auto-select first account
  if (accounts && accounts.length > 0 && !selectedAccountId) {
    setSelectedAccountId(accounts[0].id);
  }

  // Filter summaries by selected importance
  const filteredSummaries = summaries?.filter((s) => {
    if (selectedImportance.size === 0) return true;
    return selectedImportance.has(s.importance);
  });

  // Filter bySender by selected importance
  const filteredBySender = bySender?.map((group) => ({
    ...group,
    emails: group.emails.filter((e) => {
      if (selectedImportance.size === 0) return true;
      return selectedImportance.has(e.importance);
    }),
  })).filter((group) => group.emails.length > 0);

  // Toggle importance filter
  const toggleImportance = (importance: string) => {
    setSelectedImportance((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(importance)) {
        newSet.delete(importance);
      } else {
        newSet.add(importance);
      }
      return newSet;
    });
  };

  // Clear all filters
  const clearFilters = () => {
    setSelectedImportance(new Set());
  };

  // Auth checks disabled for prototype

  if (accountsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!accounts || accounts.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-primary/5 via-accent/5 to-background">
        <div className="container py-8 max-w-4xl">
          <Card>
            <CardContent className="py-12 text-center">
              <Inbox className="w-16 h-16 mx-auto mb-4 text-muted-foreground" />
              <h2 className="text-2xl font-bold mb-2">メールアカウントが未設定です</h2>
              <p className="text-muted-foreground mb-6">
                まずはメールアカウントを追加して、自動チェックを開始しましょう
              </p>
              <Button onClick={() => setLocation("/settings")}>設定ページへ</Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

  const getImportanceBadge = (importance: string) => {
    switch (importance) {
      case "high":
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700">高</span>;
      case "medium":
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700">中</span>;
      case "low":
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700">低</span>;
      case "spam":
        return <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-700">迷惑</span>;
      default:
        return null;
    }
  };

  const getNeedsReplyBadge = (needsReply: string | null | undefined) => {
    if (needsReply === "yes") {
      return (
        <span className="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-700 flex items-center gap-1">
          <MessageSquare className="w-3 h-3" />
          要返信
        </span>
      );
    }
    return null;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-accent/5 to-background">
      <div className="container py-8 max-w-6xl">
        <div className="mb-8">
          <Button variant="ghost" onClick={() => setLocation("/")}>
            ← ホームに戻る
          </Button>
        </div>

        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-primary/10">
              <Mail className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">メール要約</h1>
              <p className="text-muted-foreground">AIが分析したメールの要約を確認</p>
            </div>
          </div>
          <Button
            onClick={() => triggerBatch.mutate()}
            disabled={triggerBatch.isPending}
            className="gap-2"
          >
            {triggerBatch.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {triggerBatch.isPending ? "チェック中..." : "今すぐチェック"}
          </Button>
        </div>

        {/* Account Selector */}
        <div className="mb-6">
          <Label className="mb-2 block text-sm font-medium">アカウント選択</Label>
          <div className="flex gap-2 flex-wrap">
            {accounts.map((account) => (
              <Button
                key={account.id}
                variant={selectedAccountId === account.id ? "default" : "outline"}
                onClick={() => setSelectedAccountId(account.id)}
              >
                {account.email}
              </Button>
            ))}
          </div>
        </div>

        {/* Stats Cards with Filter */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <Card 
              className={`cursor-pointer transition-all hover:shadow-md ${selectedImportance.size === 0 ? 'ring-2 ring-primary' : ''}`}
              onClick={clearFilters}
            >
              <CardContent className="pt-6">
                <div className="text-center">
                  <Inbox className="w-8 h-8 mx-auto mb-2 text-primary" />
                  <div className="text-2xl font-bold">{stats.total}</div>
                  <div className="text-xs text-muted-foreground">総メール数</div>
                </div>
              </CardContent>
            </Card>
            <Card 
              className={`cursor-pointer transition-all hover:shadow-md ${selectedImportance.has('high') ? 'ring-2 ring-red-500' : ''}`}
              onClick={() => toggleImportance('high')}
            >
              <CardContent className="pt-6">
                <div className="text-center">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 text-red-500" />
                  <div className="text-2xl font-bold">{stats.high}</div>
                  <div className="text-xs text-muted-foreground">高優先度</div>
                </div>
              </CardContent>
            </Card>
            <Card 
              className={`cursor-pointer transition-all hover:shadow-md ${selectedImportance.has('medium') ? 'ring-2 ring-yellow-500' : ''}`}
              onClick={() => toggleImportance('medium')}
            >
              <CardContent className="pt-6">
                <div className="text-center">
                  <TrendingUp className="w-8 h-8 mx-auto mb-2 text-yellow-500" />
                  <div className="text-2xl font-bold">{stats.medium}</div>
                  <div className="text-xs text-muted-foreground">中優先度</div>
                </div>
              </CardContent>
            </Card>
            <Card 
              className={`cursor-pointer transition-all hover:shadow-md ${selectedImportance.has('low') ? 'ring-2 ring-blue-500' : ''}`}
              onClick={() => toggleImportance('low')}
            >
              <CardContent className="pt-6">
                <div className="text-center">
                  <Clock className="w-8 h-8 mx-auto mb-2 text-blue-500" />
                  <div className="text-2xl font-bold">{stats.low}</div>
                  <div className="text-xs text-muted-foreground">低優先度</div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-center">
                  <User className="w-8 h-8 mx-auto mb-2 text-purple-500" />
                  <div className="text-2xl font-bold">{stats.uniqueSenders}</div>
                  <div className="text-xs text-muted-foreground">送信者数</div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Active Filters Indicator */}
        {selectedImportance.size > 0 && (
          <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
            <span>フィルタ中:</span>
            {selectedImportance.has('high') && <span className="px-2 py-1 rounded-full bg-red-100 text-red-700">高</span>}
            {selectedImportance.has('medium') && <span className="px-2 py-1 rounded-full bg-yellow-100 text-yellow-700">中</span>}
            {selectedImportance.has('low') && <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-700">低</span>}
            <Button variant="ghost" size="sm" onClick={clearFilters}>クリア</Button>
          </div>
        )}

        <Tabs defaultValue="timeline" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="timeline">時系列表示</TabsTrigger>
            <TabsTrigger value="sender">送り主別表示</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline">
            {summariesLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : filteredSummaries && filteredSummaries.length > 0 ? (
              <div className="space-y-4">
                {filteredSummaries.map((summary) => (
                  <Card key={summary.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            {getImportanceBadge(summary.importance)}
                            {getNeedsReplyBadge((summary as any).needsReply)}
                            <span className="text-sm text-muted-foreground">
                              {new Date(summary.receivedAt).toLocaleString("ja-JP")}
                            </span>
                          </div>
                          <CardTitle className="text-lg truncate">{summary.subject}</CardTitle>
                          <CardDescription className="mt-1">
                            <User className="w-3 h-3 inline mr-1" />
                            {/* 送信者名を優先表示（なければメールアドレス） */}
                            {(summary as any).senderName || summary.sender}
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-foreground">{summary.summary}</p>
                      {(summary as any).replyReason && (
                        <p className="text-xs text-purple-600 mt-2">
                          返信理由: {(summary as any).replyReason}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <Inbox className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {selectedImportance.size > 0 ? "該当するメールがありません" : "まだメールが分析されていません"}
                  </p>
                  <p className="text-sm text-muted-foreground mt-2">
                    {selectedImportance.size > 0 ? "フィルタを変更してください" : "5分毎に自動でチェックされます"}
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="sender">
            {bySenderLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : filteredBySender && filteredBySender.length > 0 ? (
              <div className="space-y-4">
                {filteredBySender.map((group) => (
                  <Card key={group.sender}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="flex items-center gap-2">
                            <User className="w-5 h-5 text-primary" />
                            {/* 送信者名を表示（グループの最初のメールから取得） */}
                            {(group.emails[0] as any)?.senderName || group.sender}
                          </CardTitle>
                          <CardDescription className="mt-1">
                            {group.emails.length}件のメール
                          </CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {group.emails.slice(0, 5).map((email) => (
                          <div
                            key={email.id}
                            className="p-3 rounded-lg bg-muted/50 border border-border"
                          >
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              {getImportanceBadge(email.importance)}
                              {getNeedsReplyBadge((email as any).needsReply)}
                              <span className="text-xs text-muted-foreground">
                                {new Date(email.receivedAt).toLocaleDateString("ja-JP")}
                              </span>
                            </div>
                            <div className="text-sm font-medium mb-1">{email.subject}</div>
                            <div className="text-sm text-muted-foreground">{email.summary}</div>
                          </div>
                        ))}
                        {group.emails.length > 5 && (
                          <p className="text-sm text-muted-foreground text-center">
                            他 {group.emails.length - 5} 件
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="py-12 text-center">
                  <User className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {selectedImportance.size > 0 ? "該当するメールがありません" : "まだメールが分析されていません"}
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>
      </div>
      <div className="fixed bottom-4 right-4 text-xs text-muted-foreground">
        Ver {APP_VERSION}
      </div>
    </div>
  );
}

function Label({ children, className }: { children: React.ReactNode; className?: string }) {
  return <label className={className}>{children}</label>;
}
