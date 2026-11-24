# 从另一台电脑连接出片主机

什么时候读：剪辑、写提示词在一台电脑上，出片在另一台 Windows 主机上，需要从前者远程操作主机、取回成片或访问主机上的网页界面时。出片和剪辑在同一台机器上，可以跳过本文。

只写方法，地址和账号都用占位符。对应 `config.yaml`：`host.ssh`（SSH 别名或 `用户@地址`）、`host.comfyui_url`、`host.queue_dir`、`host.comfyui_output`。

## 方式一：SSH（作者已验证，macOS 连 Windows，密钥免密登录）

**准备（通用做法，作者没有记录过这部分的细节）：**
1. 两台电脑都装 Tailscale 并登录同一个账号（同一个 tailnet）。`tailscale ip -4` 查主机的 Tailscale 地址，或用它的 MagicDNS 名。同一个局域网内也可以直接用局域网地址。
2. 主机上启用 Windows 的 OpenSSH Server，服务设为自动启动，防火墙放行 22 端口。
3. 把你的公钥放到主机上。管理员账号的公钥通常要放在 `C:\ProgramData\ssh\administrators_authorized_keys`，并收紧文件权限，否则免密登录不生效。

**客户端 `~/.ssh/config`：**

```text
Host <host.ssh 里的别名>
  HostName <主机的 Tailscale 地址或 MagicDNS 名>
  User <主机的 Windows 用户名>
  ServerAliveInterval 15
```

### 容易踩的事（都是作者踩过的）

- **默认 shell 是 Windows PowerShell 5，不是 cmd。** `&` 连接符、`%VAR%` 都不能用，用 `;` 和 `$env:VAR`。
- **中文输出是乱码：** 先执行 `[Console]::OutputEncoding=[Text.Encoding]::UTF8`。
- **命令里引号层数多时，直接写成脚本文件，`scp` 过去再执行，**比转义可靠得多。
- **SSH 会话里启动的进程会随会话结束被杀掉，**不能用它直接常驻启动服务。常驻服务从桌面快捷方式启动；要从远程启动一个长跑进程（比如出片队列），用 WMI 创建进程，它脱离会话，会话断了也继续跑（作者通宵出片一直这样用，已验证）：

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = "cmd /c <python 路径> -u <仓库>\scripts\drama_queue.py run > <host.queue_dir>\queue.out 2>&1" }
```

- **链路带宽有限。** 作者的链路直连时约 300 KB/s 到数 MB/s。几十 MB 以上的文件先在主机上处理（截帧、转码、拼接），只把结果拉回来。
- **长任务加 `-o ServerAliveInterval=15`，**并让脚本把结果写到主机上的文件里。连接断了，依赖这个会话的任务也会跟着停，结果文件能告诉你停在了哪。
- 取回成片：`scp -q -o BatchMode=yes <host.ssh>:<host.comfyui_output>/... .`

### 不改任何配置，在本机用主机上的网页服务

```bash
ssh -N -L 8188:127.0.0.1:8188 <host.ssh>
```

之后本机的 `http://127.0.0.1:8188/` 就是主机上的 ComfyUI（端口按 `host.comfyui_url` 填）。要同时转发本地文本模型，多加一个 `-L`，端口按你的文本服务来。手机等不方便用 SSH 的设备用方式二。

主机上直接调接口（在 SSH 会话里）：

```powershell
(Invoke-RestMethod "<host.comfyui_url>/system_stats").devices
```

## 方式二：Tailscale Serve（步骤来自文档，作者没有在自己的机器上启用，未验证）

先想清楚安全：本地文本模型服务通常没有 API key；ComfyUI 的入口可以上传文件、操作队列。**启用前确认 tailnet 的访问控制只把这些端口开给你自己的设备，不要开到公网。**

文本服务会检查请求的 Host。先在它的配置里把主机的完整 MagicDNS 名加进允许列表（取自 `tailscale status --json` 里 `Self.DNSName`，去掉末尾的点），重启服务，再执行：

```powershell
tailscale serve --bg --https=<外部端口 A> http://127.0.0.1:<文本服务端口>
tailscale serve --bg --https=<外部端口 B> http://127.0.0.1:<ComfyUI 端口>
tailscale serve status
```

远端用 `https://<主机完整域名>:<外部端口 A>/v1` 接文本服务（key 填任意占位值），用 `https://<主机完整域名>:<外部端口 B>/` 开 ComfyUI。首次使用按提示启用 HTTPS 证书。

| 现象 | 检查 |
|---|---|
| 域名解析失败或超时 | 两端在线、MagicDNS 开启；`tailscale ping <主机名>`；访问控制是否放行该端口 |
| 502 | 在主机上直接访问服务的健康检查，确认服务在跑、端口与 Serve 的上游一致 |
| 403、Host 或 Origin 报错 | 用 Serve 打印的完整域名；核对允许列表并重启服务 |
| ComfyUI 页面能开但队列不刷新 | 浏览器网络面板里看同源 `/ws` 的 WebSocket 是否连上 |

撤销：`tailscale serve --https=<外部端口> off`。主机睡眠或服务进程退出时，远端无法使用；通宵出片前把主机的睡眠关掉。
