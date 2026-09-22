#!/bin/sh
# 开发直装（不打包 ipk）：复制文件并重启服务
# 用法: sh dev_install.sh          # 全新安装配置
#       sh dev_install.sh --keep-config
set -e

SRC=$(cd "$(dirname "$0")" && pwd)

[ "$(id -u)" = 0 ] || { echo "需要 root"; exit 1; }

echo "==> 复制主程序"
mkdir -p /usr/lib/displaydash
cp -a "$SRC/service/usr/lib/displaydash/." /usr/lib/displaydash/
cp "$SRC/service/usr/bin/displaydash" /usr/bin/displaydash
cp "$SRC/service/usr/bin/dashctl" /usr/bin/dashctl
cp "$SRC/service/usr/bin/displaydash-serial-bridge" /usr/bin/displaydash-serial-bridge
cp "$SRC/service/etc/init.d/displaydash" /etc/init.d/displaydash
chmod 755 /usr/bin/displaydash /usr/bin/dashctl /usr/bin/displaydash-serial-bridge /etc/init.d/displaydash

if [ -f /etc/config/displaydash ]; then
    if [ "$1" = "--keep-config" ]; then
        echo "==> 保留已有配置"
    else
        cp /etc/config/displaydash /etc/config/displaydash.bak.$(date +%s)
        echo "==> 旧配置已备份，写入新配置"
        cp "$SRC/service/etc/config/displaydash" /etc/config/displaydash
        chmod 644 /etc/config/displaydash
    fi
else
    cp "$SRC/service/etc/config/displaydash" /etc/config/displaydash
    chmod 644 /etc/config/displaydash
    echo "==> 写入新配置"
fi

# Preserve custom screen profiles when updating an existing installation.
if [ ! -f /etc/config/displaydash-screen ] || [ "$1" != "--keep-config" ]; then
    if [ -f /etc/config/displaydash-screen ]; then
        cp /etc/config/displaydash-screen /etc/config/displaydash-screen.bak.$(date +%s)
    fi
    cp "$SRC/service/etc/config/displaydash-screen" /etc/config/displaydash-screen
    chmod 644 /etc/config/displaydash-screen
fi

echo "==> 复制 LuCI"
cp -a "$SRC/luci/root/." /
mkdir -p /www
cp -a "$SRC/luci/htdocs/." /www/
chmod 644 /usr/share/luci/menu.d/luci-app-displaydash.json \
    /usr/share/rpcd/acl.d/luci-app-displaydash.json \
    /usr/share/rpcd/ucode/displaydash.uc
find /www/luci-static/resources/view/displaydash -type f \
    -exec chmod 644 {} + 2>/dev/null || true

/etc/init.d/displaydash enable
/etc/init.d/displaydash restart
/etc/init.d/rpcd restart 2>/dev/null || true
echo "==> 完成。LuCI: 服务 -> DisplayDash"
