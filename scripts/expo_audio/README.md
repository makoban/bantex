# 展示会動画の音（BGM・効果音・ナレーション）

## いまの状態
- **効果音（16種類）**：`make_sfx_bgm.py` でゼロから合成しています（外部素材なし）。
- **BGM**：同じスクリプトで作った仮BGM（`public/expo/audio/bgm_temp.mp3`）です。135BPMで作っているので、シーンの切り替わりと小節の頭がそろいます。
- **ナレーション**：原稿は `narration.json` にあります。音声ファイルはまだありません。

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

## ナレーションを入れる
1. `narration.json` の各行を音声にする（例：VOICEVOX「春日部つむぎ」、話速1.15くらい）
2. `public/expo/audio/narr_00.wav` 〜 `narr_10.wav` として保存
3. `src/ExpoVideo/audio.tsx` の `NARRATION` に `{ at: フレーム, file: "expo/audio/narr_00.wav", len: 長さ(フレーム) }` を並べる
4. VOICEVOX を使った場合は、動画内に `VOICEVOX:キャラクター名` のクレジット表記が必要です
