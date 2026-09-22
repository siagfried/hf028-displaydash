#!/bin/sh
# 在 ImmortalWrt 25.12（apk 包管理器）上构建两个 .apk：
#   displaydash_<ver>_x86_64.apk           服务主程序
#   luci-app-displaydash_<ver>_x86_64.apk  LuCI 界面
# 用法：sh build-apk.sh [版本号，默认 0.3.0]
set -e

SRC=$(cd "$(dirname "$0")" && pwd)
VER="${1:-0.3.0}"
OUT="$SRC/bin"
mkdir -p "$OUT"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# apk 包 = 一个 tar.gz，内部先放 .PKGINFO，再放文件树
stage_apk() {
    NAME=$1
    DATA=$2
    DEPENDS=$3
    DESC=$4
    PDIR="$TMP/$NAME"
    mkdir -p "$PDIR"
    cp -a "$DATA/." "$PDIR/"
    # 统一权限：目录可读可执行，文件可读，脚本/服务可执行
    find "$PDIR" -type d -exec chmod 755 {} \;
    find "$PDIR" -type f -exec chmod 644 {} \;
    chmod 755 "$PDIR/usr/bin/displaydash" "$PDIR/usr/bin/dashctl" \
        "$PDIR/etc/init.d/displaydash" 2>/dev/null || true

    {
        echo "pkgname = $NAME"
        echo "pkgver = ${VER}-r0"
        echo "pkgdesc = $DESC"
        echo "url = https://github.com/immortalwrt/homeproxy"
        echo "packager = displaydash"
        echo "size = $(du -sb "$PDIR" | awk '{print $1}')"
        echo "arch = x86_64"
        echo "license = GPL-2.0-only"
        echo "depends = $DEPENDS"
        echo "origin = $NAME"
        echo "maintainer = displaydash"
    } > "$PDIR/.PKGINFO"

    # .PKGINFO 必须是 tar 的第一个成员
    (cd "$PDIR" && if tar --version 2>/dev/null | grep -qi 'GNU tar'; then
        tar -czf "$OUT/${NAME}_${VER}-r0_x86_64.apk" \
            --format=ustar --owner=0 --group=0 \
            .PKGINFO $(find . -mindepth 1 ! -name '.PKGINFO' | sort)
    else
        tar -czf "$OUT/${NAME}_${VER}-r0_x86_64.apk" \
            .PKGINFO $(find . -mindepth 1 ! -name '.PKGINFO' | sort)
    fi)
}

stage_apk displaydash \
    "$SRC/service" "python3 python3-pyserial python3-ssl python3-urllib curl" \
    "HF028 serial display dashboard service"
LUCI_STAGE="$TMP/luci-stage"
mkdir -p "$LUCI_STAGE/www"
cp -a "$SRC/luci/root/." "$LUCI_STAGE/"
cp -a "$SRC/luci/htdocs/." "$LUCI_STAGE/www/"
stage_apk luci-app-displaydash \
    "$LUCI_STAGE" "luci-base displaydash" \
    "LuCI UI for HF028 display dashboard"

echo "==> 输出："
ls -la "$OUT"
