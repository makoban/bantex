// import { useAuth } from "@/_core/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { trpc } from "@/lib/trpc";
import { AlertTriangle, ExternalLink, Loader2, Mail, Play, Plus, RefreshCw, Settings as SettingsIcon, Trash2 } from "lucide-react";
import { APP_VERSION } from "../../../shared/version";
import { useState } from "react";
import { toast } from "sonner";
import { getLoginUrl } from "@/const";
import { useLocation } from "wouter";

export default function Settings() {
  // const { user, loading: authLoading } = useAuth();
  const [, setLocation] = useLocation();
  const [showForm, setShowForm] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [editingAccountId, setEditingAccountId] = useState<number | null>(null);
  const [editChatworkRoomId, setEditChatworkRoomId] = useState("");

  const [formData, setFormData] = useState({
    email: "",
    imapHost: "",
    imapPort: 993,
    imapUsername: "",
    imapPassword: "",
    chatworkRoomId: "",
  });

  const { data: accounts, isLoading, refetch } = trpc.emailAccounts.list.useQuery();
  const { data: summaryCount, refetch: refetchCount } = trpc.batch.getSummaryCount.useQuery();

  const createMutation = trpc.emailAccounts.create.useMutation({
    onSuccess: () => {
      toast.success("メールアカウントを追加しました");
      setShowForm(false);
      setFormData({
        email: "",
        imapHost: "",
        imapPort: 993,
        imapUsername: "",
        imapPassword: "",
        chatworkRoomId: "",
      });
      refetch();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const deleteMutation = trpc.emailAccounts.delete.useMutation({
    onSuccess: () => {
      toast.success("メールアカウントを削除しました");
      refetch();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const updateMutation = trpc.emailAccounts.update.useMutation({
    onSuccess: () => {
      toast.success("Chatwork Room IDを更新しました");
      setEditingAccountId(null);
      setEditChatworkRoomId("");
      refetch();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const testChatworkMutation = trpc.emailAccounts.testChatworkNotification.useMutation({
    onSuccess: (data) => {
      if (data.success) {
        toast.success(data.message);
      } else {
        toast.error(data.message);
      }
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const testConnectionMutation = trpc.emailAccounts.testConnection.useMutation({
    onSuccess: (data) => {
      if (data.success) {
        toast.success(data.message);
      } else {
        toast.error(data.message);
      }
      setTestingConnection(false);
    },
    onError: (error) => {
      toast.error(`接続テスト失敗: ${error.message}`);
      setTestingConnection(false);
    },
  });

  const resetAccountMutation = trpc.batch.resetAccount.useMutation({
    onSuccess: (data) => {
      toast.success(data.message);
      refetchCount();
    },
    onError: (error) => {
      toast.error(`リセット失敗: ${error.message}`);
    },
  });

  const resetAllMutation = trpc.batch.resetAll.useMutation({
    onSuccess: (data) => {
      toast.success(data.message);
      refetchCount();
      // リセット後に自動でバッチ実行
      triggerBatchMutation.mutate();
    },
    onError: (error) => {
      toast.error(`リセット失敗: ${error.message}`);
    },
  });

  const triggerBatchMutation = trpc.batch.triggerManually.useMutation({
    onSuccess: () => {
      toast.success("メールチェックを開始しました");
    },
    onError: (error) => {
      toast.error(`チェック失敗: ${error.message}`);
    },
  });

  const handleTestConnection = () => {
    if (!formData.imapHost || !formData.imapUsername || !formData.imapPassword) {
      toast.error("IMAP設定を入力してください");
      return;
    }

    setTestingConnection(true);
    testConnectionMutation.mutate({
      imapHost: formData.imapHost,
      imapPort: formData.imapPort,
      imapUsername: formData.imapUsername,
      imapPassword: formData.imapPassword,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData);
  };

  const handleDelete = (id: number) => {
    if (confirm("このメールアカウントを削除しますか？")) {
      deleteMutation.mutate({ id });
    }
  };

  const handleResetAccount = (id: number, email: string) => {
    if (confirm(`${email} の要約データをリセットしますか？\n次回のバッチで過去30日分のメールを再分析します。`)) {
      resetAccountMutation.mutate({ accountId: id });
    }
  };

  const handleResetAll = () => {
    if (confirm("すべてのメールアカウントの要約データをリセットしますか？\nリセット後、自動的に過去30日分のメールを再分析します。")) {
      resetAllMutation.mutate();
    }
  };

  const handleTriggerBatch = () => {
    triggerBatchMutation.mutate();
  };

  if (false) { // Disabled auth check for prototype
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (false) { // Disabled auth check for prototype
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-accent/5 to-background">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="text-center">
            <Mail className="w-12 h-12 mx-auto mb-4 text-primary" />
            <CardTitle>ログインが必要です</CardTitle>
            <CardDescription>メールアカウントを設定するにはログインしてください</CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full" onClick={() => (window.location.href = getLoginUrl())}>
              ログイン
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-accent/5 to-background">
      <div className="container py-8 max-w-4xl">
        <div className="mb-8">
          <Button variant="ghost" onClick={() => setLocation("/")}>
            ← ホームに戻る
          </Button>
        </div>

        <div className="flex items-center gap-3 mb-8">
          <div className="p-3 rounded-xl bg-primary/10">
            <SettingsIcon className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">メールアカウント設定</h1>
            <p className="text-muted-foreground">IMAPアカウントを追加して自動チェックを開始</p>
          </div>
        </div>

        {/* Summary Stats & Reset */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">要約データ管理</CardTitle>
            <CardDescription>
              現在 {summaryCount?.count ?? 0} 件の要約データがあります
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 flex-wrap">
              <Button
                variant="default"
                onClick={handleTriggerBatch}
                disabled={triggerBatchMutation.isPending || resetAllMutation.isPending}
              >
                {triggerBatchMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    チェック中...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 mr-2" />
                    今すぐチェック
                  </>
                )}
              </Button>
              <Button
                variant="destructive"
                onClick={handleResetAll}
                disabled={resetAllMutation.isPending || triggerBatchMutation.isPending}
              >
                {resetAllMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    リセット中...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    すべての要約をリセットして再分析
                  </>
                )}
              </Button>
            </div>
            <p className="text-sm text-muted-foreground mt-2">
              「今すぐチェック」は新着メールのみ、「リセットして再分析」は過去30日分を再取得
            </p>
          </CardContent>
        </Card>

        {!showForm && (
          <Button onClick={() => setShowForm(true)} className="mb-6">
            <Plus className="w-4 h-4 mr-2" />
            新しいアカウントを追加
          </Button>
        )}

        {showForm && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>新しいメールアカウント</CardTitle>
              <CardDescription>IMAP設定とChatworkルームIDを入力してください</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">メールアドレス</Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => {
                      const email = e.target.value;
                      const isGmail = email.toLowerCase().includes("gmail.com") || email.toLowerCase().includes("googlemail.com");
                      setFormData({
                        ...formData,
                        email,
                        imapUsername: email,
                        imapHost: isGmail ? "imap.gmail.com" : formData.imapHost,
                      });
                    }}
                    placeholder="your@email.com"
                    required
                  />
                </div>

                {/* Gmail検出時のアシスト表示 */}
                {(formData.email.toLowerCase().includes("gmail.com") || formData.email.toLowerCase().includes("googlemail.com")) && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                      <div className="space-y-2">
                        <p className="font-medium text-amber-800">Gmailをご利用の場合</p>
                        <p className="text-sm text-amber-700">
                          Gmailでは通常のパスワードではなく、<strong>アプリパスワード</strong>が必要です。
                          以下の手順で設定してください：
                        </p>
                        <ol className="text-sm text-amber-700 list-decimal list-inside space-y-1">
                          <li>Googleアカウントで2段階認証を有効にする</li>
                          <li>アプリパスワードを生成する</li>
                          <li>生成された16文字のパスワードを下の「IMAPパスワード」欄に入力</li>
                        </ol>
                        <a
                          href="https://myaccount.google.com/apppasswords"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-sm font-medium text-amber-800 hover:text-amber-900 underline"
                        >
                          Googleアプリパスワード設定ページを開く
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="imapHost">IMAPサーバー</Label>
                    <Input
                      id="imapHost"
                      value={formData.imapHost}
                      onChange={(e) => setFormData({ ...formData, imapHost: e.target.value })}
                      placeholder="imap.gmail.com"
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="imapPort">ポート</Label>
                    <Input
                      id="imapPort"
                      type="number"
                      value={formData.imapPort}
                      onChange={(e) => setFormData({ ...formData, imapPort: parseInt(e.target.value) })}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="imapUsername">IMAPユーザー名</Label>
                  <Input
                    id="imapUsername"
                    value={formData.imapUsername}
                    onChange={(e) => setFormData({ ...formData, imapUsername: e.target.value })}
                    placeholder="通常はメールアドレスと同じ"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="imapPassword">IMAPパスワード</Label>
                  <Input
                    id="imapPassword"
                    type="password"
                    value={formData.imapPassword}
                    onChange={(e) => setFormData({ ...formData, imapPassword: e.target.value })}
                    placeholder="アプリパスワードを推奨"
                    maxLength={undefined}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="chatworkRoomId">Chatwork ルームID</Label>
                  <Input
                    id="chatworkRoomId"
                    value={formData.chatworkRoomId}
                    onChange={(e) => setFormData({ ...formData, chatworkRoomId: e.target.value })}
                    placeholder="419007473"
                  />
                  <p className="text-sm text-muted-foreground">
                    Chatworkで通知を受け取る場合は、ルームIDを入力してください
                  </p>
                </div>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleTestConnection}
                    disabled={testingConnection}
                  >
                    {testingConnection ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        接続テスト中...
                      </>
                    ) : (
                      "接続テスト"
                    )}
                  </Button>
                  <Button type="submit" disabled={createMutation.isPending}>
                    {createMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        追加中...
                      </>
                    ) : (
                      "追加"
                    )}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                    キャンセル
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : accounts && accounts.length > 0 ? (
          <div className="space-y-4">
            {accounts.map((account) => (
              <Card key={account.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Mail className="w-5 h-5 text-primary" />
                        {account.email}
                      </CardTitle>
                      <CardDescription className="mt-2">
                        {account.imapHost}:{account.imapPort}
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleResetAccount(account.id, account.email)}
                        disabled={resetAccountMutation.isPending}
                      >
                        <RefreshCw className="w-4 h-4 mr-1" />
                        再分析
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(account.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="w-4 h-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">

                    <div className="flex justify-between">
                      <span className="text-muted-foreground">ステータス:</span>
                      <span
                        className={`font-medium ${account.isActive === "active" ? "text-green-600" : "text-gray-500"}`}
                      >
                        {account.isActive === "active" ? "有効" : "無効"}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Chatwork Room ID:</span>
                      {editingAccountId === account.id ? (
                        <div className="flex gap-2 items-center">
                          <Input
                            value={editChatworkRoomId}
                            onChange={(e) => setEditChatworkRoomId(e.target.value)}
                            placeholder="419007473"
                            className="w-32 h-8 text-sm"
                          />
                          <Button
                            size="sm"
                            onClick={() => {
                              updateMutation.mutate({
                                id: account.id,
                                chatworkRoomId: editChatworkRoomId || undefined,
                              });
                            }}
                            disabled={updateMutation.isPending}
                          >
                            保存
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setEditingAccountId(null);
                              setEditChatworkRoomId("");
                            }}
                          >
                            キャンセル
                          </Button>
                        </div>
                      ) : (
                        <div className="flex gap-2 items-center">
                          <span className="font-medium">{account.chatworkRoomId || "未設定"}</span>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setEditingAccountId(account.id);
                              setEditChatworkRoomId(account.chatworkRoomId || "");
                            }}
                          >
                            編集
                          </Button>
                          {account.chatworkRoomId && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => {
                                testChatworkMutation.mutate({
                                  chatworkRoomId: account.chatworkRoomId!,
                                });
                              }}
                              disabled={testChatworkMutation.isPending}
                            >
                              {testChatworkMutation.isPending ? (
                                <>
                                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  送信中...
                                </>
                              ) : (
                                "テスト送信"
                              )}
                            </Button>
                          )}
                        </div>
                      )}
                    </div>
                    {account.lastCheckedAt && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">最終チェック:</span>
                        <span className="font-medium">
                          {new Date(account.lastCheckedAt).toLocaleString("ja-JP")}
                        </span>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="py-12 text-center">
              <Mail className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">メールアカウントが登録されていません</p>
              <p className="text-sm text-muted-foreground mt-2">上のボタンから追加してください</p>
            </CardContent>
          </Card>
        )}
      </div>
      <div className="fixed bottom-4 right-4 text-xs text-muted-foreground">
        Ver {APP_VERSION}
      </div>
    </div>
  );
}
