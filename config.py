"""
audio2pez — 音频到 PhiraEdit 谱面生成器
配置常量模块

基于 RPE (Re:PhiEdit) 格式 v140
"""

# ── 音频分析 ──────────────────────────────────────────
SAMPLE_RATE        = 22050          # 分析采样率
HOP_LENGTH         = 512            # STFT hop 长度
ONSET_SENSITIVITY  = 0.08           # onset 检测灵敏度 (越低越敏感, 默认~0.1)
BEAT_QUANTIZE      = 8              # 量化精度: 8 = 1/8 拍 (网格密度)
QUANTIZE_TOLERANCE = 0.050          # 量化容忍窗口 (秒)
GRID_DIVISION      = 4              # 节拍细分: 4 = 1/4 拍音符 (即16分音)
NOTE_MIN_STRENGTH  = 0.03           # onset 强度下限: 低于此值不放置音符

# ── 音符生成 ──────────────────────────────────────────
MIN_NOTE_GAP       = 1              # 相邻音符最小间隔 (1/16 拍单位)
MAX_POSITION_X     = 600            # 水平范围
MIN_POSITION_X     = -600

# 轨道定义: 模仿原谱 — 绝对不含中心轨道 (0 留给判定线)
# 原谱使用 -225, -75, 75, 225, 所有音符偏左或偏右
LANES = [-450, -300, -150, 150, 300, 450]          # 6 轨道, 无中心
LANES_4 = [-225, -75, 75, 225]                      # 原谱风格紧凑 4 轨道

# 频段划分 (Hz)
BAND_LOW           = [20,  250]     # 低频 → 底鼓/贝斯
BAND_MID           = [250, 2000]    # 中频 → 人声/钢琴
BAND_HIGH          = [2000, 11025]  # 高频 → 镲片/hihat

# 频段 → 首选轨道权重 (6轨, 左右各3, 中心为空)
LANE_WEIGHT_LOW    = [0.08, 0.17, 0.25, 0.25, 0.17, 0.08]  # 低频: 偏内但不重叠
LANE_WEIGHT_MID    = [0.16, 0.17, 0.17, 0.17, 0.17, 0.16]  # 中频: 均匀
LANE_WEIGHT_HIGH   = [0.25, 0.20, 0.10, 0.10, 0.20, 0.15]  # 高频: 偏外

# 音符类型概率 — Hold 优先 (延音检测驱动)
HOLD_PROB_SUSTAIN  = 0.70           # 检测到延音时 Hold 概率
HOLD_PROB_BASE     = 0.30           # 基础 Hold 概率 (无延音时)
HOLD_PROB_STRONG   = 0.50           # 强 onset + 延音时 Hold 概率
FLICK_PROB         = 0.12           # Flick 基础概率
DRAG_PROB          = 0.06           # Drag 基础概率

# 延音检测参数
SUSTAIN_THRESHOLD  = 0.08           # onset 强度阈值: 高于此值视为"持续"
SUSTAIN_MIN_FRAMES = 3              # 最少持续帧数 (约 70ms @ hop=512, sr=22050)
SUSTAIN_MAX_GAP    = 2              # 允许的短暂下落帧数

# onset 特征 → 音符类型
MAX_TAP_DURATION   = 0.10           # >100ms 的 onset 优先判为 Hold (秒)
HOLD_MIN_DURATION  = 0.25           # Hold 至少持续 0.25 秒
HOLD_MAX_BEATS     = 2.0            # Hold 最大持续拍数 (增加到2拍, 匹配长音)
HOLD_BEATS_TIER    = [0.25, 0.375, 0.5, 0.75, 1.0, 1.5, 2.0]  # Hold 可选的持续拍数

# ── 判定线特效 ──────────────────────────────────────────
INTRO_LINE_Y       = -400           # 开头判定线 Y 偏移 (下方)
INTRO_DURATION     = 8              # 开场动画持续拍数
INTRO_EASING       = 24             # 缓动类型: 24 = ease-out (先快后慢)

# ── 段落检测 ──────────────────────────────────────────
SECTION_WINDOW     = 8              # 分析窗口 (拍)
DENSITY_LOW        = 0.25           # 稀疏段落: 密度 < 25%
DENSITY_MID        = 0.55           # 中等密度: 25-55%
DENSITY_HIGH       = 0.85           # 高密度: >55% (副歌)

# ── 特效配置 ──────────────────────────────────────────
DEFAULT_SPEED      = 10.0           # 默认下落速度
DEFAULT_ALPHA      = 255            # 默认透明度
DEFAULT_SIZE       = 1.0            # 默认音符大小

# ── .pez 打包 ─────────────────────────────────────────
RPE_VERSION        = 140            # RPE 格式版本
OUTPUT_DIR         = "output"

# ── 难度预设 ────────────────────────────────────────
DIFFICULTY_PRESETS = {
    "easy": {
        "level_tag": "IN 8",
        "density_mult": 0.35,           # 只选取最强 35% onset
        "min_note_gap": 3,              # 最小间隔 3 格点 (更稀疏)
        "lanes": [-225, -75, 75, 225],  # 4 轨, 紧凑居中
        "tap_weight": 0.60,             # 音符类型目标占比
        "hold_weight": 0.10,
        "flick_weight": 0.20,
        "drag_weight": 0.10,
        "burst_prob": 0.05,             # 几乎不用爆发(双押)
        "stair_prob": 0.05,             # 几乎不用楼梯
    },
    "hard": {
        "level_tag": "IN 14",
        "density_mult": 0.70,
        "min_note_gap": 1,
        "lanes": [-450, -300, -150, 150, 300, 450],  # 6 轨
        "tap_weight": 0.45,
        "hold_weight": 0.15,
        "flick_weight": 0.25,
        "drag_weight": 0.15,
        "burst_prob": 0.45,
        "stair_prob": 0.25,
    },
}

# ── 模式库权重 ────────────────────────────────────────
# 不同节拍结构下各模式的选用概率
PATTERN_WEIGHTS = {
    "even":    {"stair": 0.25, "mirror": 0.10, "alternate": 0.30, "flow": 0.20, "random": 0.15},
    "syncopated": {"stair": 0.10, "mirror": 0.15, "alternate": 0.20, "flow": 0.10, "burst": 0.45},
    "sparse":  {"stair": 0.10, "mirror": 0.05, "alternate": 0.10, "flow": 0.60, "random": 0.15},
}
