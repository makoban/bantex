import React from "react";
import { Audio, Sequence, interpolate, staticFile } from "remotion";
import { OUTRO_START, TOTAL, sceneStart } from "./theme";

/*
 * 音まわり（BGM・効果音・ナレーション）
 * - BGM_FILE を Suno で作った曲に差し替えれば、そのまま使えます
 * - ナレーションは NARRATION に {frame, file} を並べると再生されます
 */
export const BGM_FILE = "expo/audio/bgm_temp.mp3";
const BGM_VOLUME = 0.32;
const SFX_MASTER = 0.8;

type Cue = { at: number; file: string; vol: number };
type Narr = { at: number; file: string; len: number };

export const NARRATION: Narr[] = [];

const s = (i: number, f: number) => sceneStart(i) + f;

const SFX: Cue[] = [
  // イントロ
  { at: 0, file: "riser", vol: 0.5 },
  { at: 16, file: "impact", vol: 0.9 },
  { at: 30, file: "swish", vol: 0.4 },
  { at: 60, file: "pop", vol: 0.7 },
  // 01 映画
  { at: s(0, 10), file: "impact", vol: 0.8 },
  { at: s(0, 16), file: "pop", vol: 0.5 },
  { at: s(0, 58), file: "pop", vol: 0.7 },
  // 02 HP採点
  { at: s(1, 12), file: "scan", vol: 0.45 },
  { at: s(1, 30), file: "impact", vol: 0.8 },
  { at: s(1, 34), file: "check", vol: 0.5 },
  { at: s(1, 46), file: "check", vol: 0.5 },
  { at: s(1, 58), file: "check", vol: 0.5 },
  { at: s(1, 70), file: "check", vol: 0.5 },
  { at: s(1, 100), file: "ding", vol: 0.6 },
  // 03 エンタメ×AI
  { at: s(2, 10), file: "impact", vol: 0.8 },
  { at: s(2, 24), file: "swish", vol: 0.5 },
  { at: s(2, 34), file: "impact", vol: 0.9 },
  { at: s(2, 62), file: "swish", vol: 0.4 },
  // 04 プロデューサー
  { at: s(3, 20), file: "reel", vol: 0.7 },
  { at: s(3, 62), file: "jackpot", vol: 0.7 },
  { at: s(3, 62), file: "hit", vol: 0.6 },
  { at: s(3, 88), file: "hit", vol: 0.6 },
  // 05 早い安い
  { at: s(4, 8), file: "whoosh", vol: 0.4 },
  { at: s(4, 18), file: "impact", vol: 0.8 },
  { at: s(4, 34), file: "impact", vol: 0.8 },
  { at: s(4, 66), file: "swish", vol: 0.4 },
  { at: s(4, 92), file: "hit", vol: 0.6 },
  { at: s(4, 100), file: "hit", vol: 0.5 },
  { at: s(4, 108), file: "impact", vol: 0.9 },
  { at: s(4, 120), file: "pop", vol: 0.4 },
  // 06 LINE
  { at: s(5, 26), file: "message", vol: 0.5 },
  { at: s(5, 30), file: "impact", vol: 0.7 },
  { at: s(5, 48), file: "message", vol: 0.5 },
  { at: s(5, 74), file: "message", vol: 0.5 },
  { at: s(5, 96), file: "message", vol: 0.5 },
  { at: s(5, 112), file: "impact", vol: 0.8 },
  // 07 丸一日
  { at: s(6, 20), file: "pop", vol: 0.35 },
  { at: s(6, 26), file: "pop", vol: 0.35 },
  { at: s(6, 32), file: "pop", vol: 0.35 },
  { at: s(6, 38), file: "pop", vol: 0.35 },
  { at: s(6, 40), file: "stamp", vol: 0.8 },
  { at: s(6, 68), file: "whoosh", vol: 0.4 },
  { at: s(6, 82), file: "clock", vol: 0.55 },
  { at: s(6, 86), file: "impact", vol: 0.8 },
  { at: s(6, 132), file: "impact", vol: 0.8 },
  // 08 価格帯
  { at: s(7, 22), file: "swish", vol: 0.5 },
  { at: s(7, 32), file: "swish", vol: 0.5 },
  { at: s(7, 42), file: "swish", vol: 0.5 },
  { at: s(7, 56), file: "pop", vol: 0.5 },
  { at: s(7, 74), file: "impact", vol: 0.8 },
  { at: s(7, 84), file: "swish", vol: 0.3 },
  // 09 運用
  { at: s(8, 26), file: "whoosh", vol: 0.45 },
  { at: s(8, 84), file: "snap", vol: 0.9 },
  { at: s(8, 86), file: "pop", vol: 0.5 },
  { at: s(8, 112), file: "impact", vol: 0.8 },
  // アウトロ
  { at: OUTRO_START + 14, file: "swish", vol: 0.3 },
  { at: OUTRO_START + 56, file: "pop", vol: 0.6 },
  { at: OUTRO_START + 60, file: "sparkle", vol: 0.5 },
  { at: OUTRO_START + 80, file: "ding", vol: 0.35 },
  // シーン切替のシュッ
  ...new Array(9).fill(0).map((_, i) => ({ at: sceneStart(i) - 10, file: "whoosh", vol: 0.6 })),
  { at: OUTRO_START - 10, file: "whoosh", vol: 0.6 },
];

// ナレーション中はBGMを少し下げる
const bgmVolume = (f: number) => {
  const fade = interpolate(f, [0, 8, TOTAL - 75, TOTAL - 5], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  let duck = 1;
  for (const n of NARRATION) {
    const d = interpolate(f, [n.at - 6, n.at, n.at + n.len, n.at + n.len + 8], [1, 0.55, 0.55, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    duck = Math.min(duck, d);
  }
  return BGM_VOLUME * fade * duck;
};

export const Soundtrack: React.FC = () => {
  return (
    <>
      <Audio src={staticFile(BGM_FILE)} volume={bgmVolume} />
      {SFX.map((c, i) => (
        <Sequence key={`sfx${i}`} from={Math.max(0, c.at)} durationInFrames={120} name={`SE ${c.file}`}>
          <Audio src={staticFile(`expo/audio/${c.file}.wav`)} volume={c.vol * SFX_MASTER} />
        </Sequence>
      ))}
      {NARRATION.map((n, i) => (
        <Sequence key={`nar${i}`} from={n.at} durationInFrames={n.len + 10} name={`ナレーション ${i}`}>
          <Audio src={staticFile(n.file)} volume={1} />
        </Sequence>
      ))}
    </>
  );
};
