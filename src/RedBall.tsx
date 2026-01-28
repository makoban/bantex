import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

export const RedBall: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // バウンドアニメーション（Y軸）
  const bounce = spring({
    frame: frame % 30,
    fps,
    config: {
      damping: 10,
      stiffness: 100,
    },
  });

  // X軸の移動（左右に揺れる）
  const xMovement = interpolate(
    frame,
    [0, 75, 150],
    [300, width - 300, 300],
    { extrapolateRight: "clamp" }
  );

  // Y軸のバウンド
  const yBase = height / 2;
  const yOffset = interpolate(bounce, [0, 1], [100, -100]);

  // 回転
  const rotation = interpolate(frame, [0, 150], [0, 720]);

  // スケール（跳ねるときに少し潰れる）
  const scaleY = interpolate(bounce, [0, 0.5, 1], [0.9, 1.1, 1]);
  const scaleX = interpolate(bounce, [0, 0.5, 1], [1.1, 0.9, 1]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(180deg, #87CEEB 0%, #E0F6FF 100%)",
      }}
    >
      {/* ボールの影 */}
      <div
        style={{
          position: "absolute",
          top: yBase + 180,
          left: xMovement - 60,
          width: 120,
          height: 30,
          borderRadius: "50%",
          background: "rgba(0, 0, 0, 0.2)",
          filter: "blur(10px)",
          transform: `scaleX(${1 + (yOffset / 200)})`,
        }}
      />

      {/* ドラえもんボール */}
      <div
        style={{
          position: "absolute",
          top: yBase + yOffset - 75,
          left: xMovement - 75,
          width: 150,
          height: 150,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #FF4444 50%, #FFFFFF 50%)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3), inset -5px -5px 20px rgba(0, 0, 0, 0.2), inset 5px 5px 20px rgba(255, 255, 255, 0.4)",
          transform: `rotate(${rotation}deg) scaleX(${scaleX}) scaleY(${scaleY})`,
          border: "3px solid #333",
        }}
      >
        {/* 中央の白い星（ハイライト） */}
        <div
          style={{
            position: "absolute",
            top: 20,
            left: 25,
            width: 30,
            height: 20,
            borderRadius: "50%",
            background: "rgba(255, 255, 255, 0.7)",
            transform: "rotate(-30deg)",
          }}
        />
      </div>

      {/* キラキラエフェクト */}
      {[0, 1, 2].map((i) => {
        const sparkleFrame = (frame + i * 50) % 150;
        const sparkleOpacity = interpolate(
          sparkleFrame,
          [0, 20, 40],
          [0, 1, 0],
          { extrapolateRight: "clamp" }
        );
        const sparkleScale = interpolate(
          sparkleFrame,
          [0, 20, 40],
          [0.5, 1.2, 0.5],
          { extrapolateRight: "clamp" }
        );
        const sparkleX = xMovement + (i - 1) * 100;
        const sparkleY = yBase + yOffset - 120 + Math.sin(frame * 0.1 + i) * 20;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: sparkleY,
              left: sparkleX,
              fontSize: 30,
              opacity: sparkleOpacity,
              transform: `scale(${sparkleScale})`,
            }}
          >
            ✨
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
