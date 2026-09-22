# 串口转发工具

安装器和 hub4com 来源：https://github.com/vovsoft/com0com 。安装器文件名 signed 不表示安装器本身通过 Authenticode 验证。新电脑需安装驱动并验证兼容性。

先在路由器执行 displaydash-serial-bridge start，然后运行：

```text
start-displaydash-serial.cmd 100.105.214.93 CNCB1 2000
```

sGUI 选择配对应用端 COM11、115200。新电脑可能使用不同端口；按实际配对关系调整 CNCB1 和 COM11。
下载完成，关闭 sGUI 串口，然后运行：

```text
stop-displaydash-serial.cmd 100.105.214.93
```

默认地址是旧路由器 Tailscale IP，迁移时传入新地址。停止脚本仅结束本目录的 hub4com 并通过 SSH 恢复服务。
需要已可用的 SSH 登录，脚本不保存密码。PowerShell 脚本遵循本机执行策略。
