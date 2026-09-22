# DisplayDash 当前源码

HomeProxy/sing-box 看板：Python 服务与 LuCI 总览、主题、设置、订阅四页。
配置模板在 service/etc/config；主屏幕工程在 ../overlay/overlay2.sGUI。

在路由器本目录执行 sh dev_install.sh --keep-config。详细依赖和迁移见 ../docs/迁移与部署.md。
主题页的方向、亮度、日夜时间及 WiFi 参数为全局设置；订阅参数分别保存。
屏幕映射由 displaydash-screen 管理，目前不支持读取隐藏代码自动匹配。

build.sh 和 build-apk.sh 保留为历史构建脚本，本次没有构建或验证 APK 兼容性，使用源码安装。
测试：python -B test_regressions.py；node test_subscription_view.js。
