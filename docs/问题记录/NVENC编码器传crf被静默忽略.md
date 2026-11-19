# 问题：给 NVENC 编码器传 crf 被静默忽略

**TL;DR**：VideoHelperSuite 的 `nvenc_*` 格式定义里没有 `crf`，用的是 `bitrate` + `megabit`。

- 问题：用显卡编码器出片时设了 `crf`，输出体积和画质完全不受控，也不报错
- 根因：不同编码格式的输入项不同——`h264/h265-mp4` 用 `crf`，`nvenc_*` 用 `bitrate`（配合 `megabit` 布尔位表示 Mbps）
- 解决：批量脚本按格式分派——`-Format` 含 `nvenc` 时填 `bitrate` + `megabit`，否则填 `crf`
- 预防：新增编码格式前先看 `video_formats/<格式>.json` 里的字段定义