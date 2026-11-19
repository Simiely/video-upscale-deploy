# 问题：上游 README 写了 CLI 参数，代码里却没有

**TL;DR**：`--allow_vram_overflow` 出现在 SeedVR2 仓库 README 的「Performance Optimization」一节，但 v2.5.24 的 `inference_cli.py` 没实现它，传了直接报错退出。

- 问题：照 README 给批量脚本加了 `--allow_vram_overflow`，SeedVR2 启动即以 `unrecognized arguments` 退出
- 根因：上游文档比代码超前。入口用的是 `parser.parse_args()` 且 `allow_abbrev=False`，未知参数不会静默忽略
- 解决：从批量脚本移除该参数
- 预防：**以代码为准，不以文档为准**。改 SeedVR2 参数前先跑 `inference_cli.py --help`（命令见 [AGENTS.md](../../AGENTS.md)）