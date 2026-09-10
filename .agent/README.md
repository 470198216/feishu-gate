# 本目录给 Cursor Agent 读

你要填三份（标题不要删，不需要的项写「无」或「待填写」）：

1. **environment.md**（从 `environment.example.md` 复制而来）  
   环境、IP、账号密码、启动命令。**含密码，不要提交 git。**
2. **acceptance.md**  
   怎么算测过、硬规则、回归命令。不要把密码写进来。
3. **shutdown.json**（从 `shutdown.example.json` 复制而来）  
   下班关机设备名单。飞书说「下班关机」并回复「通过」后，按这里的 IP 关机。  
   `os`：`kylin` 走 SSH（`shutdown -h now`）；`android` 默认走 ADB（`adb reboot -p`）。  
   `order` 小的先关，网关填大、放最后。`enabled` 必须是 `true` 才会关。

Agent 会先读环境记录和验收说明，再搭环境、测试、改代码。飞书回执里不会（也不应）出现密码。

Agent 会先读这两份，再搭环境、测试、改代码。飞书回执里不会（也不应）出现密码。

以后要加字段，保持标题编号，告诉我即可。
