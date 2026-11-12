import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  random,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  BrowserFrame,
  FocusRing,
  Highlight,
  KText,
  Kicker,
  PhoneFrame,
  Pop,
  Rays,
  ScreenCam,
  Shake,
  Slam,
  clamp,
  gradientText,
  img,
} from "./components";
import { C, FONT_DISPLAY, FONT_EN, FONT_JP } from "./theme";

const useF = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const spr = (delay: number, config = { damping: 14, stiffness: 140, mass: 0.8 }) =>
    spring({ frame: frame - delay, fps, config });
  return { f: frame, spr };
};

const abs = (style: React.CSSProperties): React.CSSProperties => ({
  position: "absolute",
  ...style,
});

/* ================================================================== */
/* INTRO：無料でお試しできます！お気軽に。                             */
/* ================================================================== */
export const Intro: React.FC = () => {
  const { f, spr } = useF();
  const lineW = interpolate(f, [0, 12], [0, 1920], { ...clamp, easing: Easing.out(Easing.cubic) });
  const lineOp = interpolate(f, [10, 20], [1, 0], clamp);
  const flash = interpolate(f, [12, 14, 24], [0, 0.8, 0], clamp);
  const top = spr(6);
  const sub = interpolate(f, [96, 112], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <Rays color={C.yellow} size={2200} opacity={0.18} style={{ left: -140, top: -560 }} />
      <Shake impacts={[16, 60]} amp={22}>
        <div
          style={abs({
            top: 150,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: FONT_EN,
            fontSize: 40,
            letterSpacing: 16,
            color: "rgba(255,255,255,.85)",
            opacity: top,
            transform: `translateY(${(1 - top) * -40}px)`,
          })}
        >
          i&amp;F GROUP × BANTEX
        </div>
        <div style={abs({ top: 230, left: 0, right: 0, display: "flex", justifyContent: "center" })}>
          <Slam delay={16} fromScale={3}>
            <div
              style={{
                fontFamily: FONT_DISPLAY,
                fontSize: 250,
                lineHeight: 1.1,
                ...gradientText(C.yellow, "#FF8A00", 180),
                filter: `drop-shadow(0 0 40px ${C.yellow}88)`,
              }}
            >
              無料で
            </div>
          </Slam>
        </div>
        <div style={abs({ top: 525, left: 0, right: 0 })}>
          <KText text="お試しできます！" delay={30} stagger={2.5} size={150} align="center" />
        </div>
        <div style={abs({ top: 740, left: 0, right: 0, display: "flex", justifyContent: "center" })}>
          <Pop delay={60} rotate={-20}>
            <div
              style={{
                background: C.magenta,
                color: C.white,
                fontFamily: FONT_DISPLAY,
                fontSize: 92,
                padding: "6px 60px 14px",
                borderRadius: 100,
                transform: "rotate(-3deg)",
                boxShadow: `0 0 60px ${C.magenta}aa`,
              }}
            >
              お気軽に。
            </div>
          </Pop>
        </div>
        <div
          style={abs({
            top: 940,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: FONT_EN,
            fontSize: 34,
            letterSpacing: 22,
            color: C.yellow,
            opacity: sub,
          })}
        >
          ENTERTAINMENT × AI
        </div>
      </Shake>
      <div
        style={abs({
          top: 538,
          left: 960 - lineW / 2,
          width: lineW,
          height: 4,
          background: C.white,
          boxShadow: `0 0 30px ${C.cyan}, 0 0 60px ${C.cyan}`,
          opacity: lineOp,
        })}
      />
      <AbsoluteFill style={{ background: C.white, opacity: flash }} />
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 01：10分であなたが主人公の映画をYouTubeで                            */
/* ================================================================== */
const STRIP = ["demo1.jpg", "demo4.jpg", "demo2.jpg", "demo7.jpg", "demo3.jpg", "demo6.jpg", "demo9.jpg", "demo8.jpg", "demo5.jpg"];

const FilmStrip: React.FC<{ top: number }> = ({ top }) => {
  const { f } = useF();
  const fw = 300;
  const items = [...STRIP, ...STRIP];
  const x = -((f * 3) % (fw * STRIP.length));
  return (
    <div
      style={abs({
        top,
        left: -100,
        width: 2400,
        height: 210,
        transform: "rotate(-4deg)",
        background: "#0b0b0f",
        opacity: 0.75,
        overflow: "hidden",
        boxShadow: "0 20px 60px rgba(0,0,0,.6)",
      })}
    >
      {[0, 186].map((t) => (
        <div
          key={t}
          style={abs({
            top: t + 4,
            left: x % 40,
            width: 2600,
            height: 16,
            backgroundImage: "repeating-linear-gradient(90deg, rgba(255,255,255,.75) 0 18px, transparent 18px 40px)",
          })}
        />
      ))}
      <div style={abs({ top: 28, left: x, display: "flex", gap: 12 })}>
        {items.map((s, i) => (
          <Img
            key={i}
            src={img(s)}
            style={{ width: fw - 12, height: 154, objectFit: "cover", filter: "saturate(1.2)" }}
          />
        ))}
      </div>
    </div>
  );
};

/* 実画面の注記（ブラウザ枠の左下に置く） */
const ScreenNote: React.FC<{ text: string; at: number }> = ({ text, at }) => {
  const { f } = useF();
  return (
    <div
      style={abs({
        left: 14,
        bottom: 14,
        padding: "6px 14px",
        borderRadius: 10,
        background: "rgba(6,7,15,.78)",
        color: "rgba(255,255,255,.9)",
        fontFamily: FONT_JP,
        fontWeight: 700,
        fontSize: 18,
        opacity: interpolate(f, [at, at + 8], [0, 1], clamp),
      })}
    >
      {text}
    </div>
  );
};

// 映画ギャラリーのスクショ（1920x1200）上の位置
const CINEMA = { w: 1920, h: 1200, done: [866, 494, 62, 40], thumb: [170, 573, 521, 292], yt: [711, 790, 209, 53] } as const;

export const S1Movie: React.FC = () => {
  const { f, spr } = useF();
  const pIn = spr(4, { damping: 16, stiffness: 110, mass: 0.9 });
  const count = Math.round(interpolate(f, [10, 34], [0, 10], { ...clamp, easing: Easing.out(Easing.cubic) }));
  const FW = 860;
  const FH = 520;
  return (
    <AbsoluteFill>
      <FilmStrip top={790} />
      <Kicker num="01" label="AI MOVIE" color={C.magenta} />
      <Shake impacts={[12]} amp={14}>
        <div style={abs({ left: 110, top: 230 })}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 10 }}>
            <Slam delay={10} fromScale={2.6}>
              <div
                style={{
                  fontFamily: FONT_EN,
                  fontSize: 290,
                  lineHeight: 0.95,
                  minWidth: 260,
                  ...gradientText(C.magenta, C.yellow, 160),
                  filter: `drop-shadow(0 0 30px ${C.magenta}99)`,
                }}
              >
                {count}
              </div>
            </Slam>
            <KText text="分で" delay={20} size={130} style={{ marginBottom: 18 }} />
          </div>
          <KText text="あなたが主人公の" delay={34} stagger={1.6} size={84} style={{ marginTop: 10 }} />
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 14 }}>
            <KText text="映画を" delay={48} size={84} />
            <Pop delay={58} rotate={-15}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  background: C.red,
                  padding: "10px 26px 14px 20px",
                  borderRadius: 22,
                  boxShadow: `0 0 40px ${C.red}99`,
                }}
              >
                <div
                  style={{
                    width: 0,
                    height: 0,
                    borderTop: "22px solid transparent",
                    borderBottom: "22px solid transparent",
                    borderLeft: "36px solid white",
                    marginLeft: 8,
                  }}
                />
                <div style={{ fontFamily: FONT_EN, fontSize: 70, color: "#fff", lineHeight: 1 }}>YouTube</div>
              </div>
            </Pop>
            <KText text="で。" delay={66} size={84} />
          </div>
        </div>
      </Shake>
      {/* 実画面：BANTEX AI CINEMA の完成一覧 */}
      <BrowserFrame
        width={FW}
        height={FH}
        url="BANTEX AI CINEMA ｜ 完成一覧"
        glow={C.magenta}
        style={{
          left: 960,
          top: 200,
          opacity: interpolate(f, [4, 10], [0, 1], clamp),
          transform: `perspective(1400px) translateX(${(1 - pIn) * 800}px) rotateY(${-6 + (1 - pIn) * -30}deg)`,
        }}
      >
        <ScreenCam
          src="cinema_gallery.jpg"
          natW={CINEMA.w}
          natH={CINEMA.h}
          viewW={FW}
          viewH={FH - 46}
          keys={[
            { f: 0, fx: 0.3, fy: 0.3, zoom: 1.7 },
            { f: 42, fx: 0.3, fy: 0.32, zoom: 1.75 },
            { f: 84, fx: 0.224, fy: 0.6, zoom: 3.0 },
            { f: 106, fx: 0.24, fy: 0.6, zoom: 3.05 },
            { f: 126, fx: 0.425, fy: 0.66, zoom: 2.4 },
          ]}
        >
          <FocusRing x={CINEMA.done[0]} y={CINEMA.done[1]} w={CINEMA.done[2]} h={CINEMA.done[3]} at={30} color={C.yellow} radius={24} />
          <FocusRing x={CINEMA.yt[0]} y={CINEMA.yt[1]} w={CINEMA.yt[2]} h={CINEMA.yt[3]} at={120} color={C.red} radius={14} />
        </ScreenCam>
        <ScreenNote text="※実際のサービス画面（QRはぼかし加工）" at={14} />
      </BrowserFrame>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 02：貴社のHPをAIが採点                                               */
/* ================================================================== */
// SITE CHECK 50社比較のスクショ（1600x3000、企業名は匿名化済み）上の位置
const SITECHECK = { w: 1600, h: 3000, scores: [[400, 1550], [705, 1550]] } as const;

export const S2Score: React.FC = () => {
  const { f, spr } = useF();
  const bIn = spr(4, { damping: 15, stiffness: 110, mass: 0.9 });
  const FW = 1000;
  const FH = 680;
  const viewH = FH - 46;
  const scanY = interpolate(f, [48, 112], [-60, viewH + 60], clamp);
  const scanOn = interpolate(f, [44, 50, 108, 116], [0, 1, 1, 0], clamp);
  return (
    <AbsoluteFill>
      <Kicker num="02" label="AI SCORE" color={C.cyan} />
      {/* 実画面：SITE CHECK 50社のサイト比較 */}
      <BrowserFrame
        width={FW}
        height={FH}
        url="SITE CHECK ｜ 50社のサイト比較"
        glow={C.cyan}
        style={{
          left: 830,
          top: 175,
          transform: `perspective(1500px) translateY(${(1 - bIn) * 600}px) rotateX(${(1 - bIn) * 30}deg) rotateY(-6deg)`,
        }}
      >
        <ScreenCam
          src="sitecheck_gallery.jpg"
          natW={SITECHECK.w}
          natH={SITECHECK.h}
          viewW={FW}
          viewH={viewH}
          keys={[
            { f: 0, fx: 0.5, fy: 0.08, zoom: 1.3 },
            { f: 46, fx: 0.5, fy: 0.08, zoom: 1.3 },
            { f: 112, fx: 0.5, fy: 0.5, zoom: 1.3 },
            { f: 136, fx: 0.309, fy: 0.546, zoom: 2.3 },
          ]}
        >
          {SITECHECK.scores.map(([x, y], i) => (
            <FocusRing key={i} x={x} y={y} w={75} h={66} at={128 + i * 6} color={C.cyan} radius={18} />
          ))}
        </ScreenCam>
        {/* スキャン線（1回だけ走る） */}
        <div
          style={abs({
            left: 0,
            right: 0,
            top: scanY - 140,
            height: 140,
            opacity: scanOn,
            background: `linear-gradient(transparent, ${C.cyan}44)`,
          })}
        />
        <div
          style={abs({
            left: 0,
            right: 0,
            top: scanY,
            height: 5,
            opacity: scanOn,
            background: C.cyan,
            boxShadow: `0 0 30px ${C.cyan}, 0 0 60px ${C.cyan}`,
          })}
        />
        <AbsoluteFill
          style={{
            opacity: scanOn * 0.8,
            backgroundImage: `linear-gradient(${C.cyan}22 1px, transparent 1px), linear-gradient(90deg, ${C.cyan}22 1px, transparent 1px)`,
            backgroundSize: "60px 60px",
          }}
        />
        <ScreenNote text="※実際のサービス画面（企業名は匿名化）。点数は当社基準による参考値です" at={14} />
      </BrowserFrame>
      {/* 見出し */}
      <Shake impacts={[30]} amp={14}>
        <div style={abs({ left: 110, top: 320 })}>
          <KText text="貴社のHPを" delay={8} size={92} />
          <div style={{ display: "flex", alignItems: "flex-end", marginTop: 6 }}>
            <KText text="AIが" delay={20} size={120} font={FONT_DISPLAY} />
            <Slam delay={30} fromScale={2.8} rotate={-10}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 168,
                  lineHeight: 1.1,
                  color: C.cyan,
                  textShadow: `0 0 40px ${C.cyan}, 0 0 8px ${C.cyan}`,
                }}
              >
                採点
              </div>
            </Slam>
          </div>
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 03：エンタメ×AIのコンセプト会社                                      */
/* ================================================================== */
export const S3Concept: React.FC = () => {
  const { f, spr } = useF();
  const zoom = interpolate(f, [0, 160], [1.28, 1.04]);
  const xS = spr(24, { damping: 8, stiffness: 120, mass: 0.8 });
  const under = interpolate(f, [62, 80], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const glitch = f > 8 && f < 22 && f % 3 !== 0;
  const topOp = interpolate(f, [70, 86], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ overflow: "hidden" }}>
        <Img
          src={img("bantex_hero.jpg")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${zoom}) translateX(${glitch ? (random(`g${f}`) - 0.5) * 40 : 0}px)`,
            filter: glitch ? "hue-rotate(80deg) saturate(2) blur(2px)" : "saturate(1.15) blur(3px)",
          }}
        />
        <AbsoluteFill
          style={{
            background: "linear-gradient(90deg, rgba(6,7,15,.9), rgba(6,7,15,.62) 50%, rgba(6,7,15,.88))",
          }}
        />
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at 30% 50%, ${C.magenta}44, transparent 45%), radial-gradient(circle at 75% 50%, ${C.cyan}44, transparent 45%)`,
          }}
        />
      </AbsoluteFill>
      <Kicker num="03" label="CONCEPT" color={C.magenta} />
      <Shake impacts={[10, 22, 34]} amp={20}>
        <div
          style={abs({
            top: 300,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 30,
          })}
        >
          <Slam delay={10} fromScale={2.2}>
            <div
              style={{
                fontFamily: FONT_DISPLAY,
                fontSize: 200,
                color: C.magenta,
                textShadow: `0 0 50px ${C.magenta}, 0 0 10px ${C.magenta}`,
                lineHeight: 1.1,
              }}
            >
              エンタメ
            </div>
          </Slam>
          <div
            style={{
              fontFamily: FONT_EN,
              fontSize: 190,
              color: "#fff",
              transform: `scale(${xS}) rotate(${(1 - xS) * 360}deg)`,
              textShadow: "0 0 30px rgba(255,255,255,.8)",
              lineHeight: 1,
            }}
          >
            ×
          </div>
          <Slam delay={34} fromScale={2.6}>
            <div
              style={{
                fontFamily: FONT_EN,
                fontSize: 250,
                color: C.cyan,
                textShadow: `0 0 50px ${C.cyan}, 0 0 10px ${C.cyan}`,
                lineHeight: 1,
              }}
            >
              AI
            </div>
          </Slam>
        </div>
        <div style={abs({ top: 600, left: 0, right: 0, display: "flex", justifyContent: "center" })}>
          <div style={{ position: "relative" }}>
            <KText text="のコンセプト会社" delay={48} stagger={2} size={112} align="center" />
            <div
              style={abs({
                left: 0,
                right: 0,
                bottom: -18,
                height: 10,
                borderRadius: 5,
                background: `linear-gradient(90deg, ${C.magenta}, ${C.yellow}, ${C.cyan})`,
                transformOrigin: "0% 50%",
                transform: `scaleX(${under})`,
                boxShadow: `0 0 20px ${C.magenta}`,
              })}
            />
          </div>
        </div>
        <div
          style={abs({
            top: 830,
            left: 0,
            right: 0,
            textAlign: "center",
            fontFamily: FONT_EN,
            fontSize: 36,
            letterSpacing: 18,
            color: "rgba(255,255,255,.85)",
            opacity: topOp,
          })}
        >
          ENTERTAINMENT × AI CONCEPT COMPANY
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 04：パチンコ開発で販売台数日本一のプロデューサーが伴走                */
/* ================================================================== */
const REEL = ["777", "BAR", "★★★", "No.1", "777", "BAR", "★★★", "No.1", "777", "BAR", "★★★", "No.1", "日本一"];

const SlotReel: React.FC<{ start: number; land: number }> = ({ start, land }) => {
  const { f } = useF();
  const H = 200;
  const p = interpolate(f, [start, land], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const bounce = f >= land ? Math.sin((f - land) * 0.9) * Math.exp(-(f - land) * 0.25) * 18 : 0;
  const idx = p * (REEL.length - 1);
  const speed = f < land ? 1 - p : 0;
  const landed = f >= land;
  const shine = interpolate(f, [land + 2, land + 18], [-120, 220], clamp);
  return (
    <div
      style={{
        position: "relative",
        width: 600,
        height: H + 24,
        borderRadius: 26,
        padding: 12,
        background: `linear-gradient(135deg, ${C.gold}, #8a5a00, ${C.gold})`,
        boxShadow: landed ? `0 0 ${60 + Math.sin(f / 3) * 20}px ${C.gold}` : "0 10px 40px rgba(0,0,0,.6)",
      }}
    >
      <div
        style={{
          position: "relative",
          height: H,
          borderRadius: 16,
          overflow: "hidden",
          background: "linear-gradient(#000, #1a1306 50%, #000)",
        }}
      >
        <div
          style={{
            transform: `translateY(${-idx * H + bounce}px)`,
            filter: speed > 0.15 ? `blur(${speed * 6}px)` : undefined,
          }}
        >
          {REEL.map((t, i) => (
            <div
              key={i}
              style={{
                height: H,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: t === "日本一" ? FONT_DISPLAY : FONT_EN,
                fontSize: t === "日本一" ? 160 : 140,
                lineHeight: 1,
                ...(t === "日本一"
                  ? gradientText("#FFF6C8", C.gold, 180)
                  : { color: i % 2 ? C.magenta : C.red }),
              }}
            >
              {t}
            </div>
          ))}
        </div>
        <div
          style={abs({
            top: -40,
            bottom: -40,
            width: 80,
            left: `${shine}%`,
            background: "linear-gradient(90deg, transparent, rgba(255,255,255,.75), transparent)",
            transform: "skewX(-20deg)",
          })}
        />
        <div
          style={abs({
            inset: 0,
            background: "linear-gradient(rgba(0,0,0,.65), transparent 25%, transparent 75%, rgba(0,0,0,.65))",
          })}
        />
      </div>
    </div>
  );
};

export const S4Producer: React.FC = () => {
  const { f, spr } = useF();
  const cIn = spr(4, { damping: 13, stiffness: 120, mass: 0.9 });
  const land = 62;
  const subOp = interpolate(f, [96, 110], [0, 1], clamp);
  return (
    <AbsoluteFill>
      <Kicker num="04" label="PRODUCER" color={C.gold} />
      {/* 人物 */}
      <div style={abs({ left: 140, top: 210, width: 640, height: 640 })}>
        <Rays color={C.gold} size={1300} speed={1.2} opacity={0.4} style={{ left: -330, top: -330 }} />
        <div
          style={abs({
            inset: 0,
            borderRadius: "50%",
            background: `conic-gradient(from ${f * 4}deg, ${C.gold}, ${C.magenta}, ${C.cyan}, ${C.gold})`,
            transform: `scale(${cIn})`,
            boxShadow: `0 0 80px ${C.gold}88`,
          })}
        />
        <div
          style={abs({
            inset: 18,
            borderRadius: "50%",
            overflow: "hidden",
            transform: `scale(${cIn})`,
            background: "#fff",
          })}
        >
          <Img src={img("producer.png")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        {new Array(10).fill(0).map((_, i) => {
          const a = (i / 10) * Math.PI * 2 + f / 40;
          const r = 360 + Math.sin(f / 7 + i) * 20;
          const tw = Math.abs(Math.sin(f / 5 + i * 1.7));
          return (
            <div
              key={i}
              style={abs({
                left: 320 + Math.cos(a) * r - 16,
                top: 320 + Math.sin(a) * r - 16,
                width: 32,
                height: 32,
                background: i % 2 ? C.gold : "#fff",
                clipPath: "polygon(50% 0, 60% 40%, 100% 50%, 60% 60%, 50% 100%, 40% 60%, 0 50%, 40% 40%)",
                transform: `scale(${tw * cIn})`,
              })}
            />
          );
        })}
      </div>
      {/* テキスト */}
      <Shake impacts={[land]} amp={20}>
        <div style={abs({ left: 940, top: 200 })}>
          <KText text="パチンコ開発で" delay={10} size={80} />
          <KText text="販売台数" delay={22} size={100} style={{ marginTop: 6 }} />
          <div style={{ marginTop: 12, transform: `scale(${interpolate(spr(16), [0, 1], [0.6, 1])})`, transformOrigin: "0% 50%", opacity: interpolate(f, [16, 22], [0, 1], clamp) }}>
            <SlotReel start={20} land={land} />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end", marginTop: 22 }}>
            <KText text="プロデューサーが" delay={70} stagger={1.5} size={74} />
            <Slam delay={88} fromScale={2.2}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 110,
                  lineHeight: 1.1,
                  ...gradientText("#FFF6C8", C.gold, 180),
                  filter: `drop-shadow(0 0 20px ${C.gold})`,
                }}
              >
                伴走
              </div>
            </Slam>
          </div>
          <div
            style={{
              marginTop: 18,
              display: "inline-block",
              padding: "8px 22px",
              border: `2px solid ${C.gold}`,
              borderRadius: 40,
              fontFamily: FONT_JP,
              fontWeight: 900,
              fontSize: 30,
              color: C.gold,
              opacity: subOp,
            }}
          >
            パチンコ遊技機 20機種・200万台プロデュース
          </div>
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 05：他社より早く安い。そのわけは社員＝AI                              */
/* ================================================================== */
const SpeedLines: React.FC<{ color: string; opacity: number }> = ({ color, opacity }) => {
  const { f } = useF();
  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden" }}>
      {new Array(36).fill(0).map((_, i) => {
        const y = random(`sl${i}`) * 1080;
        const len = 200 + random(`sll${i}`) * 700;
        const sp = 40 + random(`sls${i}`) * 60;
        const x = 1920 - (((f * sp + random(`slx${i}`) * 3000) % 3200));
        return (
          <div
            key={i}
            style={abs({
              left: x,
              top: y,
              width: len,
              height: 2 + (i % 3) * 2,
              background: `linear-gradient(90deg, ${i % 4 === 0 ? color : "#fff"}, transparent)`,
              opacity: 0.5,
            })}
          />
        );
      })}
    </AbsoluteFill>
  );
};

export const S5Speed: React.FC = () => {
  const { f, spr } = useF();
  const outA = interpolate(f, [64, 74], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const bIn = spr(86, { damping: 15, stiffness: 110, mass: 0.9 });
  return (
    <AbsoluteFill>
      <SpeedLines color={C.yellow} opacity={interpolate(f, [10, 20, 64, 74], [0, 1, 1, 0.25], clamp)} />
      <Kicker num="05" label="SPEED & COST" color={C.yellow} />
      {/* フェーズA：早い！安い！ */}
      <Shake impacts={[18, 34]} amp={24}>
        <div
          style={abs({
            inset: 0,
            opacity: 1 - outA,
            transform: `translateY(${outA * -200}px) scale(${1 - outA * 0.3})`,
          })}
        >
          <div style={abs({ top: 230, left: 0, right: 0 })}>
            <KText text="他社より" delay={6} size={100} align="center" />
          </div>
          <div style={abs({ top: 400, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 90 })}>
            <Slam delay={18} fromScale={3} rotate={-12}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 240,
                  lineHeight: 1.1,
                  color: C.yellow,
                  transform: "skewX(-10deg)",
                  textShadow: `0 0 50px ${C.yellow}, 12px 12px 0 ${C.magenta}`,
                }}
              >
                早い！
              </div>
            </Slam>
            <Slam delay={34} fromScale={3} rotate={12}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 240,
                  lineHeight: 1.1,
                  color: C.magenta,
                  transform: "skewX(-10deg)",
                  textShadow: `0 0 50px ${C.magenta}, 12px 12px 0 ${C.yellow}`,
                }}
              >
                安い！
              </div>
            </Slam>
          </div>
        </div>
      </Shake>
      {/* フェーズB：そのわけは 社員＝AI */}
      {f >= 70 ? (
        <>
          <BrowserFrame
            src="koala.jpg"
            width={800}
            height={500}
            url="koala.bantex.jp"
            glow={C.cyan}
            style={{
              left: 1040,
              top: 250,
              transform: `perspective(1400px) translateX(${(1 - bIn) * 900}px) rotateY(-20deg)`,
            }}
          />
          <Shake impacts={[98, 108]} amp={20}>
            <div style={abs({ left: 110, top: 240 })}>
              <KText text="そのわけは…" delay={74} size={80} color="rgba(255,255,255,.9)" />
              <div style={{ display: "flex", alignItems: "center", marginTop: 20, gap: 10 }}>
                <Slam delay={92} fromScale={2.4}>
                  <div style={{ fontFamily: FONT_DISPLAY, fontSize: 190, color: "#fff", lineHeight: 1.1 }}>社員</div>
                </Slam>
                <Slam delay={100} fromScale={2.4}>
                  <div style={{ fontFamily: FONT_DISPLAY, fontSize: 170, color: C.yellow, lineHeight: 1.1, margin: "0 10px" }}>＝</div>
                </Slam>
                <Slam delay={108} fromScale={3}>
                  <div
                    style={{
                      fontFamily: FONT_EN,
                      fontSize: 270,
                      lineHeight: 1,
                      color: C.cyan,
                      textShadow: `0 0 50px ${C.cyan}, 0 0 10px ${C.cyan}, ${f % 4 < 2 && f < 120 ? 8 : 0}px 0 0 ${C.magenta}`,
                    }}
                  >
                    AI
                  </div>
                </Slam>
              </div>
              <div
                style={{
                  marginTop: 26,
                  display: "inline-block",
                  padding: "10px 26px",
                  borderRadius: 40,
                  background: "rgba(0,229,255,.12)",
                  border: `2px solid ${C.cyan}`,
                  fontFamily: FONT_JP,
                  fontWeight: 900,
                  fontSize: 32,
                  color: "#fff",
                  opacity: interpolate(f, [120, 132], [0, 1], clamp),
                }}
              >
                人間2名＋AI社員7名で運営中
              </div>
            </div>
          </Shake>
        </>
      ) : null}
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 06：シニアも使える LINEでシステム構築 だから操作は簡単                */
/* ================================================================== */
const MSGS: { me: boolean; text: string; at: number }[] = [
  { me: true, text: "明日10時に予約したい", at: 26 },
  { me: false, text: "承知しました。明日10:00で予約を登録しました", at: 48 },
  { me: true, text: "ありがとう！", at: 74 },
  { me: false, text: "どういたしまして。当日お待ちしております", at: 96 },
];

const LineChat: React.FC = () => {
  const { f, spr } = useF();
  return (
    <AbsoluteFill style={{ background: "#8fabd6" }}>
      <div
        style={{
          height: 120,
          background: C.line,
          display: "flex",
          alignItems: "flex-end",
          padding: "0 22px 16px",
          color: "#fff",
          fontFamily: FONT_JP,
          fontWeight: 900,
          fontSize: 26,
          gap: 12,
        }}
      >
        <div style={{ fontSize: 30 }}>‹</div>
        AIアシスタント
      </div>
      <div style={{ padding: "22px 16px", display: "flex", flexDirection: "column", gap: 18 }}>
        {MSGS.map((m, i) => {
          const s = spr(m.at, { damping: 12, stiffness: 200, mass: 0.6 });
          const typing = !m.me && f >= m.at - 14 && f < m.at;
          if (f < m.at - 14) return null;
          return (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: m.me ? "flex-end" : "flex-start",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              {!m.me ? (
                <div
                  style={{
                    width: 46,
                    height: 46,
                    borderRadius: 23,
                    background: C.line,
                    color: "#fff",
                    fontFamily: FONT_EN,
                    fontSize: 20,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  AI
                </div>
              ) : null}
              <div
                style={{
                  maxWidth: 260,
                  padding: "12px 16px",
                  borderRadius: 22,
                  background: m.me ? "#7de36f" : "#fff",
                  fontFamily: FONT_JP,
                  fontWeight: 700,
                  fontSize: 25,
                  lineHeight: 1.35,
                  color: "#111",
                  transform: typing ? undefined : `scale(${s})`,
                  transformOrigin: m.me ? "100% 0%" : "0% 0%",
                  boxShadow: "0 2px 6px rgba(0,0,0,.12)",
                }}
              >
                {typing ? (
                  <div style={{ display: "flex", gap: 6, padding: "6px 4px" }}>
                    {[0, 1, 2].map((d) => (
                      <div
                        key={d}
                        style={{
                          width: 10,
                          height: 10,
                          borderRadius: 5,
                          background: "#999",
                          transform: `translateY(${Math.sin((f + d * 4) / 2.5) * 4}px)`,
                        }}
                      />
                    ))}
                  </div>
                ) : (
                  m.text
                )}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const S6Line: React.FC = () => {
  const { spr } = useF();
  const p1 = spr(6, { damping: 14, stiffness: 110, mass: 0.9 });
  const p2 = spr(14, { damping: 14, stiffness: 110, mass: 0.9 });
  return (
    <AbsoluteFill>
      <Kicker num="06" label="LINE SYSTEM" color={C.line} />
      <PhoneFrame
        width={340}
        src="kokodash_m.jpg"
        glow={C.line}
        style={{
          left: 1000,
          top: 170,
          transform: `translateY(${(1 - p1) * 900}px) rotate(-6deg)`,
        }}
      />
      <PhoneFrame
        width={380}
        glow={C.line}
        style={{
          left: 1400,
          top: 120,
          transform: `translateY(${(1 - p2) * 900}px) rotate(4deg)`,
        }}
      >
        <LineChat />
      </PhoneFrame>
      <Shake impacts={[30, 112]} amp={14}>
        <div style={abs({ left: 110, top: 230 })}>
          <Highlight delay={14} color={`${C.yellow}cc`}>
            <KText text="シニアも使える" delay={6} size={84} />
          </Highlight>
          <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 26 }}>
            <Slam delay={30} fromScale={2.4} rotate={-10}>
              <div
                style={{
                  background: C.line,
                  color: "#fff",
                  fontFamily: FONT_EN,
                  fontSize: 110,
                  lineHeight: 1,
                  padding: "14px 34px 18px",
                  borderRadius: 34,
                  boxShadow: `0 0 50px ${C.line}aa`,
                }}
              >
                LINE
              </div>
            </Slam>
            <KText text="で" delay={38} size={100} />
          </div>
          <KText text="システム構築" delay={44} stagger={2} size={120} style={{ marginTop: 18 }} />
          <KText text="だから操作は" delay={84} size={68} style={{ marginTop: 34 }} color="rgba(255,255,255,.9)" />
          <Slam delay={112} fromScale={2.6} rotate={-8}>
            <div
              style={{
                fontFamily: FONT_DISPLAY,
                fontSize: 140,
                lineHeight: 1.15,
                color: C.yellow,
                textShadow: `0 0 40px ${C.yellow}aa, 8px 8px 0 ${C.line}`,
              }}
            >
              カンタン！
            </div>
          </Slam>
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 07：AIを始めたいけど…必見！丸一日あなたの仕事場に伺いAI化をご提示     */
/* ================================================================== */
export const S7Visit: React.FC = () => {
  const { f, spr } = useF();
  const outA = interpolate(f, [66, 78], [0, 1], { ...clamp, easing: Easing.in(Easing.cubic) });
  const bIn = spr(4, { damping: 15, stiffness: 110, mass: 0.9 });
  const clockIn = spr(78, { damping: 13, stiffness: 120, mass: 0.8 });
  const arc = interpolate(f, [82, 130], [0, 1], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const R = 190;
  const circ = 2 * Math.PI * R;
  const marks = [
    { x: 300, y: 520, d: 20 },
    { x: 1620, y: 640, d: 26 },
    { x: 220, y: 780, d: 32 },
    { x: 1700, y: 420, d: 38 },
  ];
  return (
    <AbsoluteFill>
      <Kicker num="07" label="ON-SITE SUPPORT" color={C.cyan} />
      {/* フェーズA */}
      <AbsoluteFill style={{ opacity: 1 - outA, transform: `scale(${1 - outA * 0.2})` }}>
        <BrowserFrame
          src="jigyo.jpg"
          width={1000}
          height={560}
          url="jigyo.bantex.jp"
          glow={C.cyan}
          scroll={interpolate(f, [10, 70], [70, 70], clamp)}
          style={{
            left: 460,
            top: 430,
            transform: `perspective(1400px) translateY(${(1 - bIn) * 700}px) rotateX(14deg)`,
          }}
        />
        {marks.map((m, i) => {
          const s = spr(m.d, { damping: 8, stiffness: 160, mass: 0.6 });
          return (
            <div
              key={i}
              style={abs({
                left: m.x,
                top: m.y + Math.sin(f / 8 + i) * 14,
                fontFamily: FONT_DISPLAY,
                fontSize: 140,
                color: i % 2 ? C.yellow : C.cyan,
                transform: `scale(${s}) rotate(${(i % 2 ? 1 : -1) * 14}deg)`,
                textShadow: `0 0 30px ${i % 2 ? C.yellow : C.cyan}`,
              })}
            >
              ?
            </div>
          );
        })}
        <div style={abs({ left: 0, right: 0, top: 170 })}>
          <KText text="AIを始めたいけど、" delay={6} stagger={1.5} size={84} align="center" />
          <KText text="何をしたらいいか分からない方" delay={18} stagger={1.3} size={84} align="center" style={{ marginTop: 8 }} />
        </div>
        <Pop delay={40} rotate={-40} style={abs({ left: 1540, top: 150 })}>
          <div
            style={{
              width: 250,
              height: 250,
              borderRadius: "50%",
              background: C.red,
              border: "8px solid #fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: FONT_DISPLAY,
              fontSize: 96,
              color: "#fff",
              transform: "rotate(-12deg)",
              boxShadow: `0 0 60px ${C.red}`,
            }}
          >
            必見！
          </div>
        </Pop>
      </AbsoluteFill>
      {/* フェーズB */}
      {f >= 74 ? (
        <Shake impacts={[86, 132]} amp={18}>
          <div
            style={abs({
              left: 180,
              top: 250,
              width: 500,
              height: 500,
              transform: `scale(${clockIn})`,
            })}
          >
            <svg width={500} height={500} style={{ position: "absolute" }}>
              <defs>
                <linearGradient id="g7" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor={C.yellow} />
                  <stop offset="100%" stopColor={C.cyan} />
                </linearGradient>
              </defs>
              <circle cx={250} cy={250} r={R} stroke="rgba(255,255,255,.12)" strokeWidth={30} fill="rgba(6,7,15,.75)" />
              <circle
                cx={250}
                cy={250}
                r={R}
                stroke="url(#g7)"
                strokeWidth={30}
                fill="none"
                strokeLinecap="round"
                strokeDasharray={`${circ * arc} ${circ}`}
                transform="rotate(-90 250 250)"
                style={{ filter: `drop-shadow(0 0 14px ${C.cyan})` }}
              />
              {new Array(12).fill(0).map((_, i) => {
                const a = (i / 12) * Math.PI * 2;
                return (
                  <line
                    key={i}
                    x1={250 + Math.cos(a) * 140}
                    y1={250 + Math.sin(a) * 140}
                    x2={250 + Math.cos(a) * 160}
                    y2={250 + Math.sin(a) * 160}
                    stroke="rgba(255,255,255,.6)"
                    strokeWidth={6}
                    strokeLinecap="round"
                  />
                );
              })}
              <line
                x1={250}
                y1={250}
                x2={250}
                y2={150}
                stroke="#fff"
                strokeWidth={12}
                strokeLinecap="round"
                transform={`rotate(${arc * 360} 250 250)`}
              />
              <line
                x1={250}
                y1={250}
                x2={250}
                y2={110}
                stroke={C.cyan}
                strokeWidth={7}
                strokeLinecap="round"
                transform={`rotate(${arc * 360 * 12} 250 250)`}
              />
              <circle cx={250} cy={250} r={14} fill={C.yellow} />
            </svg>
            <div
              style={abs({
                left: 0,
                right: 0,
                top: 470,
                textAlign: "center",
                fontFamily: FONT_EN,
                fontSize: 60,
                letterSpacing: 8,
                color: C.yellow,
              })}
            >
              1 DAY
            </div>
          </div>
          <div style={abs({ left: 760, top: 210 })}>
            <Slam delay={86} fromScale={2.6}>
              <div
                style={{
                  fontFamily: FONT_DISPLAY,
                  fontSize: 210,
                  lineHeight: 1.1,
                  ...gradientText(C.yellow, C.cyan, 100),
                  filter: `drop-shadow(0 0 30px ${C.yellow}88)`,
                }}
              >
                丸一日
              </div>
            </Slam>
            <KText text="あなたの仕事場に伺い" delay={98} stagger={1.5} size={78} style={{ marginTop: 18 }} />
            <div style={{ marginTop: 20 }}>
              <Slam delay={132} fromScale={2.2}>
                <div
                  style={{
                    fontFamily: FONT_DISPLAY,
                    fontSize: 120,
                    lineHeight: 1.15,
                    color: C.cyan,
                    textShadow: `0 0 40px ${C.cyan}`,
                  }}
                >
                  AI化をご提示！
                </div>
              </Slam>
            </div>
          </div>
        </Shake>
      ) : null}
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 08：ココトモSNS・介護システム・制服屋サービスなど 始めやすい価格帯     */
/* ================================================================== */
const CARDS: { label: string; color: string; src: string; rot: number; x: number; d: number }[] = [
  { label: "ココトモSNS", color: C.magenta, src: "kokotomo.jpg", rot: -7, x: 150, d: 22 },
  // 介護システム「みちしるべ」のTOP画面（ログイン後の画面をSafariから撮影。個人情報は写っていない）
  { label: "介護システム", color: "#00c9a7", src: "michishirube.jpg", rot: 0, x: 710, d: 32 },
  { label: "制服屋サービス", color: C.yellow, src: "yuukichi.jpg", rot: 7, x: 1270, d: 42 },
];

export const S8Price: React.FC = () => {
  const { f, spr } = useF();
  return (
    <AbsoluteFill>
      <Kicker num="08" label="SMALL BUSINESS" color={C.yellow} />
      {CARDS.map((c) => {
        const s = spr(c.d, { damping: 13, stiffness: 120, mass: 0.8 });
        const float = Math.sin(f / 12 + c.d) * 8;
        return (
          <div
            key={c.label}
            style={abs({
              left: c.x,
              top: 470 + (c.rot === 0 ? -24 : 0) + float,
              width: 500,
              transform: `translateY(${(1 - s) * 800}px) rotate(${c.rot + (1 - s) * c.rot * 4}deg)`,
            })}
          >
            <div
              style={{
                position: "relative",
                width: 500,
                height: 320,
                borderRadius: 22,
                overflow: "hidden",
                border: `4px solid ${c.color}`,
                boxShadow: `0 30px 80px rgba(0,0,0,.6), 0 0 50px ${c.color}66`,
                background: "#111",
              }}
            >
              <Img src={img(c.src)} style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 10%" }} />
            </div>
            <div style={{ display: "flex", justifyContent: "center", marginTop: -30 }}>
              <div
                style={{
                  position: "relative",
                  background: c.color,
                  color: c.color === C.yellow ? C.ink : "#fff",
                  fontFamily: FONT_DISPLAY,
                  fontSize: 44,
                  padding: "6px 30px 10px",
                  borderRadius: 40,
                  boxShadow: "0 10px 30px rgba(0,0,0,.5)",
                }}
              >
                {c.label}
              </div>
            </div>
          </div>
        );
      })}
      <Pop delay={56} rotate={-20} style={abs({ left: 1660, top: 880 })}>
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 56,
            color: "#fff",
            textShadow: "0 4px 20px #000",
          }}
        >
          など
        </div>
      </Pop>
      <Shake impacts={[80]} amp={14}>
        <div style={abs({ left: 0, right: 0, top: 190 })}>
          <KText text="小規模店舗が" delay={60} size={84} align="center" />
          <div style={{ display: "flex", justifyContent: "center", marginTop: 6 }}>
            <Highlight delay={84} color={`${C.magenta}cc`}>
              <Slam delay={74} fromScale={2.2}>
                <div
                  style={{
                    fontFamily: FONT_DISPLAY,
                    fontSize: 130,
                    lineHeight: 1.15,
                    color: C.yellow,
                    textShadow: `0 0 30px ${C.yellow}88`,
                  }}
                >
                  始めやすい価格帯
                </div>
              </Slam>
            </Highlight>
          </div>
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* 09：運用を変えずに、サービスを運用に合わせます                        */
/* ================================================================== */
export const S9Fit: React.FC = () => {
  const { f, spr } = useF();
  const W = 560;
  const H = 300;
  const r = 70;
  const snap = 84;
  const pIn = spr(26, { damping: 18, stiffness: 60, mass: 1 });
  const rot = interpolate(f, [26, 70, snap], [-90, -90, 0], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const px = interpolate(pIn, [0, 1], [1300, 760]);
  const fx = interpolate(f, [62, snap], [px, W], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const pieceX = f < 62 ? px : fx;
  const flash = interpolate(f, [snap, snap + 3, snap + 14], [0, 1, 0], clamp);
  const ring = interpolate(f, [snap, snap + 22], [0, 1], clamp);
  const leftIn = spr(8);
  const fitS = spr(snap + 2, { damping: 9, stiffness: 200, mass: 0.6 });
  const leftPath = `M0,0 H${W} V${H / 2 - r} A${r},${r} 0 0 1 ${W},${H / 2 + r} V${H} H0 Z`;
  const rightPath = `M0,0 H${W} V${H} H0 V${H / 2 + r} A${r},${r} 0 0 0 0,${H / 2 - r} Z`;
  return (
    <AbsoluteFill>
      <Kicker num="09" label="FIT YOUR WAY" color={C.cyan} />
      <div style={abs({ left: 110, top: 220 })}>
        <KText text="運用を変えずに、" delay={6} size={100} />
      </div>
      {/* パズル */}
      <div style={abs({ left: 960 - W - 20, top: 400, width: W * 2 + 200, height: H + 40 })}>
        <svg
          width={W + 10}
          height={H + 10}
          style={{ position: "absolute", left: 0, top: 0, overflow: "visible", transform: `translateX(${(1 - leftIn) * -600}px)`, opacity: leftIn }}
        >
          <path d={leftPath} fill="rgba(255,255,255,.08)" stroke="#fff" strokeWidth={5} />
        </svg>
        <div
          style={abs({
            left: 0,
            top: 0,
            width: W,
            height: H,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            transform: `translateX(${(1 - leftIn) * -600}px)`,
            opacity: leftIn,
          })}
        >
          <div style={{ fontFamily: FONT_DISPLAY, fontSize: 64, color: "#fff" }}>いつもの運用</div>
          <div
            style={{
              marginTop: 10,
              fontFamily: FONT_JP,
              fontWeight: 900,
              fontSize: 30,
              color: C.ink,
              background: "#fff",
              padding: "4px 20px",
              borderRadius: 30,
            }}
          >
            そのまま
          </div>
        </div>
        <div
          style={abs({
            left: pieceX,
            top: 0,
            width: W,
            height: H,
            transform: `rotate(${rot}deg)`,
            transformOrigin: "50% 50%",
            opacity: interpolate(f, [26, 32], [0, 1], clamp),
          })}
        >
          <svg width={W} height={H} style={{ position: "absolute", overflow: "visible" }}>
            <defs>
              <linearGradient id="g9" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor={C.cyan} />
                <stop offset="100%" stopColor={C.line} />
              </linearGradient>
            </defs>
            <path d={rightPath} fill="url(#g9)" style={{ filter: `drop-shadow(0 0 30px ${C.cyan})` }} />
          </svg>
          <div
            style={abs({
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              paddingLeft: 60,
              fontFamily: FONT_DISPLAY,
              fontSize: 74,
              color: C.ink,
            })}
          >
            サービス
          </div>
        </div>
        {/* スナップ時のリング */}
        <div
          style={abs({
            left: W - 300 * ring,
            top: H / 2 - 300 * ring,
            width: 600 * ring,
            height: 600 * ring,
            borderRadius: "50%",
            border: `${8 * (1 - ring)}px solid ${C.cyan}`,
            opacity: f >= snap ? 1 - ring : 0,
          })}
        />
        <Pop delay={snap + 2} rotate={-30} style={abs({ left: W + 220, top: -90 })}>
          <div
            style={{
              fontFamily: FONT_EN,
              fontSize: 58,
              letterSpacing: 6,
              color: C.ink,
              background: C.yellow,
              padding: "4px 26px",
              borderRadius: 12,
              transform: `rotate(-6deg) scale(${0.9 + fitS * 0.1})`,
              boxShadow: `0 0 40px ${C.yellow}`,
            }}
          >
            PERFECT FIT!
          </div>
        </Pop>
      </div>
      <AbsoluteFill style={{ background: C.cyan, opacity: flash * 0.35 }} />
      <Shake impacts={[snap, 112]} amp={18}>
        <div style={abs({ left: 0, right: 0, top: 780, display: "flex", justifyContent: "center", alignItems: "flex-end", gap: 10 })}>
          <KText text="サービスを" delay={94} size={86} />
          <Slam delay={112} fromScale={2.2}>
            <div
              style={{
                fontFamily: FONT_DISPLAY,
                fontSize: 118,
                lineHeight: 1.12,
                color: C.cyan,
                textShadow: `0 0 40px ${C.cyan}`,
              }}
            >
              運用に合わせます。
            </div>
          </Slam>
        </div>
      </Shake>
    </AbsoluteFill>
  );
};

/* ================================================================== */
/* OUTRO：ご用命はアイアンドエフへ（ロゴ＋QR）                          */
/* ================================================================== */
export const Outro: React.FC = () => {
  const { f, spr } = useF();
  const div = interpolate(f, [44, 64], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const logo = spr(80);
  const qr = spr(56, { damping: 12, stiffness: 120, mass: 0.8 });
  const pulse = (f % 45) / 45;
  const corner = 6 + Math.sin(f / 6) * 6;
  const endFade = interpolate(f, [200, 210], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ background: "linear-gradient(135deg, #ffffff 0%, #f3f5fb 60%, #fff8d6 100%)" }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${85 + Math.sin(f / 30) * 4}% 15%, ${C.yellow}55, transparent 30%), radial-gradient(circle at 10% 95%, ${C.cyan}33, transparent 35%), radial-gradient(circle at 60% 110%, ${C.magenta}22, transparent 35%)`,
        }}
      />
      <div style={abs({ left: 130, top: 120 })}>
        <Highlight delay={14} color={`${C.yellow}`}>
          <KText text="無料でお試しできます！" delay={4} stagger={1.5} size={84} color={C.ink} charStyle={{ textShadow: "none" }} />
        </Highlight>
        <KText
          text="お気軽に。"
          delay={22}
          size={84}
          color={C.magenta}
          style={{ marginTop: 12 }}
          charStyle={{ textShadow: "none" }}
        />
        <div
          style={{
            marginTop: 40,
            width: 1000 * div,
            height: 4,
            background: `linear-gradient(90deg, ${C.ink}, transparent)`,
          }}
        />
        <KText text="ご用命は" delay={48} size={56} color="#555" font={FONT_JP} weight={900} style={{ marginTop: 34 }} charStyle={{ textShadow: "none" }} />
        <KText text="アイアンドエフへ" delay={56} stagger={2.2} size={126} color={C.ink} style={{ marginTop: 4 }} charStyle={{ textShadow: "none" }} />
        <div
          style={{
            marginTop: 40,
            opacity: logo,
            transform: `translateY(${(1 - logo) * 40}px)`,
            display: "flex",
            alignItems: "center",
            gap: 36,
          }}
        >
          <Img src={img("iandf_logo.png")} style={{ width: 400 }} />
        </div>
      </div>
      {/* QR */}
      <div
        style={abs({
          left: 1320,
          top: 200,
          width: 480,
          padding: "34px 40px 30px",
          borderRadius: 32,
          background: "#fff",
          boxShadow: "0 30px 80px rgba(20,25,50,.18), 0 0 0 1px rgba(0,0,0,.05)",
          transform: `scale(${qr}) rotate(${(1 - qr) * 10}deg)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        })}
      >
        <div
          style={{
            fontFamily: FONT_DISPLAY,
            fontSize: 44,
            color: "#fff",
            background: C.ink,
            padding: "4px 34px 8px",
            borderRadius: 40,
          }}
        >
          HPはこちら
        </div>
        <div style={{ position: "relative", width: 380, height: 380, marginTop: 24 }}>
          <Img src={img("qr_iandf.png")} style={{ width: 380, height: 380, display: "block" }} />
          {[
            { left: -corner, top: -corner, bl: true, bt: true },
            { right: -corner, top: -corner, br: true, bt: true },
            { left: -corner, bottom: -corner, bl: true, bb: true },
            { right: -corner, bottom: -corner, br: true, bb: true },
          ].map((c, i) => (
            <div
              key={i}
              style={abs({
                left: c.left,
                right: c.right,
                top: c.top,
                bottom: c.bottom,
                width: 60,
                height: 60,
                borderLeft: c.bl ? `8px solid ${C.magenta}` : undefined,
                borderRight: c.br ? `8px solid ${C.magenta}` : undefined,
                borderTop: c.bt ? `8px solid ${C.magenta}` : undefined,
                borderBottom: c.bb ? `8px solid ${C.magenta}` : undefined,
                borderRadius: 6,
              })}
            />
          ))}
          <div
            style={abs({
              inset: -20 - pulse * 40,
              borderRadius: 30,
              border: `4px solid ${C.magenta}`,
              opacity: (1 - pulse) * 0.5,
            })}
          />
        </div>
        <div style={{ marginTop: 22, fontFamily: FONT_JP, fontWeight: 900, fontSize: 30, color: C.ink, letterSpacing: 1 }}>
          www.i-and-f.co.jp
        </div>
      </div>
      <div
        style={abs({
          left: 0,
          right: 0,
          bottom: 40,
          textAlign: "center",
          fontFamily: FONT_EN,
          fontSize: 26,
          letterSpacing: 14,
          color: "rgba(0,0,0,.45)",
          opacity: logo,
        })}
      >
        i&amp;F GROUP × BANTEX ／ ENTERTAINMENT × AI
      </div>
      <AbsoluteFill style={{ background: "#000", opacity: endFade }} />
    </AbsoluteFill>
  );
};
