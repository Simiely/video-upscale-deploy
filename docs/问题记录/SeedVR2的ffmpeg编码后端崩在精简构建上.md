# 问题：SeedVR2 的 ffmpeg 编码后端崩在精简构建上

**TL;DR**：`inference_cli.py` 里写死了裸命令 `ffmpeg`（`shutil.which` 校验 + `subprocess.Popen(['ffmpeg', ...])` 编码），**只认 PATH**。PATH 上第一个往往是精简构建（`--disable-everything`，无 rawvideo、无 libx265），一跑就 `Unknown input format: 'rawvideo'` 崩溃；若换 opencv 后端则写成 MPEG-4 Part 2。

- 问题：批量脚本已探测出完整版 ffmpeg 路径，但 CLI 依然崩——因为"探测到"和"子进程能用上"是两件事
- 根因：CLI 不读任何"ffmpeg 路径"参数，只用 PATH 查找；本机实测 PATH 首个是 TRAE 自带的精简构建
- 解决：`Enable-FfmpegOnPath` 把完整版所在目录插到当前进程 PATH 最前面（只影响本进程及子进程），批量脚本启动时调用
- 预防：**涉及外部命令的探测，必须确认"子进程也拿得到"**。另外判断 ffmpeg 可用性不能只看 PATH 上有没有，要按能力探测（`-demuxers` 找 rawvideo、`-encoders` 找 libx265）