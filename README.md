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

## 4. 接到工单

通道确认后，把 `.env` 里改成：

```
FEISHU_MODE=jobs
```

重启 `feishu-gate.exe`。再发一句，会回工单号，并追加到 `data/jobs.jsonl`。  
`risk` 目前是按关键字猜的：普通询问 = read，含「改/部署」= write，含「删除/关机」= destroy。后面再接到真正的工人。

可选：把你的 `open_id` 填进 `FEISHU_ALLOW_OPEN_IDS`，只让你一个人能下任务。可在飞书收到的第一条 jobs 回执对应的 jsonl 里看到 `user`。

---

## 常见卡住

| 现象 | 处理 |
|---|---|
| 搜不到机器人 | 可用范围没包含你，或版本没发布 |
| 能发但没回 | 程序没开；或长连接没保存成功；或没订 `im.message.receive_v1` |
| 保存长连接失败 | 先把本程序跑起来再点保存 |
| 权限被拒 | 权限变更后要重新发版 |

不要把 `.env` 发到聊天或提交 git。
