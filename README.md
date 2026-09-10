# feishu-gate

飞书长连接通道：先原样回一句证明活着，再切到工单入队。

我无法登录你的飞书账号，机器人必须在开放平台由你点创建。下面按这个顺序做：**先创建应用 → 填 `.env` → 启动本程序 → 再保存「长连接」事件**（飞书要求保存长连接时，本地程序必须已经在线）。

---

## 1. 创建飞书机器人（你点，大约 10 分钟）

1. 手机安装飞书，用手机号注册。电脑也登录同一个账号。
2. 若还没有团队：飞书里创建一个免费团队，只有你自己即可。
3. 打开 [飞书开放平台](https://open.feishu.cn/app) ，右上角登录。
4. **创建企业自建应用**（不要选商店应用）。名称例如 `值班闸门`。
5. 左侧 **添加应用能力** → 添加 **机器人**。
6. **权限管理** 打开并申请：
   - `以应用身份发消息`（`im:message:send_as_bot`）
   - `获取用户发给机器人的单聊消息`（`im:message.p2p_msg` 或只读版）
7. **凭证与基础信息**：复制 **App ID**、**App Secret**。
8. **版本管理与发布** → 创建版本 → 可用范围选 **只有你自己** → 发布。你是管理员则自己通过。

先不要配「把事件推到某个 https 网址」。长连接在第 3 步启动程序之后再保存。

---

## 2. 在这台 Windows 上启动（先启动，再回调后台）

```powershell
cd C:\Users\wenjin\Desktop\wwjfiles\feishu-gate
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
notepad .env
```

把 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 填进去，保存。然后：

```powershell
.\.venv\Scripts\feishu-gate.exe
```

窗口里出现长连接相关日志（connected / 启动）后，**不要关这个窗口**。

回到开放平台，打开这个应用：

1. **事件与回调** → **事件配置** → 订阅方式选 **使用长连接接收事件** → 保存（此时本程序必须在跑）。
2. 添加事件：**接收消息** `im.message.receive_v1`。
3. 若提示要再发一版，再发一个小版本。

---

## 3. 证明通道活着

飞书客户端搜索机器人名称（或用 `https://applink.feishu.cn/client/bot/open?appId=你的AppID`），发一句：

```
ping
```

机器人应原样回 `ping`。这就是 echo 模式。

---

## 4. 工单 + 只读工人

`.env` 里保持 `FEISHU_MODE=jobs`。关掉旧窗口再启动 `feishu-gate.exe`。

- 发「N80-B 通不通」或「B3 又灰了」：先回工单号，再查 `TOPOLOGY_STATUS_URL`（默认 `http://192.168.1.107:8080/api/status`），把通/灰推回飞书。
- 发「给拓扑加按钮」：只入队，`risk=write`，还不会改代码。
- 发无关闲聊：回「暂无只读工人认领」。

麒麟上的拓扑网页要在跑，否则会回「拓扑服务连不上」。

---

## 5. 写入两道闸（接到项目）

飞书发写入任务会先收到【审核卡】，**不会立刻改文件**。通过后工人按项目手册搭本地环境、测试、分析、改代码，再发【验收卡】。你回 **确认** 才留下改动；**驳回** 会还原这次改动。全程不 git commit / push。

指定仓库：

```
改拓扑：给页面加导出按钮
改机器人：加一条确认口令
```

不写前缀时：提到「拓扑/心跳」走拓扑仓，提到「机器人/闸门」走本仓；都没有则默认拓扑，审核卡会写明。

- 回复 `通过`：开工（只对【审核卡】有效）
- 回复 `确认`：收下【验收卡】里的改动
- 回复 `驳回` 或 `驳回：原因`：取消待审，或还原已改完待验收的工作区
- 多单时：`通过 job-xxxx` / `确认 job-xxxx` / `驳回 job-xxxx`
- `删除全部数据` 这类 destroy：通过也只归档，不会真执行

### 下班关机

飞书发「下班关机」会出【审核卡】，列出 `.agent/shutdown.json` 里 `enabled=true` 的设备。回复 **通过** 才会关机。

- 麒麟 / Linux：SSH 执行 `shutdown -h now`（可填密码或 `key_path`）
- 安卓：ADB `adb connect IP:端口` 再 `adb reboot -p`
  - 本机把 `platform-tools` 目录加入用户 PATH，或在 `shutdown.json` 写 `adb_path` 指向 `adb.exe`
  - PATH 加的是**文件夹**，不是 `adb.exe` 本身；改完 PATH 后必须新开窗口并重启 `feishu-gate`
  - 设备要开 USB 调试 / 无线调试，且这台电脑能访问那个 IP
- `order` 小的先关，**网关填大、放最后**
- 密码不会出现在飞书回执里

先编辑 `feishu-gate/.agent/shutdown.json`（已 gitignore）。`删除/格式化` 仍然不会真执行。

`CURSOR_API_KEY` 可写在 `feishu-gate/.env`，不写则自动用 `cursor-lan/.env` 里那把。启动窗口会打印两个项目路径和 `key=已配` 或 `缺失`。

改代码可能要几分钟。同时只跑一单 Agent。拓扑本机自测用 `--http-port 18080`，不要去占麒麟的 8080。

每个仓库有一份给 Agent 读的填写大纲（你填，工人读）：

- `topology-heartbeat-viewer/.agent/environment.md` 与 `acceptance.md`
- `feishu-gate/.agent/environment.md` 与 `acceptance.md`

`environment.md` 含账号密码，已 gitignore；大纲在 `environment.example.md`。标题不要删，不需要的项写「待填写」或「无」。以后要加字段直接说。

改完代码后必须：**关掉旧 feishu-gate 窗口再开**（长连接同时只能一个进程）。

---

## 常见卡住

| 现象 | 处理 |
|---|---|
| 搜不到机器人 | 可用范围没包含你，或版本没发布 |
| 能发但没回 | 程序没开；或长连接没保存成功；或没订 `im.message.receive_v1` |
| 保存长连接失败 | 先把本程序跑起来再点保存 |
| 权限被拒 | 权限变更后要重新发版 |

不要把 `.env` 发到聊天或提交 git。
