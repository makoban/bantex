import "@fontsource/dela-gothic-one/400.css";
import "@fontsource/noto-sans-jp/700.css";
import "@fontsource/noto-sans-jp/900.css";
import "@fontsource/anton/400.css";
import React, { useEffect, useState } from "react";
import {
  AbsoluteFill,
  Sequence,
  continueRender,
  delayRender,
  useCurrentFrame,
} from "remotion";
import { Soundtrack } from "./audio";
import { Background, FreeBadge, Ticker, Wipe } from "./components";
import {
  Intro,
  Outro,
  S1Movie,
  S2Score,
  S3Concept,
  S4Producer,
  S5Speed,
  S6Line,
  S7Visit,
  S8Price,
  S9Fit,
} from "./scenes";
import {
  ACCENTS,
  ALL_TEXT,
  INTRO_LEN,
  OUTRO_LEN,
  OUTRO_START,
  SCENE_LEN,
  sceneStart,
} from "./theme";

const SCENES = [S1Movie, S2Score, S3Concept, S4Producer, S5Speed, S6Line, S7Visit, S8Price, S9Fit];

// 日本語フォントの必要な文字を先に読み込んでから描画する
const useFonts = () => {
  const [handle] = useState(() => delayRender("Loading fonts"));
  useEffect(() => {
    const loads = [
      document.fonts.load('400 100px "Dela Gothic One"', ALL_TEXT),
      document.fonts.load('900 100px "Noto Sans JP"', ALL_TEXT),
      document.fonts.load('700 100px "Noto Sans JP"', ALL_TEXT),
      document.fonts.load('400 100px "Anton"', ALL_TEXT),
    ];
    Promise.all(loads)
      .then(() => document.fonts.ready)
      .then(() => continueRender(handle))
      .catch(() => continueRender(handle));
  }, [handle]);
};

export const ExpoVideo: React.FC = () => {
  useFonts();
  const frame = useCurrentFrame();
  const idx =
    frame < INTRO_LEN
      ? 0
      : frame >= OUTRO_START
        ? ACCENTS.length - 1
        : 1 + Math.floor((frame - INTRO_LEN) / SCENE_LEN);
  const [accent, accent2] = ACCENTS[Math.min(idx, ACCENTS.length - 2)];
  const inPoints = frame >= INTRO_LEN && frame < OUTRO_START;

  return (
    <AbsoluteFill style={{ backgroundColor: "#06070f" }}>
      <Soundtrack />
      <Background accent={accent} accent2={accent2} />

      <Sequence durationInFrames={INTRO_LEN} name="Intro">
        <Intro />
      </Sequence>

      {SCENES.map((Scene, i) => (
        <Sequence key={i} from={sceneStart(i)} durationInFrames={SCENE_LEN} name={`Point ${i + 1}`}>
          <Scene />
        </Sequence>
      ))}

      {inPoints ? (
        <>
          <Ticker color={accent} />
          <FreeBadge appear={INTRO_LEN + 8} />
        </>
      ) : null}

      <Sequence from={OUTRO_START} durationInFrames={OUTRO_LEN} name="Outro">
        <Outro />
      </Sequence>

      {/* シーン切替ワイプ */}
      {SCENES.map((_, i) => (
        <Wipe key={i} at={sceneStart(i)} color={ACCENTS[i + 1][0]} color2={ACCENTS[i + 1][1]} />
      ))}
      <Wipe at={OUTRO_START} color="#ffffff" color2="#FFD400" />

      {/* 音声合成のクレジット（VOICEVOX 春日部つむぎの利用条件） */}
      <div
        style={{
          position: "absolute",
          right: 22,
          bottom: inPoints ? 72 : 14,
          fontFamily: '"Noto Sans JP", sans-serif',
          fontWeight: 700,
          fontSize: 18,
          color: "rgba(255,255,255,.75)",
          textShadow: "0 1px 4px rgba(0,0,0,.8)",
        }}
      >
        VOICEVOX:春日部つむぎ
      </div>
    </AbsoluteFill>
  );
};
