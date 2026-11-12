#!/usr/bin/env python3
"""narration.json の原稿を VOICEVOX（春日部つむぎ）で音声にし、audio.tsx の NARRATION を書き換える。

前提: VOICEVOX エンジンが動いていること（既定 http://127.0.0.1:50021、VOICEVOX_URL で変更可）
  Mac mini のエンジンを使うとき: ssh -f -N -L 50121:127.0.0.1:50021 mac-mini
                                  VOICEVOX_URL=http://127.0.0.1:50121 python3 scripts/expo_audio/make_narration.py
出力:
  public/expo/audio/narr_00.wav 〜   1行ずつの音声（48kHz・-16 LUFS にそろえる）
  src/ExpoVideo/audio.tsx           NARRATION の中身（開始フレームと長さ）
narration.json の各行で使えるキー:
  frame  話し始めるフレーム（30fps）
  text   原稿
  kana   読みの直し（AquesTalk 風。句ごとに ' を1つ、/ で句を区切る）。あればこの読みで話す
  speed  この行だけの話速（既定は SPEED）
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021")
SPEAKER_NAME = "春日部つむぎ"
SPEED = 1.15          # 話速
PITCH = 0.03          # 少し高め（元気め）
INTONATION = 1.3      # 抑揚を強め（元気め）
PAUSE = 0.7           # 読点の間を短く
FPS = 30
OUT_DIR = ROOT / "public/expo/audio"
AUDIO_TSX = ROOT / "src/ExpoVideo/audio.tsx"


def call(path, params, body=None):
    url = f"{ENGINE}{path}?{urllib.parse.urlencode(params)}"
    data = json.dumps(body).encode() if body is not None else b""
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as res:
        return res.read()


def speaker_id(name):
    with urllib.request.urlopen(f"{ENGINE}/speakers", timeout=30) as res:
        for s in json.load(res):
            if s["name"] == name:
                return s["styles"][0]["id"]
    raise SystemExit(f"speaker not found: {name}")


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def main():
    sid = speaker_id(SPEAKER_NAME)
    lines = json.loads((ROOT / "scripts/expo_audio/narration.json").read_text())["lines"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, line in enumerate(lines):
        q = json.loads(call("/audio_query", {"text": line["text"], "speaker": sid}))
        if line.get("kana"):
            q["accent_phrases"] = json.loads(
                call("/accent_phrases", {"text": line["kana"], "speaker": sid, "is_kana": "true"})
            )
        q.update(
            speedScale=line.get("speed", SPEED),
            pitchScale=PITCH,
            intonationScale=INTONATION,
            prePhonemeLength=0.05,
            postPhonemeLength=0.12,
            outputSamplingRate=48000,
        )
        if "pauseLengthScale" in q:
            q["pauseLengthScale"] = PAUSE
        raw = call("/synthesis", {"speaker": sid}, q)
        out = OUT_DIR / f"narr_{i:02d}.wav"
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(raw)
            tmp.flush()
            # 音量をそろえる（声だけで -16 LUFS、ピーク -1.5 dBTP）
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", tmp.name,
                 "-af", "loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000",
                 "-ac", "1", "-c:a", "pcm_s16le", str(out)],
                check=True,
            )
        secs = wav_seconds(out)
        length = int(secs * FPS + 0.999)
        entries.append((line["frame"], out.name, length))
        print(f"narr_{i:02d}  start {line['frame']:4d}  {secs:4.2f}s ({length}f)  {line['text']}")

    # 次の行と重ならないか確認
    for (a, _, la), (b, name, _) in zip(entries, entries[1:]):
        if a + la > b:
            print(f"  ! 重なり: {name} の前の行が {a + la - b} フレームはみ出しています", file=sys.stderr)

    body = "\n".join(f'  {{ at: {a}, file: "expo/audio/{n}", len: {l} }},' for a, n, l in entries)
    src = AUDIO_TSX.read_text()
    new, count = re.subn(
        r"export const NARRATION: Narr\[\] = \[[^\]]*\];",
        f"export const NARRATION: Narr[] = [\n{body}\n];",
        src,
    )
    if count != 1:
        raise SystemExit("audio.tsx の NARRATION が見つかりません")
    AUDIO_TSX.write_text(new)
    print(f"audio.tsx の NARRATION を {len(entries)} 行で更新しました")


if __name__ == "__main__":
    main()
