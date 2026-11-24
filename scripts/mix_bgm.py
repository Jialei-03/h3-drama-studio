#!/usr/bin/env python3
"""给成片混背景音乐：画面直接复制，原声只做增益，音乐在 numpy 里整条算好再叠上去，最后限幅、编码一次。

规则（来自 bgm.md / loudness.md）：音乐只当背景、整条连续不剪、电平全程一致、不压低原声；
从结尾反推对齐（让高潮收尾那一句的重拍落在最后一个大招的冲击帧上）；混音后限幅，量编码后的成片。
本脚本不带任何音乐，请用你有授权的歌。所有数字都放在一份 yaml 里（示例：examples/gemini-revenge/data/bgm.example.yaml）。

输入：
  PLAN.yaml   配乐参数（见下，每项都有注释版的示例）
  FILM.mp4    已加好字幕的成片（第 0 路是画面；已嵌入的封面流会带过去）
  --song      歌曲文件（覆盖 yaml 里第一条 track 的 file；任何 ffmpeg 能解的格式）
输出：OUT.mp4（画面 -c:v copy，音轨 AAC）；脚本结束时量一遍响度和真峰值并提示是否超标。

yaml 里所有"片中时间"都按**写参数时的时间线**写，经过 shifts 平移后才使用：剪过片，只往 shifts 里加一行，
其余常量一个不改（rough-cut.md 第 6 节）。歌曲里的时间（align.song_time）不平移。

yaml 结构（秒）：
  shifts: [{at: 41.7, delta: -0.25}]          # 时间 >= at 的统一加 delta（负数 = 前移）
  film_gain_db: 4.0                           # 原声（对白+音效）整体增益
  shouts: [{start, end, db, ramp}]            # 喊招等需要突出的原声段：只放大原声，不动音乐；两端各 ramp 秒渐变
  tracks:                                     # 一首歌一条；两首歌接力就写两条（交叉淡变靠两条的 fade）
    - file: 歌曲文件
      align: {song_time: S_end, film_time: T_end}   # 歌里某个重拍 ↔ 片中某个时刻，偏移 OFF = T_end - S_end
      fade_in: [起, 满]                       # 音乐在片中 起 进入，满 时到满电平（余弦淡入）
      fade_out: [起, 止]                      # 可省：省了就一直放到歌曲自然结束
      gain_db: 0                              # 这首歌单独的微调
  music:
    gain_db: -14.5                            # 音乐总增益；或 target_lufs: -21.8（按使用段响度自动算）
    target_lufs: null
    measure_range: [85, 150]                  # target_lufs 用哪一段量（默认 淡入满之后到对齐点）
    leveler: {ref: [85, 150], max_db: 8, window: 2.0, smooth: 1.0, floor_db: 30, start: 83.0, ramp: 0.5}   # 校平
    boosts: [{rise: [153.5, 154.0], fall: [162, 163], db: 4}]   # 关键点推高；fall 省了就保持到片尾
    tail: {take: [160.8, 162.3], fade_out: [164.0, 168.0], wet_db: -15.5, ir_len: 8, decay_60db: 15, lowpass: 0.6, predelay_ms: 20, seed: 1}
  limiter: {limit: 0.8, attack: 5, release: 80}
  aac_bitrate: 256k

用法示例：
  python3 scripts/mix_bgm.py bgm.yaml film_subs.mp4 film_bgm.mp4 --song my_licensed_song.flac
  python3 scripts/mix_bgm.py bgm.yaml film_subs.mp4 --dry-run    # 只打印平移后的时间线
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _config import add_config_arg, load_config  # noqa: E402


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, **kw)
    except FileNotFoundError:
        sys.exit("找不到 ffmpeg/ffprobe，请先安装并加入 PATH")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", "replace")[-600:] if isinstance(e.stderr, bytes) else ""
        sys.exit(f"命令失败（{cmd[0]}，退出码 {e.returncode}）：{err}")


def probe(path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + ["-show_entries", entries, "-of", "csv=p=0", path]
    return run(cmd, capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------------------ 数值小工具（只用 numpy）
def load(path, sr):
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    if not raw:
        sys.exit(f"解不出音频：{path}")
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def ramp(t, a, b, up=True):
    """余弦淡变，0→1（up=False 则 1→0）"""
    x = np.clip((t - a) / max(b - a, 1e-6), 0, 1)
    v = 0.5 - 0.5 * np.cos(np.pi * x)
    return v if up else 1 - v


def uniform_filter1d(x, size):
    """滑动平均，边缘按 scipy 的 reflect 方式（不依赖 scipy）。"""
    if size <= 1:
        return x.copy()
    left, right = size // 2, (size - 1) // 2
    p = np.pad(x, (left, right), mode="symmetric")
    return np.convolve(p, np.ones(size) / size, mode="valid")


def fftconvolve(x, h):
    n = len(x) + len(h) - 1
    nfft = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:n]


def write_wav(path, data, sr):
    run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", path],
        input=np.ascontiguousarray(data, np.float32).tobytes())


def ebur128(path, ss=None, t=None):
    """用 ffmpeg 的 ebur128 量 整合响度 I、响度范围 LRA、真峰值（dBTP）；量不到的项返回 None。"""
    cmd = ["ffmpeg", "-hide_banner", "-nostats"] + (["-ss", str(ss)] if ss is not None else []) + (["-t", str(t)] if t is not None else []) + \
          ["-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    txt = subprocess.run(cmd, capture_output=True, text=True).stderr
    summ = txt[txt.rfind("Summary:"):] if "Summary:" in txt else ""
    pick = lambda pat: (lambda m: float(m.group(1)) if m else None)(re.search(pat, summ))
    return dict(I=pick(r"\bI:\s+(-?[\d.]+) LUFS"), LRA=pick(r"LRA:\s+(-?[\d.]+) LU"), TP=pick(r"Peak:\s+(-?[\d.]+) dBFS"))


def make_shift(shifts):
    return lambda t: t + sum(float(s["delta"]) for s in shifts if t >= float(s["at"]))


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser(description="背景音乐混音：对齐 / 淡入 / 校平 / 推高 / 混响尾巴 / 原声增益 / 限幅", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="本脚本不含任何音乐。更多说明见脚本顶部和 skills/drama-postproduction/references/bgm.md。")
    ap.add_argument("plan", help="配乐参数 PLAN.yaml")
    ap.add_argument("film", help="成片 FILM.mp4")
    ap.add_argument("out", nargs="?", help="输出 OUT.mp4（--dry-run 时可省）")
    ap.add_argument("--song", help="歌曲文件（覆盖 yaml 里第一条 track 的 file）")
    ap.add_argument("--dry-run", action="store_true", help="只打印平移后的时间线，不处理音频")
    ap.add_argument("--work-dir", help="中间 wav（音乐轨、原声轨）存放目录（默认临时目录，用完删除）")
    ap.add_argument("--no-measure", action="store_true", help="混完不量响度和真峰值")
    add_config_arg(ap)
    a = ap.parse_args()
    load_config(a.config)
    if not a.out and not a.dry_run:
        ap.error("需要 OUT.mp4（或 --dry-run）")
    if not os.path.isfile(a.film):
        sys.exit(f"找不到成片：{a.film}")
    try:
        import yaml
    except ImportError:
        sys.exit("缺少 PyYAML：pip install pyyaml")
    ppath = os.path.abspath(a.plan)
    P = yaml.safe_load(open(ppath, encoding="utf-8")) or {}
    sh = make_shift(P.get("shifts") or [])
    SR = int(P.get("sample_rate", 48000))
    tracks = P.get("tracks") or []
    if not tracks:
        sys.exit("yaml 里没有 tracks")
    if a.song:
        tracks[0]["file"] = a.song
    for tr in tracks:
        f = os.path.expanduser(str(tr.get("file") or ""))
        if not f:
            sys.exit("有一条 track 没有 file（用 --song 或在 yaml 里写）")
        tr["_file"] = f if os.path.isabs(f) or a.song and tr is tracks[0] else os.path.join(os.path.dirname(ppath), f)

    dur = float(probe(a.film, "format=duration"))
    N = int(dur * SR)
    t = np.arange(N) / SR
    M = P.get("music") or {}

    # -------- 时间线（平移后）
    print(f"成片 {dur:.3f} s；shifts: {P.get('shifts') or '无'}")
    for i, tr in enumerate(tracks, 1):
        al = tr["align"]
        off = sh(float(al["film_time"])) - float(al["song_time"])
        fi = [sh(float(x)) for x in tr["fade_in"]]
        fo = [sh(float(x)) for x in tr["fade_out"]] if tr.get("fade_out") else None
        tr["_off"], tr["_fi"], tr["_fo"] = off, fi, fo
        print(f"  轨 {i}：偏移 OFF={off:+.3f}（片中 = 歌曲 + OFF）；淡入 {fi[0]:.2f}→{fi[1]:.2f}；" + (f"淡出 {fo[0]:.2f}→{fo[1]:.2f}" if fo else "一直放到歌曲结束"))
    if a.dry_run:
        for k in ("leveler", "tail"):
            if M.get(k):
                print(f"  {k}: {M[k]}（时间项平移后使用）")
        return

    # -------- 1. 把歌曲按偏移摆到片中时间线上，淡入、淡出
    for tr in tracks:
        if not os.path.isfile(tr["_file"]):
            sys.exit(f"找不到歌曲文件：{tr['_file']}（本仓库不带音乐：用 --song 指定你有授权的歌）")
    music = np.zeros((N, 2), np.float32)
    for tr in tracks:
        y = load(tr["_file"], SR)
        i0, i1 = tr["_fi"]
        s0 = int(round((i0 - tr["_off"]) * SR))                 # 片中 i0 对应的歌曲采样位置
        if s0 < 0:
            sys.exit(f"歌曲在片中 {i0:.2f} s 对应的位置是歌曲第 {s0 / SR:.1f} s，歌曲没有那么早的内容：调整 align 或 fade_in")
        a0 = int(round(i0 * SR))
        end = int(round(tr["_fo"][1] * SR)) if tr["_fo"] else N
        n = max(0, min(end - a0, len(y) - s0, N - a0))
        seg = np.zeros((N, 2), np.float32)
        seg[a0:a0 + n] = y[s0:s0 + n]
        env = ramp(t, i0, i1)
        if tr["_fo"]:
            env *= ramp(t, tr["_fo"][0], tr["_fo"][1], False)
        music += seg * env[:, None].astype(np.float32) * np.float32(10 ** (float(tr.get("gain_db", 0)) / 20))
        print(f"  歌曲 {os.path.basename(tr['_file'])}：从歌曲 {s0 / SR:.2f} s 起放，片中 {a0 / SR:.2f}–{(a0 + n) / SR:.2f} s"
              + ("（歌曲在此之前自然结束）" if a0 + n < end and tr["_fo"] is None else ""))

    # -------- 2. 总增益：给定 gain_db，或按使用段响度算到目标 LUFS
    tmp = tempfile.TemporaryDirectory() if not a.work_dir else None
    wd = a.work_dir or tmp.name
    os.makedirs(wd, exist_ok=True)
    try:
        gain_db = M.get("gain_db")
        if M.get("target_lufs") is not None:
            r0, r1 = (sh(float(x)) for x in (M.get("measure_range") or [tracks[0]["_fi"][1], sh(float(tracks[-1]["align"]["film_time"]))]))
            p = os.path.join(wd, "_measure.wav")
            write_wav(p, music[int(r0 * SR):int(r1 * SR)], SR)
            cur = ebur128(p)["I"]
            if cur is None:
                sys.exit("量不到使用段的响度，请改用 gain_db")
            gain_db = float(M["target_lufs"]) - cur
            print(f"  使用段 {r0:.1f}–{r1:.1f} s 的音乐响度 {cur:.1f} LUFS → 目标 {M['target_lufs']} LUFS，增益 {gain_db:+.2f} dB")
        elif gain_db is None:
            sys.exit("music 里要给 gain_db 或 target_lufs（歌曲母带一般很响，要降十几 dB；换歌要重新量，不要抄别人的数）")
        g = np.full(N, 10 ** (float(gain_db) / 20))

        # -------- 3. 校平：淡入完成后音乐响度全程一致（短时响度 → 偏离参考值的部分补回来，限幅在 ±max_db）
        L = M.get("leveler")
        if L:
            hop = SR // 10
            nb = N // hop
            x = (music * g[:, None].astype(np.float32)).mean(1)[:nb * hop].astype(np.float64)
            pw = (x.reshape(nb, hop) ** 2).mean(1)
            lv = 10 * np.log10(uniform_filter1d(pw, int(round(float(L.get("window", 2.0)) * 10))) + 1e-12)
            tt = np.arange(nb) * 0.1 + 0.05
            r0, r1 = (sh(float(v)) for v in L["ref"])
            sel = (tt > r0) & (tt < r1)
            if not sel.any():
                sys.exit("leveler.ref 范围里没有声音，检查时间")
            ref = np.median(lv[sel])                                  # 参考值 = 主段内短时响度的中位数
            mx = float(L.get("max_db", 8))
            agc = np.where(lv > ref - float(L.get("floor_db", 30)), np.clip(ref - lv, -mx, mx), 0)   # 只在有声音处起作用
            agc = uniform_filter1d(agc, int(round(float(L.get("smooth", 1.0)) * 10)))
            st = sh(float(L.get("start", tracks[0]["_fi"][1])))
            g *= 10 ** (np.interp(t, tt, agc) * ramp(t, st, st + float(L.get("ramp", 0.5))) / 20)   # 淡入结束之后才渐入，不改淡入本身
            print(f"  校平：参考 {ref:.1f} dB（相对满刻度），修正范围 ±{mx:g} dB，实际 {agc.min():+.1f}…{agc.max():+.1f} dB")

        # -------- 4. 关键点推高（例：最后两声被爆炸声盖住，单独推高）
        for b in M.get("boosts") or []:
            up = [sh(float(v)) for v in b["rise"]]
            e = ramp(t, up[0], up[1])
            if b.get("fall"):
                dn = [sh(float(v)) for v in b["fall"]]
                e = e * ramp(t, dn[0], dn[1], False)
            g *= 10 ** (float(b["db"]) / 20 * e)
        music *= g[:, None].astype(np.float32)

        # -------- 5. 混响尾巴：原曲最后一声骤停时，给它加大厅混响让余音延续，再慢慢淡掉
        T = M.get("tail")
        if T:
            a0, a1 = (sh(float(v)) for v in T["take"])
            f0, f1 = (sh(float(v)) for v in T["fade_out"])
            rng = np.random.default_rng(int(T.get("seed", 1)))
            Ln = int(float(T.get("ir_len", 8)) * SR)
            ir = rng.standard_normal((Ln, 2)) * np.exp(-6.9 * (np.arange(Ln) / SR) / float(T.get("decay_60db", 15)))[:, None]   # 6.9 = ln(1000)，即衰减 60 dB
            ir[:int(float(T.get("predelay_ms", 20)) * SR / 1000)] = 0
            al = float(T.get("lowpass", 0.6))                          # 一阶低通，让尾巴更暖
            h = al * (1 - al) ** np.arange(64)
            for c in range(2):
                ir[:, c] = np.convolve(ir[:, c], h)[:Ln]
            src = music[int(a0 * SR):int(a1 * SR)].astype(np.float64)
            if len(src) < SR // 10 or not np.any(src):
                sys.exit(f"tail.take 取到的音乐是空的（{a0:.2f}–{a1:.2f} s）：检查时间")
            wet = np.stack([fftconvolve(src[:, c], ir[:, c]) for c in range(2)], 1)
            wet *= np.sqrt(np.mean(src ** 2)) / np.sqrt(np.mean(wet[:len(src)] ** 2)) * 10 ** (float(T.get("wet_db", -15.5)) / 20)
            i0 = int(a0 * SR)
            n = min(len(wet), N - i0)
            music[i0:i0 + n] += wet[:n].astype(np.float32)
            music *= (ramp(t, f0, f1, False) * (t >= f0) + (t < f0))[:, None].astype(np.float32)
            print(f"  混响尾巴：取 {a0:.2f}–{a1:.2f} s，{f0:.1f}→{f1:.1f} s 淡出")

        # -------- 6. 原声：整体增益 + 喊招增益区间（只放大原声，不动音乐；不压低任何原声）
        film = load(a.film, SR)
        film = film[:N] if len(film) >= N else np.vstack([film, np.zeros((N - len(film), 2), np.float32)])
        film = film * np.float32(10 ** (float(P.get("film_gain_db", 0)) / 20))
        for s in P.get("shouts") or []:
            s0, s1 = sh(float(s["start"])), sh(float(s["end"]))
            rp = float(s.get("ramp", 0.15))
            film *= (10 ** (float(s["db"]) / 20 * ramp(t, s0 - rp, s0) * ramp(t, s1, s1 + rp, False)))[:, None].astype(np.float32)

        mw, fw = os.path.join(wd, "music.wav"), os.path.join(wd, "film.wav")
        write_wav(mw, music, SR)
        write_wav(fw, film, SR)

        # -------- 7. 混合 → 限幅 → 编码一次；画面直接复制
        lim = P.get("limiter") or {}
        flt = (f"[1:a][2:a]amix=inputs=2:duration=first:normalize=0,"
               f"alimiter=limit={lim.get('limit', 0.8)}:attack={lim.get('attack', 5)}:release={lim.get('release', 80)}:level=false[a]")
        nvid = len([x for x in probe(a.film, "stream=index", "v").splitlines() if x.strip()])
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.film, "-i", fw, "-i", mw, "-filter_complex", flt, "-map", "0:v:0", "-map", "[a]"]
        if nvid >= 2:                                                  # 带着嵌入的封面流
            cmd += ["-map", "0:v:1"]
        cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", str(P.get("aac_bitrate", "256k")), "-ar", str(SR)]
        if nvid >= 2:
            cmd += ["-disposition:v:1", "attached_pic"]
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        run(cmd + ["-movflags", "+faststart", a.out], stderr=subprocess.PIPE)
    finally:
        if tmp:
            tmp.cleanup()
    print("OK", a.out)

    if not a.no_measure:                                               # 量编码后的成片，不量中间 wav
        m = ebur128(a.out)
        print(f"  成片响度 I={m['I']} LUFS，LRA={m['LRA']} LU，真峰值 {m['TP']} dBTP（目标：约 -15 LUFS、真峰值 <= -1.5 dBTP；见 loudness.md）")
        if m["TP"] is not None and m["TP"] > -1.5:
            print(f"  注意：真峰值超过 -1.5 dBTP：把 limiter.limit 再调低一点（例 0.75）重混；重混不需要重新渲染画面")


if __name__ == "__main__":
    main()
