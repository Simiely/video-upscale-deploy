# 04-VisualEnhancer · DLSS 5 视觉增强启动器（非 ComfyUI）

**方案四**：面向 [Merserk Visual Enhancer](https://github.com/Merserk/dlss5-visual-enhancer) 的桌面部署助手。
它不依赖 ComfyUI、不占显存，跟前面三套方案的定位不同——前三套做「超分/修复」，
这一套做「神经渲染 + DLSS SR + RTX VSR」的实时增强，适合边看边调、快速预览。

本目录只放 **VEHelper**（下载 + 安装 + 启动的图形界面），官方程序本体由它下载到
`D:\Tool\VisualEnhancer`（可在界面里换目录），**仓库不含任何官方二进制**。

---

## 怎么用

```powershell
# 源码直接跑（调试用）
python .\04-VisualEnhancer\VEHelper.py

# 或下载 Releases 里的 VEHelper.exe 双击
```

界面只有三件事：

| 按钮 | 行为 |
|---|---|
| 选择目录 | 深色自绘目录选择器，改安装位置并写入 `ve_helper_config.json` |
| 下载并安装最新版 | 查 GitHub 最新 Release → 16 段并行下载 → 校验 → 解压到目标目录 |
| 启动官方 GUI | 拉起目标目录里的 `Visual Enhancer.exe` |

启动时会自动识别目录里是否已装（状态行显示「已安装」和版本号）。

**配置文件**：`ve_helper_config.json` 固定写在 exe 旁边（源码运行时写在同级目录），
只存一个键 `ve_dir`，默认 `D:\Tool\VisualEnhancer`。删掉即恢复默认。

**日志**：`%LOCALAPPDATA%\VEHelper\logs\vehelper.log`，滚动保留 3 份。

---

## 下载链路

1. **查最新版**：读 `github.com/Merserk/dlss5-visual-enhancer/releases.atom` 拿 tag，再读
   `releases/expanded_assets/<tag>` 拿资产名。**不走 REST API**——未认证只有 60 次/小时。
2. **分段**：按远端总大小切 16 段，`curl.exe -r` 并行拉取，每段独立文件。
3. **续传**：分段计划写在 `.parts/plan.json`（tag / 资产名 / 总字节数）。中断后重开，
   只有三者都与当前版本一致才续，否则整计划重置，避免拼出错包。
4. **合并**：全部段完成后按顺序拼接、删除 `.parts`，再交给解压安装。
5. **镜像回退**：`gh.llkk.cc` → 直连 → `ghproxy.net`，任一源失败自动换下一个。
6. **代理**：启动下载时内部探测 `7890 / 7891 / 10809 / 1080`，**不在界面显示、不单独占线程**；
   这只是兜底——GitHub 的 atom 通常能直连，资产直连不稳定时才用得上。取消下载会终止全部 curl 子进程。

---

## 模型为什么下不了

官方 GUI 里 VisionNext / SharpNext / MoGe-2 三个模型需要作者的 Hugging Face 私有仓库权限
（匿名请求 401，作者页也没有公开副本），程序没有 token 输入口，命令行版会一直停在
`Waiting for connection`。**结论：没有合法 token 就下不了，别在这个方向做下载器。**

好消息是这三颗模型只影响「模型加载」相关功能；神经渲染、DLSS SR、RTX VSR 都不需要它们，
所以主流程可以直接用。

---

## 代码结构

```
VEHelper.py             # 入口，只有三行：把 main 交给下方包
vehelper/
├── app.py              # 主窗口 + 控制器：只做事件编排、队列回主线程、UI 更新
├── ui.py               # 色板 / 深色标题栏 / 深色按钮 / 深色消息框 / 目录选择器
├── downloader.py       # 纯函数：分段计划、续传校验、合并；外壳：curl 并行下载
├── release.py          # GitHub 版本查询（atom + expanded_assets）、代理探测
├── installer.py        # 解压与定位 Visual Enhancer.exe
├── config.py           # 读写 ve_helper_config.json
└── errors.py           # 异常类型：ReleaseError / DownloadError / InstallError
tests/                  # 17 项 unittest，纯函数优先
```

依赖方向单向：`app → (ui, downloader, release, installer, config)`，
底层模块之间只共享 `errors`。`downloader` 与 `release` 的解析/计划部分是纯函数，
测试不需要网络。

**线程模型**：UI 只活在主线程；版本查询与下载各起一个 daemon 线程，结果统一走
`queue.Queue`，主线程 `after()` 轮询消费。关窗时置 `stop_event` 并 `downloader.cancel()`。

---

## 打包

```powershell
cd .\04-VisualEnhancer
python -m PyInstaller --clean --noconfirm VEHelper.spec
# 产物：dist\VEHelper.exe（单文件、无控制台、UPX 关闭）
```

`VEHelper.spec` 用 `collect_all("sv_ttk")` 带上主题资源。

> **打包前先清环境变量**：若当前终端里有外部程序留下的 `TCL_LIBRARY` / `TK_LIBRARY`，
> PyInstaller 会判定「tkinter installation is broken」并把 tkinter 整个排除，
> 打出来的 exe 一启动就报 `No module named 'tkinter'`。构建前先
> `Remove-Item Env:TCL_LIBRARY, Env:TK_LIBRARY`，再确认 `--log` 里出现
> `pyi_rth__tkinter.py`。

---

## 测试

```powershell
cd .\04-VisualEnhancer
python -m unittest discover -s tests -v
```

覆盖：分段计划覆盖与边界、合并、续传字节统计、Plan JSON 往返、atom/资产名解析、
解压与 exe 定位、代理探测失败返回空。当前 **17 项全绿**。

---

## 已知限制

- 官方程序更新后若改了 Release 资产命名规则（不再是 `Visual.Enhancer.vX.Y.zip`），
  资产匹配会失败——`release.parse_asset` 的兜底是取 tag 名包含的 zip。
- 没有自动更新提示：启动时只显示「检测到最新版」，实际替换要手动点下载。
- 只支持 Windows；`Visual Enhancer.exe` 的路径由解压结果决定，找不到会明确报错。
