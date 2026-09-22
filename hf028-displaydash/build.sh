#!/bin/sh
# 旧版 ipk（opkg）构建脚本；ImmortalWrt 25.12 已改用 apk，请使用 build-apk.sh。
# 在 OpenWrt/ImmortalWrt 软路由上构建两个 ipk：
#   displaydash_<ver>_all.ipk          服务主程序
#   luci-app-displaydash_<ver>_all.ipk LuCI 界面
# 需要 opkg-utils（opkg update && opkg install opkg-utils）
set -e

SRC=$(cd "$(dirname "$0")" && pwd)
VER=0.2.0
OUT="$SRC/bin"
mkdir -p "$OUT"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

command -v opkg-build >/dev/null 2>&1 || {
    echo "缺少 opkg-build，请先: opkg update && opkg install opkg-utils"
    exit 1
}

stage_pkg() {
    NAME=$1
    DATA=$2
    DEPENDS=$3
    PDIR="$TMP/$NAME"
    mkdir -p "$PDIR/control" "$PDIR/data"
    cp -a "$DATA/." "$PDIR/data/"
    cat > "$PDIR/control/control" <<EOF
Package: $NAME
Version: $VER
Depends: $DEPENDS
Architecture: all
Maintainer: displaydash
Section: luci
Priority: optional
Description: HF028 serial display dashboard (HomeProxy edition)
EOF
    (cd "$PDIR" && opkg-build -o root -g root "$OUT" >/dev/null)
}

stage_pkg displaydash "$SRC/service" "python3, python3-pyserial, python3-ssl, python3-urllib, curl"
LUCI_STAGE="$TMP/luci-stage"
mkdir -p "$LUCI_STAGE/www"
cp -a "$SRC/luci/root/." "$LUCI_STAGE/"
cp -a "$SRC/luci/htdocs/." "$LUCI_STAGE/www/"
stage_pkg luci-app-displaydash "$LUCI_STAGE" "luci-base, displaydash"

echo "==> 输出:"
ls -la "$OUT"
