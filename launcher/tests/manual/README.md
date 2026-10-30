# 手动验证脚本（不参与 `unittest discover`）

`launcher/tests/` 下被 `discover` 自动跑的是**纯函数**用例（46 个，无 tkinter，0.6 秒）。
本目录放的是**必须真开窗口/真起进程**的两个冒烟脚本 —— 自动化跑不了，但也不能丢：

| 脚本 | 抓什么 | 前提 |
|---|---|---|
| `smoke_ui.py` | 真建 Tk + 真建 App，9 条断言（mixin 是否接上、清单 16 项、日志漏斗、体积口径）+ 截图 | 带 tkinter 的 Python；Pillow 可选 |
| `smoke_exe.py` | 启动 `dist/ComfyUI启动器.exe`，按**窗口标题**确认开窗、无崩溃日志 + 截图 | 先打包出 exe |

```bash
python launcher/tests/manual/smoke_ui.py     # 改完界面/拆完 mixin 就跑这个
python launcher/tests/manual/smoke_exe.py    # 发版前/打包后跑这个
```

截图落在系统临时目录（`launcher-smoke.png` / `launcher-exe-smoke.*`），不进仓库。

## 这两个脚本为什么必须在仓库里

- 2026-10-30 拆 `部署卡.py` 时，`import` 阶段一切正常，只有 App 实例化到部署卡才暴露问题；
- exe 冒烟踩了两个坑，重踩一遍要花很久：**PyInstaller 单文件是引导进程 + 子进程两段，
  按父 PID 枚举窗口永远是空**；**`PrintWindow` 抓 Tk 窗口是全黑的**，得先试一次、
  全黑再降级 `ImageGrab` 并置前。

两个坑的处置都写在脚本注释里，跑的时候会打印用的是哪种截图方式。
