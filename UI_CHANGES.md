# 界面改造说明 · 喵斯快跑风（MUSE POP）

参考《Muse Dash》的视觉语言重做了界面皮肤：糖果霓虹撞色 + 粗黑描边贴纸块 + 斜条纹/半调网点 + 描边粗体字 + 小恶魔系角色。

**核心逻辑零改动**：参数校验、任务派发、worker 进程管理、取消、结果校验全部保持原样，只替换视觉层。

---

## 1. 已部署位置

| 项目 | 路径 |
| --- | --- |
| 程序目录 | `D:\audio2pez\audio2pez\audio2pez\` |
| 主题层（新增） | `D:\audio2pez\audio2pez\audio2pez\anime_theme.py` |
| 改造后的界面 | `D:\audio2pez\audio2pez\audio2pez\desktop_app.py` |
| 原版备份 | `D:\audio2pez\audio2pez\audio2pez\.desktop\backup\desktop_app.py.orig` |

启动方式不变：双击桌面「Audio2Phira 本地制谱」快捷方式，或 `launch_desktop.vbs`。

## 2. 配色（Muse Dash 取色）
| 角色 | 色值 | 用在哪 |
| --- | --- | --- |
| 主背景 | `#170a28` | 窗口底 |
| 近黑描边 | `#0d0518` | 所有控件的 2–4px 粗边、锯齿边、标题描边 |
| 糖晶品红 | `#ff3d9a` | 选中标签页、主行动按钮、分组标签、进度条、描边 |
| 电光青 | `#22e0e6` | 输入框描边、表头、滚动条、衣领 |
| 柠檬黄 | `#ffe14d` | 徽标底、勾选框、状态条文字、底部霓虹线 |
| 毒紫 | `#9b5cff` | 普通按钮、未选中标签页 hover |
| 青柠绿 | `#a8ff3e` | 星光粒子 |

对照旧版：`#eef3f7` 浅蓝灰底 + `#087f83` 青绿强调 → 现在是深紫黑 + 粉青黄撞色。

## 3. 头图（150px）

自上而下：渐变（深紫 → 品红 → 粉）→ 右侧斜条纹警戒带 → 半调网点 → 左上双层圆环 → 左上速度线 → 左缘粉色竖条 → 亮黄平行四边形徽标（黑描边黑字）→ 30pt 粗描边主标题（白字 + 4px 近黑描边）→ 粉底黄边副标题条 → 小恶魔角色 → 底部锯齿边 + 亮黄霓虹线。

**小恶魔角色**：双马尾（紫粉挑染）、恶魔角（品红）、锯齿刘海、呆毛、斜挑眼（粉黄双色瞳 + 十字星高光 + 粗上睫毛）、锯齿嘴、条纹腮红、青色水手领 + 粉色领结、身后唱片圆盘。约 2.5 秒眨一次眼，只重画眼睛层。

**星光粒子**：18 个四角星/菱形，向上漂并左右摆动，品红/亮黄/电光青/青柠绿循环。

## 4. 控件样式要点

| 控件 | 做法 |
| --- | --- |
| 普通按钮 | 毒紫块 + 3px 近黑描边，hover 转粉、按下变品红 |
| 开始生成 | 品红块 + 4px 近黑描边 + 12pt 粗黑字，按下变柠檬黄（像街机按键） |
| 标签页 | 未选中深紫块 + 3px 描边；选中品红块 + 黄描边 + 黑字 + 底部 3px 外扩 |
| 输入框 / 下拉框 | 深紫底 + 2px 电光青描边，聚焦描边转黄 |
| 勾选框 | 选中是柠檬黄方块 + 黑勾 |
| 分组卡 | 3px 近黑描边，标题是品红底黑字的贴纸条 |
| 结果表格 | 深底，表头电光青 + 黑字，选中行品红 + 黑字 |
| 日志 | 近黑底 + 冰蓝等宽字 + 黄色光标 |
| 进度条 | 品红条 + 近黑槽 + 2px 描边 |
| 滚动条 | 13px 电光青 + 近黑槽，hover 变黄 |
| 系统标题栏 | DWM 深紫 + 黄色标题文字（Win10/11） |

## 5. `desktop_app.py` 改动（共 66 行，全部在视觉层）

1. 顶部 `import anime_theme as theme`
2. `_style()`：窗口标题、尺寸 `1200x880`（最小 `920x680`）、原 33 行配色/样式配置 → 一行 `theme.apply(self.root)`
3. `_build()`：头图换 `theme.AnimeHeader(...)`（徽标文案 `MUSE POP · LOCAL CHART LAB`）、body 内边距、标签页与按钮文案加装饰符号、日志 Text 主题色、状态栏 `Pill.TLabel`
4. `_scroll_tab()`：滚动画布底色
5. `_results()`：结果标题字体

`_make_job` / `_run_worker` / `_generate` / `_cancel` / `_kill_tree` / `_poll` / `_done` / `_validate_result` 等业务方法逐字节未改。

## 6. 验证记录

```
python desktop_app.py --smoke-test   → SMOKE_TEST_OK: Tk 8.6
python setup_healthcheck.py          → HEALTH_OK Python=3.12.10 NumPy=2.2.6 librosa=0.11.0 PyAV=19.0.2 Tk=8.6
python test_desktop_ui.py            → PASS UI generation and result display
                                       PASS cancel worker tree
                                       PASS worker error and controls restored
                                       UI TESTS PASSED
```

布局检查：全部控件在父容器内无溢出；头图 573 个 Canvas item，只有设计上越界的光晕、锯齿与飞出画面的粒子。

## 7. 回滚

```powershell
Copy-Item 'D:\audio2pez\audio2pez\audio2pez\.desktop\backup\desktop_app.py.orig' `
          'D:\audio2pez\audio2pez\audio2pez\desktop_app.py' -Force
Remove-Item 'D:\audio2pez\audio2pez\audio2pez\anime_theme.py'
```

## 8. 二次微调

| 想改什么 | 改哪 |
| --- | --- |
| 主色 | `anime_theme.py` 的 `class C`：`PINK` / `CYAN` / `YELLOW` / `PURPLE` |
| 描边粗细 | `_buttons` / `_entries` / `_notebook` / `_frames` 里的 `borderwidth` |
| 头图高度 | `desktop_app.py` 的 `theme.AnimeHeader(..., height=150)` |
| 标题描边宽度 | `_render` 里 `outlined_text(..., width=2)`，改 3 更粗、1 更细 |
| 角色位置 | `_chibi_geometry()` 返回 `(self._cw - 96, self._ch * 0.44, ...)` |
| 粒子数量 | `_spawn_petals` 的 `range(18)` |
| 斜条纹疏密 | `_render` 里 `skew_band(..., 16, 30, ...)` 两个数是条宽和间隔 |

## 9. 应用图标

`.desktop\app.ico` 已换成画的小恶魔像素头像，7 个尺寸（16 / 24 / 32 / 48 / 64 / 128 / 256），全部 PNG 压缩条目，由 `make_icon.py` 生成。

- 造型：深紫唱片圆底 + 品红恶魔角 + 紫发挑染 + 呆毛 + 锯齿刘海 + 斜挑眼（粉黄双色瞳 + 白色十字星高光）+ 条纹腮红 + 青水手领 + 粉领结。
- 小尺寸优化：睫毛、呆毛、嘴在 32px 以下会自动加粗到 2px，避免细线断成虚线；脸和角按可读性优先级放大了占比。
- 生效位置：窗口标题栏 / 任务栏用 `desktop_app.py` 里的 `iconbitmap(STATE / 'app.ico')`；桌面两个快捷方式（本地制谱、环境安装）的 `IconLocation` 指向同一个 ico；`install_environment.ps1` 新建快捷方式时也用它。
- 重新生成：`python make_icon.py D:\audio2pez\audio2pez\audio2pez`（会覆盖 `.desktop\app.ico` 并输出 `icon_preview.png`）。原图标备份在 `.desktop\backup\app.ico.orig`。

## 10. 分发压缩包

`D:\audio2pez\audio2pez.zip` 由 `make_dist.py` 生成，结构与最初收到的 `audio2pez.zip` 一致：顶层 `audio2pez/`，含 `.desktop` `.git` `.setup` `.venv` `__pycache__` `output` `songs` `wheels` 与全部根文件，可直接解压到其他电脑用 `launch_desktop.vbs` 启动。

唯一区别：排除了 `.setup\clean-test-4b73b2`（安装脚本的测试残留，613 MB，对使用者无用）、`.venv-backup-*` 和 `Phira`（游戏本体，不属于本工具）。

## 11. 安装器界面（installer_gui.ps1）

WinForms 窗口换成同一套 Muse 配色，逻辑一行未动。

- **头图**：自绘 Panel —— 深紫→品红线性渐变 + 倾斜警戒条纹 + 底部黄/黑双线 + 左侧粉色竖条 + 19pt 描边标题（4px 近黑描边）+ 黄色小徽标 + 右侧 84px 角色头像
- **按钮**：安装/修复 = 品红底黑字 3px 黑边，hover 转亮粉、按下转黄；检查环境 = 毒紫；页脚三个分别是青 / 深紫 / 深紫
- **复选框**：深色底，离线模式青色字、强制重建粉字，粗体
- **状态条**：深紫卡片底 + 黄字粗体
- **日志框**：近黑底 + 冰蓝等宽字，滚动条通过 `SetWindowTheme(..., 'DarkMode_Explorer', ...)` 走深色
- **窗口图标**：`.desktop\app.ico`；标题栏走 DWM 深色（与主程序一致）
- **DPI**：`SetProcessDPIAware` + 按 DPI 缩放所有像素尺寸，125% 缩放下不再整窗发虚

四个坑和处理：

1. PS 5.1 解析器不认 `New-Object System.Drawing.Size((Px 900), (Px 712))` 这种嵌套表达式，改成 `[Type]::new(...)`，并封装 `Sz` / `Pd` 两个辅助函数统一换算。
2. 脚本必须存成 **UTF-8 with BOM**，否则 PS 5.1 按 ANSI 读中文，全角标点被当成引号，整段语法崩掉。
3. `.NET Framework` 的 `System.Drawing.Icon` 只认 BMP 条目，所以 `app.ico` 里 16/24/32/48/64 改成 BMP 编码，128/256 保留 PNG；安装器横幅改用新增的 `.desktop\app.png`（256px）。
4. 所有 `New-Object ...(...)` 的糖语法在带计算参数时必须显式构造，否则第一次 `ClientSize` 就报 `Unexpected token`。

验证：

```
powershell -File installer_gui.ps1 -Root . -SmokeTest
→ INSTALLER_GUI_SMOKE_TEST_OK
```

另外用 `PrintWindow` 抓真实窗口位图核对过配色：BG 367k / 卡片 68k / 品红 11k / 黄 3.8k / 青 8.3k / 毒紫 6.9k 像素，标题白字 3653、状态黄字 2567、复选框两类文字均有渲染。
