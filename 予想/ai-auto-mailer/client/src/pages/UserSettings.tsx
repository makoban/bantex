import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { trpc } from "@/lib/trpc";
import { Loader2, Settings, User, Ban, Trash2 } from "lucide-react";
import { APP_VERSION } from "../../../shared/version";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useLocation } from "wouter";

export default function UserSettings() {
  const [, setLocation] = useLocation();
  
  const [formData, setFormData] = useState({
    chatworkInterval: 10,
    personalName: "",
    companyName: "",
    additionalKeywords: "",
    ignorePromotions: true,
    ignoreSales: true,
    detectReplyNeeded: true,
    includeReplySuggestion: false,
    sendEmptyNotification: false,
    minimumImportance: "medium" as "medium" | "high",
    customPrompt: "",
  });

  const [newIgnoredSender, setNewIgnoredSender] = useState({
    senderEmail: "",
    senderName: "",
    reason: "",
  });

  const { data: settings, isLoading, refetch } = trpc.userSettings.get.useQuery();
  const { data: ignoredSenders, refetch: refetchIgnored } = trpc.userSettings.getIgnoredSenders.useQuery();

  const updateMutation = trpc.userSettings.update.useMutation({
    onSuccess: () => {
      toast.success("設定を保存しました");
      refetch();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const addIgnoredMutation = trpc.userSettings.addIgnoredSender.useMutation({
    onSuccess: () => {
      toast.success("無視リストに追加しました");
      setNewIgnoredSender({ senderEmail: "", senderName: "", reason: "" });
      refetchIgnored();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  const removeIgnoredMutation = trpc.userSettings.removeIgnoredSender.useMutation({
    onSuccess: () => {
      toast.success("無視リストから削除しました");
      refetchIgnored();
    },
    onError: (error) => {
      toast.error(`エラー: ${error.message}`);
    },
  });

  useEffect(() => {
    if (settings) {
      setFormData({
        chatworkInterval: settings.chatworkInterval || 10,
        personalName: settings.personalName || "",
        companyName: settings.companyName || "",
        additionalKeywords: settings.additionalKeywords || "",
        ignorePromotions: settings.ignorePromotions ?? true,
        ignoreSales: settings.ignoreSales ?? true,
        detectReplyNeeded: settings.detectReplyNeeded ?? true,
        includeReplySuggestion: settings.includeReplySuggestion ?? false,
        sendEmptyNotification: settings.sendEmptyNotification ?? false,
        minimumImportance: (settings.minimumImportance || "medium") as "medium" | "high",
        customPrompt: settings.customPrompt || "",
      });
    }
  }, [settings]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(formData);
  };

  const handleAddIgnored = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newIgnoredSender.senderEmail) {
      toast.error("メールアドレスを入力してください");
      return;
    }
    addIgnoredMutation.mutate(newIgnoredSender);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
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
            <User className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">ユーザー設定</h1>
            <p className="text-muted-foreground">AI分析と通知のカスタマイズ</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Chatwork設定 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                Chatwork通知設定
              </CardTitle>
              <CardDescription>
                各メールアカウントの設定画面でRoom IDを設定してください
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="chatworkInterval">通知間隔（分）</Label>
                <select
                  id="chatworkInterval"
                  value={formData.chatworkInterval}
                  onChange={(e) => setFormData({ ...formData, chatworkInterval: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value={10}>10分</option>
                  <option value={20}>20分</option>
                  <option value={60}>60分</option>
                </select>
                <p className="text-sm text-muted-foreground">
                  この間隔で受信したメールをまとめて通知します
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 個人情報設定 */}
          <Card>
            <CardHeader>
              <CardTitle>個人情報（重要度判定用）</CardTitle>
              <CardDescription>
                あなたの名前や会社名が含まれるメールは重要度が上がります
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="personalName">あなたの名前</Label>
                  <Input
                    id="personalName"
                    value={formData.personalName}
                    onChange={(e) => setFormData({ ...formData, personalName: e.target.value })}
                    placeholder="山田太郎"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="companyName">会社名</Label>
                  <Input
                    id="companyName"
                    value={formData.companyName}
                    onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
                    placeholder="株式会社〇〇"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="additionalKeywords">追加キーワード（カンマ区切り）</Label>
                <Input
                  id="additionalKeywords"
                  value={formData.additionalKeywords}
                  onChange={(e) => setFormData({ ...formData, additionalKeywords: e.target.value })}
                  placeholder="プロジェクトA, 緊急, 重要"
                />
                <p className="text-sm text-muted-foreground">
                  これらのキーワードが含まれるメールは重要度が上がります
                </p>
              </div>
            </CardContent>
          </Card>

          {/* AI分析オプション */}
          <Card>
            <CardHeader>
              <CardTitle>AI分析オプション</CardTitle>
              <CardDescription>
                メールの分析方法をカスタマイズします
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <Label>宣伝メールを自動で無視</Label>
                  <p className="text-sm text-muted-foreground">
                    プロモーションやニュースレターを自動的にスキップ
                  </p>
                </div>
                <Switch
                  checked={formData.ignorePromotions}
                  onCheckedChange={(checked) => setFormData({ ...formData, ignorePromotions: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>営業メールを自動で無視</Label>
                  <p className="text-sm text-muted-foreground">
                    セールスや勧誘メールを自動的にスキップ
                  </p>
                </div>
                <Switch
                  checked={formData.ignoreSales}
                  onCheckedChange={(checked) => setFormData({ ...formData, ignoreSales: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>返信が必要かを判定</Label>
                  <p className="text-sm text-muted-foreground">
                    あなたが返信すべきメールかどうかをAIが判定
                  </p>
                </div>
                <Switch
                  checked={formData.detectReplyNeeded}
                  onCheckedChange={(checked) => setFormData({ ...formData, detectReplyNeeded: checked })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>Chatworkに返信案を含める</Label>
                  <p className="text-sm text-muted-foreground">
                    通知に返信例を表示します(デフォルト:オフ)
                  </p>
                </div>
                <Switch
                  checked={formData.includeReplySuggestion}
                  onCheckedChange={(checked) => setFormData({ ...formData, includeReplySuggestion: checked })}
                />
              </div>
            </CardContent>
          </Card>

          {/* 通知フィルター設定 */}
          <Card>
            <CardHeader>
              <CardTitle>通知フィルター設定</CardTitle>
              <CardDescription>
                どのメールを通知するかを設定します
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="minimumImportance">送信する重要度レベル</Label>
                <select
                  id="minimumImportance"
                  value={formData.minimumImportance}
                  onChange={(e) => setFormData({ ...formData, minimumImportance: e.target.value as "medium" | "high" })}
                  className="w-full px-3 py-2 border rounded-md bg-background"
                >
                  <option value="medium">中以上（中・高）</option>
                  <option value="high">高のみ</option>
                </select>
                <p className="text-sm text-muted-foreground">
                  この重要度以上のメールのみ通知します
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label>重要なメールがない場合も通知する</Label>
                  <p className="text-sm text-muted-foreground">
                    オフの場合、重要なメールがないときは通知しません（デフォルト:オフ）
                  </p>
                </div>
                <Switch
                  checked={formData.sendEmptyNotification}
                  onCheckedChange={(checked) => setFormData({ ...formData, sendEmptyNotification: checked })}
                />
              </div>
            </CardContent>
          </Card>

          {/* カスタムプロンプト */}
          <Card>
            <CardHeader>
              <CardTitle>カスタムAIプロンプト（上級者向け）</CardTitle>
              <CardDescription>
                AIの分析方法をカスタマイズするプロンプトを入力できます
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={formData.customPrompt}
                onChange={(e) => setFormData({ ...formData, customPrompt: e.target.value })}
                placeholder="例: 技術的な内容のメールは重要度を上げてください。社内の定例会議の案内は低優先度にしてください。"
                rows={4}
              />
            </CardContent>
          </Card>

          <Button type="submit" disabled={updateMutation.isPending} className="w-full">
            {updateMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                保存中...
              </>
            ) : (
              "設定を保存"
            )}
          </Button>
        </form>

        {/* 無視リスト */}
        <Card className="mt-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Ban className="w-5 h-5" />
              無視する送信者リスト
            </CardTitle>
            <CardDescription>
              このリストに追加された送信者からのメールは分析されません
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handleAddIgnored} className="flex gap-2">
              <Input
                value={newIgnoredSender.senderEmail}
                onChange={(e) => setNewIgnoredSender({ ...newIgnoredSender, senderEmail: e.target.value })}
                placeholder="spam@example.com"
                type="email"
                className="flex-1"
              />
              <Button type="submit" disabled={addIgnoredMutation.isPending}>
                追加
              </Button>
            </form>

            {ignoredSenders && ignoredSenders.length > 0 ? (
              <div className="space-y-2">
                {ignoredSenders.map((sender) => (
                  <div key={sender.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                    <div>
                      <p className="font-medium">{sender.senderEmail}</p>
                      {sender.senderName && (
                        <p className="text-sm text-muted-foreground">{sender.senderName}</p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeIgnoredMutation.mutate({ id: sender.id })}
                      disabled={removeIgnoredMutation.isPending}
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                無視リストは空です
              </p>
            )}
          </CardContent>
        </Card>
      </div>
      <div className="fixed bottom-4 right-4 text-xs text-muted-foreground">
        Ver {APP_VERSION}
      </div>
    </div>
  );
}
