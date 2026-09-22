# HF028 迁移实验环境

2026-09-21：已完成 BIOS 兼容启动、隔离网络、8 GB 根文件系统修复扩容、运行时依赖安装、`clean-system` 快照和实体屏 DisplayDash 验证。EFI 启动仍受本机 VirtualBox 固件异常限制；配置备份恢复和真实热点扫码不作为已完成项目。

## 已创建环境

- VirtualBox 7.2.6；虚拟机 HF028-Migration-Lab。
- UUID：297ca146-0f2f-4569-a871-4c635d5d169f。
- 目录：D:\VirtualBox VMs\HF028-Migration-Lab。
- BIOS、2 核、2048 MB；system.vdi 为由项目 IMG.GZ 转换并扩展至 8 GB 的动态磁盘。
- GPT 备份表和 ext4 已在救援 ISO 中离线修复，根文件系统约 7.9 GB。
- 网卡一：现有 Host-only；网卡二：NAT。客体管理地址为 192.168.56.215，LAN DHCP 已关闭。
- UART1 当前为 TCP 控制台 127.0.0.1:2301；UART2（0x2F8/IRQ3）映射宿主 COM4。
- COM4 发送 GET_ADDR 后收到 GETADDR 与 OK，物理通信初检通过。

## 阻塞证据

EFI 输出 X64 Exception Type 0D (#GP - General Protection)，定位至 VirtualBox EFI CpuDxe。
尚未进入 ImmortalWrt 内核，不能归因于 DisplayDash 或认定系统镜像损坏。
日志显示使用 NEM 后端；此为环境事实，尚未确认它是异常原因。
日志还出现全局共享目录 E:\share 不存在的非致命提示，未修改该全局设置。
证据保存在 evidence/efi-console.log 和 evidence/VBox.log。

## 当前状态与未完成项目

ISO 已在 BIOS 模式启动并用于离线修复。依赖、源码、HomeProxy 测试订阅和实体屏已验证；Alpha/Bravo 切换、方向 `DIR(1)`、管理地址二维码以及二维码不重复重绘均有日志证据。原路由器及 Windows 安全设置未修改。

尚未标记为完成的项目是：从 `clean-system` 快照重新部署并恢复备份的完整闭环，以及真实热点扫码联网。无真实热点时只能验证 WiFi QR payload 的转义和格式。

兼容性问题解决后继续既定计划；已生成磁盘与虚拟机保留，无须重新转换。
可用下面命令查看环境；启动会重新占用 COM4，先关闭 sGUI 串口：

```powershell
& 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' showvminfo HF028-Migration-Lab
& 'C:\Program Files\Oracle\VirtualBox\VBoxManage.exe' startvm HF028-Migration-Lab --type headless
```

完整的逐步命令、串口交接和扩容排错记录见 `docs/迁移与部署.md`。不自动关闭 Hyper-V、VBS 或其他安全功能。
