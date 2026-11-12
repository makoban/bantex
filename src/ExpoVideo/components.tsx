import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  random,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C, FONT_DISPLAY, FONT_EN, FONT_JP } from "./theme";

export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

export const img = (name: string) => staticFile(`expo/${name}`);

export const gradientText = (
  a: string,
  b: string,
  angle = 100,
): React.CSSProperties => ({
  backgroundImage: `linear-gradient(${angle}deg, ${a}, ${b})`,
  WebkitBackgroundClip: "text",
  backgroundClip: "text",
  color: "transparent",
});

/* ------------------------------------------------------------------ */
/* 文字を1文字ずつ動かすテキスト                                        */
/* ------------------------------------------------------------------ */
type KTextProps = {
  text: string;
  delay?: number;
  stagger?: number;
  size: number;
  color?: string;
  font?: string;
  weight?: number;
  from?: "up" | "down" | "scale" | "left" | "right";
  glow?: string;
  stroke?: string;
  align?: "flex-start" | "center" | "flex-end";
  style?: React.CSSProperties;
  charStyle?: React.CSSProperties;
};

export const KText: React.FC<KTextProps> = ({
  text,
  delay = 0,
  stagger = 2,
  size,
  color = C.white,
  font = FONT_DISPLAY,
  weight = 400,
  from = "up",
  glow,
  stroke,
  align = "flex-start",
  style,
  charStyle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const chars = Array.from(text);
  return (
    <div
      style={{
        display: "flex",
        justifyContent: align,
        fontFamily: font,
        fontSize: size,
        fontWeight: weight,
        color,
        lineHeight: 1.15,
        whiteSpace: "pre",
        ...style,
      }}
    >
      {chars.map((ch, i) => {
        const local = frame - delay - i * stagger;
        const s = spring({
          frame: local,
          fps,
          config: { damping: 12, stiffness: 190, mass: 0.7 },
        });
        const op = interpolate(local, [0, 4], [0, 1], clamp);
        let tf = "";
        if (from === "up")
          tf = `translateY(${(1 - s) * 0.75 * size}px) rotate(${(1 - s) * 10}deg)`;
        if (from === "down") tf = `translateY(${-(1 - s) * 0.75 * size}px)`;
        if (from === "scale") tf = `scale(${1 + (1 - s) * 1.6})`;
        if (from === "left") tf = `translateX(${-(1 - s) * 1.2 * size}px)`;
        if (from === "right") tf = `translateX(${(1 - s) * 1.2 * size}px)`;
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: op,
              transform: tf,
              textShadow: glow
                ? `0 0 ${size * 0.22}px ${glow}, 0 0 ${size * 0.05}px ${glow}`
                : "0 6px 24px rgba(0,0,0,.45)",
              WebkitTextStroke: stroke,
              ...charStyle,
            }}
          >
            {ch === " " ? " " : ch}
          </span>
        );
      })}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* ドンッと叩きつける登場                                               */
/* ------------------------------------------------------------------ */
export const Slam: React.FC<{
  delay: number;
  fromScale?: number;
  rotate?: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ delay, fromScale = 2.4, rotate = 0, style, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 9, stiffness: 230, mass: 0.6 },
  });
  const op = interpolate(frame - delay, [0, 3], [0, 1], clamp);
  return (
    <div
      style={{
        display: "inline-block",
        opacity: op,
        transform: `scale(${interpolate(s, [0, 1], [fromScale, 1])}) rotate(${(1 - s) * rotate}deg)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/* ポップ（バネで拡大） */
export const Pop: React.FC<{
  delay: number;
  style?: React.CSSProperties;
  children: React.ReactNode;
  rotate?: number;
}> = ({ delay, style, children, rotate = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 11, stiffness: 200, mass: 0.7 },
  });
  return (
    <div
      style={{
        transform: `scale(${s}) rotate(${(1 - s) * rotate}deg)`,
        opacity: interpolate(frame - delay, [0, 3], [0, 1], clamp),
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/* 衝撃でブルッと揺れる */
export const Shake: React.FC<{
  impacts: number[];
  amp?: number;
  children: React.ReactNode;
}> = ({ impacts, amp = 18, children }) => {
  const frame = useCurrentFrame();
  let x = 0;
  let y = 0;
  for (const at of impacts) {
    const d = frame - at;
    if (d >= 0 && d < 12) {
      const a = amp * (1 - d / 12);
      x += (random(`sx${at}-${frame}`) - 0.5) * 2 * a;
      y += (random(`sy${at}-${frame}`) - 0.5) * 2 * a;
    }
  }
  return (
    <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px)` }}>
      {children}
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ */
/* 背景（グラデ・グリッド床・パーティクル）                             */
/* ------------------------------------------------------------------ */
export const Background: React.FC<{ accent: string; accent2: string }> = ({
  accent,
  accent2,
}) => {
  const frame = useCurrentFrame();
  const x1 = 20 + Math.sin(frame / 50) * 12;
  const y1 = 25 + Math.cos(frame / 60) * 10;
  const x2 = 80 + Math.cos(frame / 45) * 10;
  const y2 = 70 + Math.sin(frame / 55) * 12;
  return (
    <AbsoluteFill style={{ background: C.bg, overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${x1}% ${y1}%, ${accent}40 0%, transparent 38%),
            radial-gradient(circle at ${x2}% ${y2}%, ${accent2}38 0%, transparent 42%),
            radial-gradient(ellipse at 50% 115%, #3b2bff40 0%, transparent 60%)`,
        }}
      />
      {/* グリッド床 */}
      <div
        style={{
          position: "absolute",
          left: "-50%",
          width: "200%",
          bottom: -260,
          height: 760,
          transform: "perspective(520px) rotateX(64deg)",
          transformOrigin: "50% 100%",
          backgroundImage: `linear-gradient(${accent}66 2px, transparent 2px), linear-gradient(90deg, ${accent}55 2px, transparent 2px)`,
          backgroundSize: "90px 90px",
          backgroundPosition: `0px ${(frame * 4) % 90}px`,
          WebkitMaskImage: "linear-gradient(to top, black 15%, transparent 85%)",
          maskImage: "linear-gradient(to top, black 15%, transparent 85%)",
          opacity: 0.45,
        }}
      />
      <Particles color={accent} />
      {/* ビネット */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,.65) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

export const Particles: React.FC<{ color: string; count?: number }> = ({
  color,
  count = 46,
}) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      {new Array(count).fill(0).map((_, i) => {
        const sx = random(`px${i}`) * 1920;
        const speed = 0.6 + random(`ps${i}`) * 2.2;
        const size = 2 + random(`pz${i}`) * 5;
        const y = (((random(`py${i}`) * 1180 - frame * speed) % 1180) + 1180) % 1180 - 50;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(frame / (8 + i % 7) + i));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: sx + Math.sin(frame / 30 + i) * 20,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: i % 3 === 0 ? color : "#fff",
              opacity: 0.55 * tw,
              boxShadow: `0 0 ${size * 3}px ${i % 3 === 0 ? color : "#fff"}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* 回転する放射光（パチンコ風） */
export const Rays: React.FC<{
  color: string;
  size: number;
  speed?: number;
  opacity?: number;
  style?: React.CSSProperties;
}> = ({ color, size, speed = 0.6, opacity = 0.35, style }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        width: size,
        height: size,
        borderRadius: "50%",
        background: `repeating-conic-gradient(from ${frame * speed}deg, ${color} 0deg 7deg, transparent 7deg 18deg)`,
        WebkitMaskImage: "radial-gradient(circle, black 10%, transparent 68%)",
        maskImage: "radial-gradient(circle, black 10%, transparent 68%)",
        opacity,
        ...style,
      }}
    />
  );
};

/* ------------------------------------------------------------------ */
/* ブラウザ枠・スマホ枠                                                 */
/* ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ */
/* 実画面のスクショをカメラで寄る・流す（ScreenCam）                    */
/* - 中の座標はスクショの実ピクセル。children（強調枠など）も同じ座標  */
/* - keys: フレームごとの {注目点 fx,fy（0〜1）, 倍率 zoom（1=幅ぴったり）} */
/* ------------------------------------------------------------------ */
export type CamKey = { f: number; fx: number; fy: number; zoom: number };

export const ScreenCam: React.FC<{
  src: string;
  natW: number;
  natH: number;
  viewW: number;
  viewH: number;
  keys: CamKey[];
  children?: React.ReactNode;
}> = ({ src, natW, natH, viewW, viewH, keys, children }) => {
  const frame = useCurrentFrame();
  const fs = keys.map((k) => k.f);
  const opt = { ...clamp, easing: Easing.inOut(Easing.cubic) };
  const at = (pick: (k: CamKey) => number) =>
    keys.length === 1 ? pick(keys[0]) : interpolate(frame, fs, keys.map(pick), opt);
  const s = (viewW / natW) * at((k) => k.zoom);
  const w = natW * s;
  const h = natH * s;
  const tx = Math.min(0, Math.max(viewW - w, viewW / 2 - at((k) => k.fx) * w));
  const ty = h <= viewH ? 0 : Math.min(0, Math.max(viewH - h, viewH / 2 - at((k) => k.fy) * h));
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        width: natW,
        height: natH,
        transformOrigin: "0 0",
        transform: `translate(${tx}px, ${ty}px) scale(${s})`,
      }}
    >
      <Img src={img(src)} style={{ width: natW, height: natH, display: "block" }} />
      {children}
    </div>
  );
};

/* スクショ上の一点を囲んで光らせる枠（ScreenCam の children 用） */
export const FocusRing: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  at: number;
  color: string;
  radius?: number;
}> = ({ x, y, w, h, at, color, radius = 16 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 10, stiffness: 190, mass: 0.6 } });
  const pulse = 0.55 + 0.45 * Math.sin(Math.max(0, frame - at) / 4);
  if (frame < at) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: x - 10,
        top: y - 10,
        width: w + 20,
        height: h + 20,
        borderRadius: radius,
        border: `6px solid ${color}`,
        boxShadow: `0 0 ${30 * pulse}px ${color}, inset 0 0 ${18 * pulse}px ${color}88`,
        transform: `scale(${1.6 - s * 0.6})`,
        opacity: Math.min(1, s * 1.4),
      }}
    />
  );
};

export const BrowserFrame: React.FC<{
  src?: string;
  width: number;
  height: number;
  url?: string;
  scroll?: number;
  imgScale?: number;
  glow?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({ src, width, height, url, scroll = 0, imgScale = 1, glow, style, children }) => {
  return (
    <div
      style={{
        position: "absolute",
        width,
        height,
        borderRadius: 18,
        overflow: "hidden",
        background: "#0d0f18",
        boxShadow: `0 40px 120px rgba(0,0,0,.65), 0 0 0 2px rgba(255,255,255,.14)${glow ? `, 0 0 70px ${glow}66` : ""}`,
        ...style,
      }}
    >
      <div
        style={{
          height: 46,
          background: "linear-gradient(#262a38, #1b1e29)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 18px",
        }}
      >
        {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
          <div key={c} style={{ width: 14, height: 14, borderRadius: 7, background: c }} />
        ))}
        {url ? (
          <div
            style={{
              marginLeft: 18,
              flex: 1,
              height: 28,
              borderRadius: 14,
              background: "rgba(255,255,255,.09)",
              color: "rgba(255,255,255,.75)",
              fontFamily: FONT_JP,
              fontSize: 16,
              display: "flex",
              alignItems: "center",
              paddingLeft: 16,
            }}
          >
            {url}
          </div>
        ) : null}
      </div>
      <div style={{ position: "relative", height: height - 46, overflow: "hidden" }}>
        {src ? (
          <Img
            src={img(src)}
            style={{
              width: "100%",
              display: "block",
              transform: `translateY(${-scroll}px) scale(${imgScale})`,
              transformOrigin: "50% 0%",
            }}
          />
        ) : null}
        {children}
      </div>
    </div>
  );
};

export const PhoneFrame: React.FC<{
  width: number;
  src?: string;
  style?: React.CSSProperties;
  glow?: string;
  children?: React.ReactNode;
}> = ({ width, src, style, glow, children }) => {
  const h = (width * 844) / 390;
  const bez = width * 0.04;
  return (
    <div
      style={{
        position: "absolute",
        width: width + bez * 2,
        height: h + bez * 2,
        borderRadius: width * 0.15,
        background: "linear-gradient(145deg, #2c2f3a, #0a0b10)",
        padding: bez,
        boxShadow: `0 40px 110px rgba(0,0,0,.7), 0 0 0 2px rgba(255,255,255,.18)${glow ? `, 0 0 70px ${glow}55` : ""}`,
        ...style,
      }}
    >
      <div
        style={{
          position: "relative",
          width,
          height: h,
          borderRadius: width * 0.12,
          overflow: "hidden",
          background: "#000",
        }}
      >
        {src ? (
          <Img src={img(src)} style={{ width: "100%", display: "block" }} />
        ) : null}
        {children}
        <div
          style={{
            position: "absolute",
            top: width * 0.03,
            left: "50%",
            transform: "translateX(-50%)",
            width: width * 0.3,
            height: width * 0.08,
            borderRadius: 100,
            background: "#000",
          }}
        />
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* 見出しラベル（左上の番号）                                           */
/* ------------------------------------------------------------------ */
export const Kicker: React.FC<{ num: string; label: string; color: string }> = ({
  num,
  label,
  color,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 4, fps, config: { damping: 16, stiffness: 140 } });
  const line = interpolate(frame, [8, 24], [0, 120], { ...clamp, easing: Easing.out(Easing.cubic) });
  const op = interpolate(frame, [12, 22], [0, 1], clamp);
  return (
    <div
      style={{
        position: "absolute",
        left: 100,
        top: 54,
        display: "flex",
        alignItems: "center",
        gap: 22,
      }}
    >
      <div
        style={{
          fontFamily: FONT_EN,
          fontSize: 120,
          lineHeight: 1,
          color: "transparent",
          WebkitTextStroke: `3px ${color}`,
          transform: `translateX(${(1 - s) * -160}px)`,
          opacity: s,
          filter: `drop-shadow(0 0 14px ${color}88)`,
        }}
      >
        {num}
      </div>
      <div style={{ width: line, height: 4, background: color, boxShadow: `0 0 12px ${color}` }} />
      <div style={{ opacity: op }}>
        <div
          style={{
            fontFamily: FONT_EN,
            fontSize: 22,
            letterSpacing: 8,
            color: "rgba(255,255,255,.6)",
          }}
        >
          POINT {num} / 09
        </div>
        <div
          style={{
            fontFamily: FONT_EN,
            fontSize: 40,
            letterSpacing: 6,
            color: C.white,
          }}
        >
          {label}
        </div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* 「無料でお試しOK」バッジ（右上に常駐）                               */
/* ------------------------------------------------------------------ */
export const FreeBadge: React.FC<{ appear: number }> = ({ appear }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - appear, fps, config: { damping: 10, stiffness: 160 } });
  const pulse = 1 + Math.sin(frame / 6) * 0.035;
  const pts: string[] = [];
  const n = 16;
  for (let i = 0; i < n * 2; i++) {
    const r = i % 2 === 0 ? 50 : 43;
    const a = (Math.PI * i) / n;
    pts.push(`${50 + r * Math.cos(a)}% ${50 + r * Math.sin(a)}%`);
  }
  return (
    <div
      style={{
        position: "absolute",
        right: 56,
        top: 40,
        width: 210,
        height: 210,
        transform: `scale(${s * pulse}) rotate(${Math.sin(frame / 20) * 6 - 8}deg)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: C.yellow,
          clipPath: `polygon(${pts.join(",")})`,
          transform: `rotate(${frame * 0.5}deg)`,
          filter: "drop-shadow(0 8px 20px rgba(0,0,0,.4))",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: FONT_DISPLAY,
          color: C.ink,
          lineHeight: 1.1,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 46 }}>無料で</div>
        <div style={{ fontSize: 34 }}>お試しOK</div>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* 下部のティッカー                                                     */
/* ------------------------------------------------------------------ */
export const Ticker: React.FC<{ color: string }> = ({ color }) => {
  const frame = useCurrentFrame();
  const unit =
    "ENTERTAINMENT × AI ◆ 無料でお試しできます！お気軽に。 ◆ ご用命はアイアンドエフへ ◆ BANTEX AI SERVICE ◆ ";
  const text = unit.repeat(3);
  const shift = (frame * 0.12) % 50;
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 62,
        background: "rgba(5,6,12,.88)",
        borderTop: `3px solid ${color}`,
        boxShadow: `0 -6px 30px ${color}55`,
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          whiteSpace: "nowrap",
          transform: `translateX(-${shift}%)`,
          fontFamily: FONT_JP,
          fontWeight: 900,
          fontSize: 28,
          letterSpacing: 3,
          color: C.white,
        }}
      >
        <span>{text}</span>
        <span>{text}</span>
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* シーン切替のワイプ                                                   */
/* ------------------------------------------------------------------ */
export const Wipe: React.FC<{ at: number; color: string; color2: string }> = ({
  at,
  color,
  color2,
}) => {
  const frame = useCurrentFrame();
  const d = frame - at;
  if (d < -11 || d > 12) return null;
  const e = { ...clamp, easing: Easing.inOut(Easing.cubic) };
  const x1 = interpolate(d, [-10, -1, 1, 11], [-165, -18, -18, 135], e);
  const x2 = interpolate(d, [-11, -2, 2, 12], [-180, -18, -18, 122], e);
  const slices = new Array(7).fill(0).map((_, i) => ({
    top: random(`wt${at}-${i}`) * 100,
    h: 1 + random(`wh${at}-${i}`) * 5,
    off: (random(`wo${at}-${i}-${d}`) - 0.5) * 300,
  }));
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          top: "-20%",
          height: "140%",
          width: "140%",
          left: `${x2}%`,
          background: color2,
          transform: "skewX(-18deg)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: "-20%",
          height: "140%",
          width: "135%",
          left: `${x1}%`,
          background: color,
          transform: "skewX(-18deg)",
          boxShadow: `0 0 80px ${color}`,
        }}
      />
      {Math.abs(d) < 6
        ? slices.map((s, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                left: s.off,
                width: "100%",
                top: `${s.top}%`,
                height: `${s.h}%`,
                background: i % 2 ? C.cyan : C.magenta,
                opacity: 0.55,
                mixBlendMode: "screen",
              }}
            />
          ))
        : null}
    </AbsoluteFill>
  );
};

/* 蛍光ペン風ハイライト */
export const Highlight: React.FC<{
  delay: number;
  color: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ delay, color, children, style }) => {
  const frame = useCurrentFrame();
  const w = interpolate(frame, [delay, delay + 12], [0, 1], {
    ...clamp,
    easing: Easing.out(Easing.cubic),
  });
  return (
    <div style={{ position: "relative", display: "inline-block", ...style }}>
      <div
        style={{
          position: "absolute",
          left: -12,
          right: -12,
          bottom: "6%",
          height: "42%",
          background: color,
          transformOrigin: "0% 50%",
          transform: `scaleX(${w}) skewX(-12deg)`,
          borderRadius: 6,
        }}
      />
      <div style={{ position: "relative" }}>{children}</div>
    </div>
  );
};
