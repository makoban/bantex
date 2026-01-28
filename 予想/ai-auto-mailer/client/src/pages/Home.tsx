import { Button } from "@/components/ui/button";
import { Mail, Sparkles, Clock, User, LogOut } from "lucide-react";
import { useLocation } from "wouter";
import { useAuth } from "@/hooks/useAuth";
import { APP_VERSION } from "../../../shared/version";

export default function Home() {
  const [, setLocation] = useLocation();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 via-accent/5 to-background">
      {/* Header with user info */}
      <div className="absolute top-4 right-4 flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <User className="w-4 h-4" />
            <span>{user.name || user.email}</span>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={logout}>
          <LogOut className="w-4 h-4 mr-2" />
          ログアウト
        </Button>
      </div>

      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto text-center">
          {/* Header */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6">
              <Sparkles className="w-4 h-4" />
              AI Auto Mailer
              <span className="ml-2 px-2 py-0.5 bg-primary/20 rounded text-xs">Ver {APP_VERSION}</span>
            </div>
            <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              あなたのメールを
              <br />
              自動でチェック
            </h1>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              5分ごとに要約して重要なメールを逃しません
            </p>
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-8">
            <Button
              size="lg"
              className="text-lg px-8 py-6"
              onClick={() => setLocation("/settings")}
            >
              <Mail className="w-5 h-5 mr-2" />
              メールアカウント設定
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="text-lg px-8 py-6"
              onClick={() => setLocation("/summaries")}
            >
              メール要約を見る
            </Button>
          </div>

          {/* User Settings Button */}
          <div className="mb-16">
            <Button
              variant="ghost"
              className="text-muted-foreground"
              onClick={() => setLocation("/user-settings")}
            >
              <User className="w-4 h-4 mr-2" />
              AI分析・通知設定
            </Button>
          </div>

          {/* Features */}
          <div className="grid md:grid-cols-3 gap-8 mt-16">
            <div className="p-6 rounded-2xl bg-card border border-border">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 mx-auto">
                <Clock className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">5分毎の自動チェック</h3>
              <p className="text-sm text-muted-foreground">
                設定後は完全自動。手動でメールを確認する必要はありません。
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-card border border-border">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 mx-auto">
                <Sparkles className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">AIによる重要度判定</h3>
              <p className="text-sm text-muted-foreground">
                営業メールや迷惑メールを自動で除外。本当に重要なメールだけを通知。
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-card border border-border">
              <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4 mx-auto">
                <Mail className="w-6 h-6 text-primary" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Chatwork通知</h3>
              <p className="text-sm text-muted-foreground">
                重要なメールの概要をChatworkに自動送信。詳細はWebで確認。
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="fixed bottom-4 right-4 text-xs text-muted-foreground">
        Ver {APP_VERSION}
      </div>
    </div>
  );
}
