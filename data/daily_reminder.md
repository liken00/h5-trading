每日 8:30 提醒用户（管理员） 9:25 之前手动选股

提醒内容：
1. 今日是否交易日（节假日跳过）
2. 9:25 前需完成的步骤
3. 选股后给我5 只 + 战法依据的格式
4. 提醒自动运行（Flask 后端 + OpenClaw cron）

执行:
  每天 8:30 触发（节假日判断在 prompt 里）
  发到飞书 DM (用户（管理员）自己的 chat_id)
  备用：生成日志文件供查看

依赖:
  - Hermes cron 工具（已装）
  - 飞书 bot 已配（<YOUR_FEISHU_APP_ID>）
  - chat_id: <YOUR_FEISHU_CHAT_ID>
