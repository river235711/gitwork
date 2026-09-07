#!/bin/bash
# extract_all.sh -- 依檔名建立資料夾並解壓縮
#
# 用法:
#   ./extract_all.sh [-n] [-o OUTDIR] [SRC ...]
#
#   SRC 可以是目錄(掃描其中的壓縮檔)、單一壓縮檔、或含檔案清單的純文字檔
#       (清單檔不限副檔名,例如 list;也可用 -l 強制當成清單)
#   不給 SRC 時預設掃描目前目錄
#
#   -n  dry-run,只印出要做的事
#   -l  把 SRC 一律當成檔案清單
#   -o  解壓的輸出根目錄(預設:目前工作目錄)
#
# 例:
#   LN04LPP_ICVDFM_S00-V1.0.9.3_DFM.zip      -> LN04LPP_ICVDFM_S00-V1.0.9.3_DFM/
#   LN04LPP_ICVDummyFill_S00-V1.0.9.3_doc.tar.gz -> LN04LPP_ICVDummyFill_S00-V1.0.9.3_doc/

set -u

DRYRUN=0
OUTROOT=""
ASLIST=0

usage() { sed -n '2,20p' "$0"; exit 1; }

# 自行解析參數:選項可以放在來源之前或之後
SRCS=()
while [ $# -gt 0 ]; do
    case "$1" in
        -n)  DRYRUN=1 ;;
        -l)  ASLIST=1 ;;
        -o)  shift; [ $# -gt 0 ] || { echo "-o 需要一個目錄" >&2; exit 1; }; OUTROOT=$1 ;;
        -o*) OUTROOT=${1#-o} ;;
        -h|--help) usage ;;
        -*)  echo "未知選項: $1" >&2; usage ;;
        *)   SRCS+=("$1") ;;
    esac
    shift
done
set -- "${SRCS[@]+"${SRCS[@]}"}"

[ $# -eq 0 ] && set -- .

run() {
    if [ "$DRYRUN" -eq 1 ]; then
        printf '  [dry-run]'; printf ' %q' "$@"; printf '\n'
    else
        "$@"
    fi
}

# 由檔名推出資料夾名(去掉副檔名)
base_name() {
    local b=${1##*/}
    case "$b" in
        *.tar.gz)  echo "${b%.tar.gz}"  ;;
        *.tar.bz2) echo "${b%.tar.bz2}" ;;
        *.tar.xz)  echo "${b%.tar.xz}"  ;;
        *.tgz)     echo "${b%.tgz}"     ;;
        *.tar)     echo "${b%.tar}"     ;;
        *.zip)     echo "${b%.zip}"     ;;
        *.gz)      echo "${b%.gz}"      ;;
        *)         echo ""              ;;
    esac
}

# 判斷 SRC 是不是「檔案清單」:非壓縮副檔名 + 是純文字檔
is_list_file() {
    [ -n "$(base_name "$1")" ] && return 1   # 有壓縮副檔名 -> 不是清單
    grep -Iq . -- "$1" 2>/dev/null           # -I: 二進位檔視為不符合
}

n_ok=0 n_skip=0 n_fail=0

extract_one() {
    local f=$1
    local dirname_ base out rc

    if [ ! -f "$f" ]; then
        echo "!! 找不到檔案: $f" >&2
        n_fail=$((n_fail + 1))
        return
    fi

    base=$(base_name "$f")
    if [ -z "$base" ]; then
        echo "-- 略過(非支援的壓縮檔): $f"
        n_skip=$((n_skip + 1))
        return
    fi

    dirname_=${OUTROOT:-.}
    out=$dirname_/$base

    if [ -d "$out" ] && [ -n "$(ls -A -- "$out" 2>/dev/null)" ]; then
        echo "== 已存在且非空,略過: $out"
        n_skip=$((n_skip + 1))
        return
    fi

    echo ">> $f"
    echo "   -> $out"
    run mkdir -p -- "$out" || { n_fail=$((n_fail + 1)); return; }

    case "$f" in
        *.zip)
            run unzip -q -o -d "$out" -- "$f" ;;
        *.tar.gz|*.tgz)
            run tar -xzf "$f" -C "$out" ;;
        *.tar.bz2)
            run tar -xjf "$f" -C "$out" ;;
        *.tar.xz)
            run tar -xJf "$f" -C "$out" ;;
        *.tar)
            run tar -xf "$f" -C "$out" ;;
        *.gz)
            if [ "$DRYRUN" -eq 1 ]; then
                echo "  [dry-run] gunzip -c $f > $out/$base"
            else
                gunzip -c -- "$f" > "$out/$base"
            fi
            ;;
    esac
    rc=$?

    if [ $rc -eq 0 ]; then
        n_ok=$((n_ok + 1))
    else
        echo "!! 解壓失敗 (rc=$rc): $f" >&2
        n_fail=$((n_fail + 1))
    fi
}

for src in "$@"; do
    if [ -d "$src" ]; then
        # 掃描目錄內的壓縮檔(不遞迴)
        while IFS= read -r f; do
            extract_one "$f"
        done < <(find "$src" -maxdepth 1 -type f \
                    \( -name '*.zip'  -o -name '*.tar.gz' -o -name '*.tgz' \
                       -o -name '*.tar' -o -name '*.tar.bz2' -o -name '*.tar.xz' \) \
                 | sort)
    elif [ -f "$src" ] && { [ "$ASLIST" -eq 1 ] || is_list_file "$src"; }; then
        # 檔案清單:一行一個路徑
        while IFS= read -r line; do
            line=${line%$'\r'}
            [ -z "${line// }" ] && continue
            case "$line" in \#*) continue ;; esac
            extract_one "$line"
        done < "$src"
    else
        extract_one "$src"
    fi
done

echo
echo "完成: 成功 $n_ok / 略過 $n_skip / 失敗 $n_fail"
[ "$n_fail" -eq 0 ]
