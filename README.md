# audio2pez — 音频转 PhiraEdit 谱面生成器

将任意音频文件（.mp3 / .wav / .ogg / .flac）自动分析并生成 RPE 格式的 Phira 谱面（.pez）。

## 环境依赖

- Python 3.10+
- librosa
- numpy

```bash
pip install librosa numpy
```

## 快速开始

```bash
cd rephiraedit
python main.py <音频文件> [选项]
```

### 基本用法

```bash
# 最简单的用法：自动检测 BPM 并生成谱面
python main.py song.mp3

# 同时指定所有元数据
python main.py song.mp3 --bpm 140 --name "My Song" --level "IN 14" --charter "你的名字" --composer "作曲者"
```

### 仅检测 BPM（不生成谱面）

```bash
python main.py song.mp3 --bpm-only
```

## 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `input` | 位置参数 | 必填 | 输入音频文件路径 |
| `--bpm` | float | 自动检测 | 手动指定 BPM |
| `--name` | str | 文件名 | 谱面名称 / 曲名 |
| `--level` | str | `"IN 13"` | 难度标识 |
| `--charter` | str | `"auto-generated"` | 谱师名 |
| `--composer` | str | `"Unknown"` | 作曲者 |
| `--offset` | int | `0` | 音频偏移 (ms) |
| `--outdir` | str | `"output"` | 输出目录 |
| `--difficulty` | str | `"hard"` | 难度: `easy` (IN 8) / `hard` (IN 14) |
| `--bpm-only` | flag | — | 仅检测 BPM，不生成谱面 |

## 工作流程

程序分 4 步运行：

### Step 1: 音频分析

- **加载音频**：将文件重采样到 22050Hz 单声道
- **BPM 检测**：使用 librosa 的节拍跟踪算法自动检测
- **节拍检测**：定位每个拍子的时间点
- **Onset 检测**：多频带 onset 检测，定位所有音符起始点
- **频谱分析**：将音频分为低频(20-250Hz)、中频(250-2000Hz)、高频(2000Hz+)三个频段
- **段落检测**：基于 RMS 能量变化将歌曲分为 intro/break、verse、chorus 段落

### Step 2: 谱面生成

- 构建密集节拍网格（1/4 拍精度）
- 按段落分配音符密度（chorus 密集，intro 稀疏）
- 按 onset 强度排序选取最强音符
- 频段驱动轨道选择 + 延音检测驱动 Hold 比例
- 6 种排列模式随机组合：楼梯(stair)、对称(mirror)、交替(alternate)、流水(flow)、爆发(burst)、随机(random)

### Step 3: 构建 JSON

生成符合 RPE v140 格式的完整谱面 JSON，包含：
- BPM 列表
- 元数据（曲名、谱师、封面、难度等）
- 判定线配置（含开场动画）
- 全部音符数据

### Step 4: 打包 .pez

将以下文件打包为 ZIP 格式的 .pez 文件：
- 谱面 JSON
- 原始音频 MP3
- 封面图片（自动匹配同名 .jpg/.png）
- info.txt

## 输出文件

生成的文件位于 `output/` 目录：

```
output/
├── <曲名>.pez    ← 可直接导入 Phira 的谱面包
└── <曲名>.json   ← 单独谱面 JSON（便于调试）
```

## 封面图片

如果音频文件同目录下有同名的 `.jpg` / `.jpeg` / `.png` 文件，会自动作为封面打包。否则使用 1x1 黑色占位图。

## 配置说明

编辑 `config.py` 可调整以下参数：

### 音频分析

| 参数 | 默认值 | 说明 |
|---|---|---|
| `SAMPLE_RATE` | 22050 | 分析采样率 |
| `ONSET_SENSITIVITY` | 0.08 | onset 检测灵敏度（越低越敏感） |
| `BEAT_QUANTIZE` | 8 | 节拍量化精度 |
| `NOTE_MIN_STRENGTH` | 0.03 | 音符强度下限 |

### 音符生成

| 参数 | 默认值 | 说明 |
|---|---|---|
| `LANES` | [-450, -300, -150, 150, 300, 450] | 6 条轨道（无中心轨道） |
| `HOLD_PROB_SUSTAIN` | 0.70 | 检测到延音时 Hold 概率 |
| `HOLD_PROB_BASE` | 0.30 | 基础 Hold 概率 |
| `FLICK_PROB` | 0.12 | Flick 基础概率 |
| `DRAG_PROB` | 0.06 | Drag 基础概率 |

## 难度模式

| 特性 | Easy (IN 8) | Hard (IN 14) |
|---|---|---|
| 轨道数 | 4 轨 (-225~225) | 6 轨 (-450~450) |
| 物量 (5分钟曲) | ~300-500 notes | ~700-1000 notes |
| 排列模式 | 交替/镜像/流水 (无爆发) | 全模式 (含双押爆发) |
| Tap 占比 | ~60% | ~45% |
| Flick 占比 | ~20% | ~25% |
| Drag 占比 | ~10% | ~15% |
| Hold 占比 | ~10% | ~15% |

### 音符类型映射规则

基于音乐特征自动选择音符类型：

| 音频特征 | 检测方式 | 音符类型 |
|---|---|---|
| 普通节拍音 (底鼓、旋律音) | 中等 onset 强度, on-beat | **Tap** |
| 重音/强调音 (军鼓、镲片) | 强 onset (>0.35) 或高频重音 | **Flick** |
| 持续长音 (人声、弦乐) | onset 后延音 >150ms | **Hold** |
| 滑动/扫频音 (合成器滑音) | 高频 + 短延音 (70-150ms) | **Drag** |

```bash
# 生成不同难度
python main.py song.mp3 --difficulty easy   # IN 8, 4轨, 低物量
python main.py song.mp3 --difficulty hard   # IN 14, 6轨, 高物量
```

## 常见问题

### Tap/Flick/Drag 音符在游戏中全部居中？

已修复。判定线配置中 `isCover` 必须为 `true`，且 `posControl` 和 `yControl` 需保持恒定值（参考 `pez_packager.py` 中的 `main_line` 配置）。

### 音符太少或太多？

调整 `config.py` 中的 `NOTE_MIN_STRENGTH`（降低 = 更多音符）和 `ONSET_SENSITIVITY`（提高 = 更少 onset）。

### BPM 检测不准？

使用 `--bpm` 参数手动指定。

### 音频时长限制？

无硬性限制。但 5 分钟以上的歌曲建议将 `SAMPLE_RATE` 降到 16000 以加快分析速度。

## 示例

```bash
# 生成 song.mp3 的谱面（自动匹配同名封面 song.jpg）
python main.py song.mp3

# 自定义谱面信息
python main.py song.wav --bpm 128 --name "My Song" --level "IN 14" --charter "MyName"

# 指定输出目录
python main.py song.mp3 --outdir my_charts

# 偏移调整（用于音画同步）
python main.py song.mp3 --offset 50
```
