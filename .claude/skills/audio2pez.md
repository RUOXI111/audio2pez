# audio2pez — 音频转 PhiraEdit 谱面生成器

从任意音频文件自动分析并生成 RPE v140 格式的 Phira 谱面 (.pez)。

## 项目位置

`rephiraedit`

## 使用方式

```bash
cd rephiraedit

# 基本用法 (默认 hard 难度)
python main.py <音频文件>

# 指定难度
python main.py <音频文件> --difficulty easy     # IN 8, 低物量
python main.py <音频文件> --difficulty hard     # IN 14 (默认)

# 仅检测 BPM
python main.py <音频文件> --bpm-only

# 自定义元数据
python main.py song.mp3 --bpm 140 --name "曲名" --level "IN 14" --charter "谱师" --offset 50
```

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `input` | 必填 | 音频文件 |
| `--bpm` | 自动 | 手动指定 BPM |
| `--name` | 文件名 | 谱面名称 |
| `--level` | 难度对应 | 难度标签 (默认随 difficulty) |
| `--charter` | auto-generated | 谱师名 |
| `--composer` | Unknown | 作曲者 |
| `--offset` | 0 | 音频偏移 (ms) |
| `--outdir` | output | 输出目录 |
| `--difficulty` | hard | easy / hard |

## 难度模式

| 特性 | Easy (IN 8) | Hard (IN 14) |
|---|---|---|
| 轨道 | 4 轨 (-225~225) | 6 轨 (-450~450) |
| 物量 | ~300-500 (5min曲) | ~700-1000 |
| 排列 | 交替/镜像/流水, 无爆发 | 全模式含双押 |
| Tap | ~60% | ~45% |
| Flick | ~20% | ~25% |
| Drag | ~10% | ~15% |
| Hold | ~10% | ~15% |

## 音符类型映射 (音乐驱动)

- **普通节拍音** (底鼓/旋律) → **Tap** — 中等 onset, on-beat
- **强重音** (军鼓/镲片) → **Flick** — onset>0.35 或高频强音
- **延音长音** (人声/弦乐) → **Hold** — onset 后持续 >150ms
- **滑动扫频** (合成器滑音) → **Drag** — 高频 + 短延音

## 关键技术细节

### 判定线配置 (必须正确, 否则非 Hold 音符居中)

`pez_packager.py` 中 `main_line`:
```python
"isCover": True,                                          # 必须 True
"posControl": [{"pos": 1.0, "x": 0}, {"pos": 1.0, "x": 9999999}],  # 固定 1.0
"yControl": [{"y": 1.0, "x": 0}, {"y": 1.0, "x": 9999999}],        # 固定 1.0
```

### 配置调整

编辑 `config.py`:
- `DIFFICULTY_PRESETS` — easy/hard 难度参数
- `NOTE_MIN_STRENGTH` — 提高 = 更少音符
- `ONSET_SENSITIVITY` — 提高 = 更少 onset

## 工作流程

1. **音频分析** → BPM/节拍/onset/频谱/段落
2. **谱面生成** → 节拍网格 → 选取最强 onset → 排列模式 → 音符类型分类
3. **构建 JSON** → RPE v140 格式
4. **打包 .pez** → JSON + MP3 + 封面图片

## 输出

```
output/
├── <曲名>.pez    ← 导入 Phira
└── <曲名>.json   ← 调试用
```
