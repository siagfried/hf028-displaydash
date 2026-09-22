# HF028 DisplayDash 可迁移项目

当前维护源码为 `hf028-displaydash/`，屏幕主工程为 `overlay/overlay2.sGUI`。整理日期：2026-09-21。

| 路径 | 用途 |
| --- | --- |
| firmware/ | ImmortalWrt 25.12.1 ext4 EFI 整盘镜像、EFI ISO、SHA256SUMS |
| hf028-displaydash/ | Python 服务、LuCI、配置模板、源码安装和回归测试 |
| overlay/ | 当前屏幕工程及图片资源、早期界面示例 |
| HF028-QVGA-ST-04-V02 20251217/ | 厂商文档、工具链接、参考工程 |
| tools/com0com/ | Windows 虚拟串口驱动安装程序、TCP 转发工具 |
| hfd.py、selftest.py、app_example.py | 独立串口驱动及通信示例 |
| docs/迁移与部署.md | 安装、下载、配置迁移步骤 |
| docs/整理记录.json | 历史文件移出清单和归档位置 |

复制整个项目即可迁移源码、屏幕素材、工具及系统镜像。依赖仍需安装，原路由器运行配置需另行备份。
旧代码、旧安装包、制盘中间文件及整盘备份已移到项目外的历史归档；未重新打包 APK。

## 使用

1. 按 [迁移与部署](docs/迁移与部署.md) 安装系统和依赖。
2. 上传 hf028-displaydash 到路由器，在其目录执行 `sh dev_install.sh --keep-config`。
3. LuCI → 服务 → DisplayDash，核对总览、主题、设置、订阅四页。
4. sGUI 打开 overlay/overlay2.sGUI，连同图片资源下载到屏幕。

## 验证

```text
python -B hf028-displaydash/test_regressions.py
node hf028-displaydash/test_subscription_view.js
```

firmware/SHA256SUMS 用于复制完整性校验，不等同于发行方签名认证。项目不包含原机当前订阅、AP 凭据和 Tailscale 登录状态。
