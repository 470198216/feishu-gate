# feishu-gate（Agent 手册）

飞书长连接闸门：聊天入队、只读探测、写入两道闸（通过才开工，确认才收下改动）。

开工前必读：

- `.agent/environment.md`（没有则 `environment.example.md`）
- `.agent/acceptance.md`

按环境记录搭环境，按验收说明测试。不要改 environment.md 里的账号密码，不要把密码写进回执。

## 本地测试

用仓库里已有的 `.venv` 跑测试，不要另起一个 `feishu-gate.exe`（长连接同时只能一个进程）：

```
.\.venv\Scripts\python.exe -m pytest
```

## 禁区

- 不要改 `.env` 和密钥
- 不要 git commit / push
- 不要把密钥写进代码或聊天回执


用仓库里已有的 `.venv` 跑测试，不要另起一个 `feishu-gate.exe`（长连接同时只能一个进程）：

```
.\.venv\Scripts\python.exe -m pytest
```

## 禁区

- 不要改 `.env` 和密钥
- 不要 git commit / push
- 不要把密钥写进代码或聊天回执
