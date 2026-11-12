# 展示会動画の音（BGM・効果音・ナレーション）

## いまの状態
- **効果音（16種類）**：`make_sfx_bgm.py` でゼロから合成しています（外部素材なし）。
- **BGM**：同じスクリプトで作った仮BGM（`public/expo/audio/bgm_temp.mp3`）です。135BPMで作っているので、シーンの切り替わりと小節の頭がそろいます。
- **ナレーション**：`narration.json` の原稿を VOICEVOX「春日部つむぎ」（話速1.15・抑揚強め）で音声にし、`public/expo/audio/narr_00.wav`〜`narr_10.wav` に入れてあります。画面右下に `VOICEVOX:春日部つむぎ` を表示しています（商用利用の条件）。
- **実画面（1 映画・2 HP採点）**：`scripts/expo_capture/capture_galleries.cjs` で撮った `public/expo/cinema_gallery.jpg`・`sitecheck_gallery.jpg` を使っています。映画は受付001だけを載せてQRをぼかし、採点は企業名を「企業A〜」に置き換えてサムネイルをぼかしています。8 価格帯の3枚（ココトモSNS・介護システム「みちしるべ」・制服屋サービス）も実際の画面です。

作り直すとき：

```
python3 scripts/expo_audio/make_sfx_bgm.py
npm run render:expo
```

## Suno の BGM に差し替える
1. Suno で下の設定で曲を作る（Instrumental をオン）
   - **Style**: `energetic future bass EDM, 135 BPM, A minor, bright synth plucks, punchy four-on-the-floor kick, uplifting corporate promo, instrumental, no vocals`
   - **Title**: `ENTERTAINMENT x AI`
2. 気に入った曲の mp3 を `public/expo/audio/bgm_suno.mp3` として保存
3. `src/ExpoVideo/audio.tsx` の `BGM_FILE` を `"expo/audio/bgm_suno.mp3"` に変更
4. `npm run render:expo`（BGMは最後の2.5秒で自動的にフェードアウトします）

## ナレーションを作り直す
1. VOICEVOX エンジンを起動する（このMacのアプリ、または Mac mini の `~/dev/old-photo-colorize/third_party/voicevox/engine/run`）
   - mini のエンジンを使うとき：`ssh -f -N -L 50121:127.0.0.1:50021 mac-mini` でつなぎ、`VOICEVOX_URL=http://127.0.0.1:50121` を付けて実行
2. `python3 scripts/expo_audio/make_narration.py`
   - wav を作り、音量を -16 LUFS にそろえ、`src/ExpoVideo/audio.tsx` の `NARRATION`（開始フレームと長さ）を書き換えます
   - 読み間違いは `narration.json` の `kana`、長すぎる行は `speed` と `frame` で直します（次の行と重なると警告が出ます）
3. 動画内の `VOICEVOX:春日部つむぎ` 表記は消さないでください

## 実画面を撮り直す
両方のギャラリー（8820・8792）を起動してから：

```
PLAYWRIGHT=/path/to/node_modules/playwright node scripts/expo_capture/capture_galleries.cjs
```

載せる映画は `CINEMA_JOB=001` のように受付番号で選びます（顔が写るので、掲載してよい作品だけにしてください）。カードの位置が変わったら `scenes.tsx` の `CINEMA`・`SITECHECK` の座標も直します。

8 価格帯の「介護システム」カード（`public/expo/michishirube.jpg`）は、みちしるべのTOP画面（ログインが必要）を Safari の窓ごと撮り、上下を切って 1920×1200 に合わせたものです。スクリプトでは撮れないので、差し替えるときは同じように画面を撮り、利用者名などの個人情報が写っていないことを確かめてから置き換えます。

## 書き出しで「No browser found」になるとき
Remotion 付属の Chrome が壊れているときは、Playwright の Chrome を指定して書き出せます：

```
npm run render:expo -- --browser-executable="$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell"
```
