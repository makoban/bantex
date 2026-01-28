# ai-auto-mailer/boatrace-collector/render.yaml at main · makoban/ai-auto-mailer

**URL:** https://github.com/makoban/ai-auto-mailer/blob/main/boatrace-collector/render.yaml

---

Skip to content
Navigation Menu
makoban
/
ai-auto-mailer
Type / to search
Code
Issues
Pull requests
Actions
Projects
Security
Insights
Settings
 main
Breadcrumbs
ai-auto-mailer/boatrace-collector
/render.yaml
t
Latest commit
makoban
feat: 結果収集バッチにManus Space DB更新機能を追加
37da0b2
 · 
History
History
File metadata and controls
Code
Blame
Raw
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
31
32
33
34
35
36
37
38
39
40
41
42
43
44
45
46
47
48
49
50
51
52
53
54
55
56
# Render Blueprint - 競艇データ収集システム
# このファイルをリポジトリのルートに配置してください


services:
  # 日次収集ジョブ（毎朝8:00 JST = 23:00 UTC前日）
  - type: cron
    name: boatrace-daily-collection
    runtime: python
    buildCommand: pip install -r boatrace-collector/requirements.txt
    startCommand: cd boatrace-collector/src && python cron_jobs.py daily
    schedule: "0 23 * * *"  # 毎日 23:00 UTC (= 08:00 JST)
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: kokotomo-db-staging
          property: connectionString
      - key: TZ
        value: Asia/Tokyo


  # 定期オッズ収集ジョブ（10分ごと、8:00-21:00 JST）
  - type: cron
    name: boatrace-odds-regular
    runtime: python
    buildCommand: pip install -r boatrace-collector/requirements.txt
    startCommand: cd boatrace-collector/src && python cron_jobs.py odds_regular
    schedule: "*/10 23,0-12 * * *"  # 23:00-12:59 UTC (= 08:00-21:59 JST)
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: kokotomo-db-staging
          property: connectionString
      - key: TZ
        value: Asia/Tokyo


  # 結果収集ジョブ（15分ごと）
  # 追加機能: Manus Space DBのvirtualBetsも更新
  - type: cron
    name: boatrace-result-collection
    runtime: python
    buildCommand: pip install -r boatrace-collector/requirements.txt
    startCommand: cd boatrace-collector/src && python cron_jobs.py result
    schedule: "*/15 23,0-13 * * *"  # 23:00-13:59 UTC (= 08:00-22:59 JST)
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: kokotomo-db-staging
          property: connectionString
      - key: MANUS_DATABASE_URL
        sync: false  # 手動で設定が必要
      - key: TZ
        value: Asia/Tokyo


databases:
  - name: kokotomo-db-staging
    plan: basic-256mb
    region: singapore