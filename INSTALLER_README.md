# Audio2Phira 中文一键环境安装

将完整项目解压到有写入权限的本地目录，然后双击 **Setup.vbs** 打开中文安装界面（不显示控制台）；也可双击 **Setup.cmd** 查看启动诊断。路径可以包含中文和空格。请不要只复制启动器，需保留同目录的 `installer_gui.ps1`、`install_environment.ps1` 和项目文件。

界面使用 Windows 自带的 **Windows PowerShell 5.1 + WinForms**，打开安装器不需要预装 Python，也不会自动下载或安装内容。默认无需管理员权限；建议放在个人可写目录，避免 Program Files 等受保护位置。

## 使用

1. 关闭 Audio2Phira 和正在使用项目环境的终端或程序。
2. 点击 **安装 / 修复环境**。普通安装会检查并复用健康的现有环境；安装引擎负责准备 **Python 3.12 x64** 和项目制谱、音频分析、桌面运行所需依赖。
3. 观察实时日志，等待显示“操作成功（退出码 0）”。首次安装通常需要联网，下载速度会影响耗时。
4. 成功且 `.venv\Scripts\pythonw.exe` 存在后，**打开 Audio2Phira** 按钮才会启用。它使用项目虚拟环境的 `pythonw.exe` 启动 `desktop_app.py`。

本工具不安装 Phira 游戏，不下载歌曲，也不自动导入谱面。

- **检查环境**：只调用安装引擎的 `-CheckOnly`，检查环境是否可用；不会附加 `-Repair`。检查成功同样可以启用打开应用按钮。
- **离线模式**：附加 `-Offline`。仅在本机 Python 和依赖缓存足够完整时才能成功；不完整时请取消离线模式后重试。
- **强制重建环境**：默认不勾选，附加 `-Repair`。仅在确实需要重建时使用；界面会要求先关闭应用并确认，安装引擎应先备份旧 `.venv` 后重建，不直接删除旧环境。旧备份可能占用磁盘空间，请确认新环境正常后再自行处理。
- **打开日志目录**：打开项目下 `.setup\logs`，其中每次操作都有独立的 `*.stdout.log` 和 `*.stderr.log`。界面合并显示两路日志，跨通道顺序可能与实际发生顺序略有不同；原始文件保留各通道顺序。
- **关闭**：操作完成后可关闭。操作期间禁用关闭按钮，窗口右上角关闭也会提示等待；没有取消按钮，避免中断 Python 或依赖安装。请勿通过任务管理器强制结束。

失败时请查看两份日志，再重试或使用强制重建；失败不会解锁“打开 Audio2Phira”。若提示缺少安装引擎，请重新解压完整项目到同一目录。

## 已完成的验证与限制

- 当前项目普通安装：复用现有健康环境，不改包；创建桌面快捷方式。
- 隔离目录从空虚拟环境离线安装 28 个锁定依赖：通过版本、pip check、Tk 窗口及实际节拍检测检查。
- 故意移走一个离线包再强制重建：正确返回失败，保留失败环境并自动恢复原环境，恢复后健康检查通过。
- GUI / CMD 启动与成功、失败日志显示：通过。
- Python 3.12.10 x64 官方安装程序已经缓存并验证 SHA-256 和 Python Software Foundation 签名。**没有在这台已有 Python 的电脑上实际执行“完全无 Python”的安装分支**，因此这一路仍需在干净 Windows 机器上验证。

当前 `wheels` 已缓存完整依赖，约 130 MiB；`.setup/cache/python-3.12.10-amd64.exe` 约 26 MiB。转移到另一台 x64 Windows 电脑时需带上这些缓存和完整项目；只复制 Setup 启动器不够。离线系统若无法验证 Windows 数字签名，安装器会停止，不会绕过校验。

程序只在需要时安装用户级 Python，不设置系统 PATH。安装包固定为已经测试的版本，不是自动追踪最新版本。检查会产生诊断日志及必要的 Python 缓存，但不会安装或替换依赖。测试目录 `.setup/clean-test-*` 和重建备份仅用于验证/回退，不属于运行所必需的文件。

## 引擎接口

界面在独立进程执行以下命令，以项目目录为工作目录，不依赖当前终端位置：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<项目>\install_environment.ps1" -Root "<项目>"
# 根据所选操作追加：-CheckOnly、-Offline、-Repair
```

引擎标准输出和标准错误应使用 UTF-8；退出码 0 表示成功，非 0 表示失败，不需要结构化结果。界面通过 .NET 异步流复制将输出写入日志文件，用 WinForms 定时器读取不断增长的 UTF-8 文件并检查保存的 Process 对象的 `HasExited`。不在后台 PowerShell 脚本块中操作控件，不阻塞界面等待进程。

可用 `-Root` 为界面指定其他完整项目目录；缺省为界面脚本所在目录：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File .\installer_gui.ps1 -Root "D:\我的项目\Audio2Phira"
```

## 界面冒烟测试

在 Windows PowerShell 5.1 中运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File .\installer_gui.ps1 -SmokeTest
```

测试会构建、显示、刷新并关闭真实 WinForms 窗口，输出 `INSTALLER_GUI_SMOKE_TEST_OK`。它不会启动安装引擎、创建日志目录、联网或修改 Python 环境。此测试仅验证界面可启动，不代表安装引擎和应用已通过完整环境检查。

脚本以 UTF-8 BOM 保存，以确保 Windows PowerShell 5.1 正确显示中文。若编辑脚本，请保留该编码。
