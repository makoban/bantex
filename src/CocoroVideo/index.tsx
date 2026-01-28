
import { AbsoluteFill, Img, useCurrentFrame, useVideoConfig, interpolate, Easing, staticFile, Audio } from "remotion";

const images = [
  "interior.png",
  "style.png",
  "shampoo.png",
  "closeup.png",
  "products.png",
  "reception.png",
];

const captions = [
  "日常を忘れる、極上のプライベート空間",
  "30代からの髪質改善",
  "あなただけの「似合わせ」スタイル",
  "心まで満たされる癒やしのひととき",
  "厳選されたオーガニックアイテム",
  "COCOROで、新しい自分へ",
];

export const CocoroVideo = () => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();

  // 1枚あたりの表示時間
  const displayTime = 150; // 5秒
  const transitionTime = 30; // 1秒

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
       {/* BGM: Audioコンポーネントを追加 */}
      <Audio
        src={staticFile("cocoro/relaxing_bgm_v2.mp3")}
        volume={(f) =>
          interpolate(
            f,
            [0, 30, durationInFrames - 60, durationInFrames],
            [0, 0.15, 0.15, 0], // 音量を0.4から0.15に下げて、より静かに
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          )
        }
      />

      {images.map((img, index) => {
        const startFrame = index * (displayTime - transitionTime);
        const endFrame = startFrame + displayTime;

        // 自分の順番が来ていない、または終わった画像は描画しない（パフォーマンス）
        if (frame < startFrame || frame > endFrame) return null;

        const progress = interpolate(
          frame,
          [startFrame, endFrame],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        // フェードイン・アウト
        const opacity = interpolate(
          frame,
          [startFrame, startFrame + transitionTime, endFrame - transitionTime, endFrame],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        // ケン・バーンズ効果（ズーム）
        const scale = interpolate(
          progress,
          [0, 1],
          [1, 1.1],
          { easing: Easing.out(Easing.quad) }
        );

        return (
          <AbsoluteFill key={img} style={{ opacity }}>
             <Img
              src={staticFile(`cocoro/${img}`)}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: `scale(${scale})`,
              }}
            />
            {/* キャプション */}
            <div style={{
                position: 'absolute',
                bottom: 100,
                left: 0,
                width: '100%',
                textAlign: 'center',
                color: 'white',
                fontFamily: '"Noto Serif JP", serif',
                textShadow: '0 2px 4px rgba(0,0,0,0.8)',
                fontSize: 50,
                fontWeight: 600,
                letterSpacing: '0.1em'
            }}>
                {captions[index]}
            </div>
          </AbsoluteFill>
        );
      })}

      {/* ロゴ・フィナーレ */}
       <AbsoluteFill
        style={{
            opacity: interpolate(
                frame,
                [durationInFrames - 90, durationInFrames - 30],
                [0, 1],
                { extrapolateLeft: "clamp" }
            ),
            backgroundColor: 'rgba(255,255,255,0.9)',
            justifyContent: 'center',
            alignItems: 'center',
            flexDirection: 'column'
        }}
      >
          <div style={{
              fontFamily: '"Cormorant Garamond", serif',
              fontSize: 120,
              color: '#5D5C61',
              letterSpacing: '0.2em',
              marginBottom: 20
          }}>
              COCORO
          </div>
          <div style={{
              fontFamily: '"Noto Sans JP", sans-serif',
              fontSize: 30,
              color: '#333',
              letterSpacing: '0.1em'
          }}>
              Webからのご予約をお待ちしております
          </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
