# 问题：Video2X 列设备用了旧版参数名

**TL;DR**：6.4.0 用 `--list-devices` / `-l` 列设备、`--device` / `-d` 选设备；`--list-gpus` 是旧版写法。

- 问题：安装脚本用 `--list-gpus` 做自检兜底，在 6.4.0 上报未知参数
- 根因：文档站部分页面停留在旧版命令行
- 解决：改用 `--list-devices`，并把该事实写进脚本注释
- 预防：**命令行参数以 tag 对应的 `argparse.cpp` 为准**