#!/usr/bin/env bash
# 把封面图作为"附图"（attached_pic）嵌进 mp4，画面和声音直接复制，不重新编码（几秒）。
#
# 输入：VIDEO.mp4（成片）、COVER.jpg（封面；不是 JPEG 的会先转成 JPEG，只转封面，不动成片）
# 输出：OUT.mp4（和成片同样的画面、声音，多一路封面流）
# 成片里如果已经有封面流，会先去掉再嵌新的（所以可以反复嵌）。
# 嵌入后：画面流仍是第 0 路视频流，封面是紧接着的下一路（见 drama-publish/covers.md）。
#
# 用法示例：
#   scripts/embed_cover.sh final.mp4 cover_landscape.jpg final_with_cover.mp4
#
# 注意：字幕（render_subs.py）、冲击帧（impact_frames.py）这两步会丢掉封面流；
#       配乐（mix_bgm.py）和歌词（render_lyrics.py）会把它带过去。所以封面最好在字幕之后嵌。
set -euo pipefail

usage() { awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"; }
case "${1:-}" in -h|--help) usage; exit 0 ;; esac
if [ "$#" -ne 3 ]; then usage >&2; exit 2; fi
VIDEO=$1; COVER=$2; OUT=$3

command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo "找不到 ffmpeg/ffprobe，请先安装并加入 PATH" >&2; exit 1; }
[ -f "$VIDEO" ] || { echo "找不到成片：$VIDEO" >&2; exit 1; }
[ -f "$COVER" ] || { echo "找不到封面：$COVER" >&2; exit 1; }
if [ "$(cd "$(dirname "$VIDEO")" && pwd)/$(basename "$VIDEO")" = "$(mkdir -p "$(dirname "$OUT")" && cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")" ]; then
  echo "OUT 不能和成片是同一个文件" >&2; exit 1
fi

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# 封面统一成 JPEG（mp4 里 mjpeg 的附图兼容性最好）
CODEC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$COVER")
if [ "$CODEC" != "mjpeg" ]; then
  ffmpeg -v error -y -i "$COVER" -frames:v 1 -q:v 2 "$TMP/cover.jpg"
  COVER="$TMP/cover.jpg"
fi

# 真正的画面流有几路（ffprobe 的 V = 不含附图的视频流），封面就是它们之后的那一路
NV=$(ffprobe -v error -select_streams V -show_entries stream=index -of csv=p=0 "$VIDEO" | grep -c . || true)
[ "$NV" -ge 1 ] || { echo "成片里没有视频流：$VIDEO" >&2; exit 1; }

# -map 0:V 只取真正的画面流，旧封面因此被丢掉；音频、字幕轨用 ? 容许没有
ffmpeg -v error -y -i "$VIDEO" -i "$COVER" \
  -map 0:V -map '0:a?' -map '0:s?' -map 1:v \
  -c copy -disposition:v:"$NV" attached_pic \
  -map_metadata 0 -movflags +faststart "$OUT"

echo "OK $OUT"
ffprobe -v error -show_entries stream=index,codec_type,codec_name:stream_disposition=attached_pic -of compact "$OUT"
