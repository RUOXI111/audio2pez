# -*- coding: utf-8 -*-
"""可选的 Gradio 网页界面；核心逻辑见 generate.py。依赖 gradio（可选）。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate import generate


def _run(audio, cover, title, artist, charter, tier, all_tiers, density, line_fx,
         pulse_style, deco_when, main_y, mix_spec, key_mode, main_swing,
         tap_weight, hold_weight, flick_weight, drag_weight, nt_custom):
    if audio is None:
        raise ValueError("请先上传音频文件。")
    out = generate(
        audio_path=audio,
        difficulty=tier,
        all_tiers=bool(all_tiers),
        image_path=cover,
        title=(title or "").strip() or None,
        artist=(artist or "").strip(),
        charter_name=(charter or "").strip() or None,
        outdir=str(Path(__file__).parent / "output"),
        density_mult=float(density),
        line_fx=line_fx,
        pulse_style=pulse_style,
        deco_when=deco_when,
        main_y=float(main_y),
        mix_spec=(mix_spec or "").strip(),
        key_mode=key_mode,
        main_swing=bool(main_swing),
        tap_weight=(float(tap_weight) if nt_custom else None),
        hold_weight=(float(hold_weight) if nt_custom else None),
        flick_weight=(float(flick_weight) if nt_custom else None),
        drag_weight=(float(drag_weight) if nt_custom else None),
    )
    return list(out["results"].values()), out["log"]


def build_demo():
    import gradio as gr
    with gr.Blocks(title="audio2pez · 音频转 Phira 谱面") as demo:
        gr.Markdown("# audio2pez · 音频转音游谱面（Phira / Phigros .pez）\n"
                    "上传音频，自动检测音符并按难度分级排布成可直接导入 Phira 的 .pez。")
        with gr.Row():
            with gr.Column(scale=1):
                audio = gr.Audio(sources=["upload"], type="filepath", label="音频文件")
                cover = gr.Image(sources=["upload"], type="filepath", label="封面/背景（可选）")
            with gr.Column(scale=1):
                title = gr.Textbox(label="曲名", placeholder="留空则用文件名")
                artist = gr.Textbox(label="曲师 / Artist", placeholder="Unknown")
                charter = gr.Textbox(label="谱师 / Charter", placeholder="audio2pez")
                tier = gr.Dropdown(
                    choices=[("简单 EASY","easy"),("普通 NORMAL","normal"),("困难 HARD","hard"),
                             ("专家 EXPERT","expert"),("大师 MASTER","master")],
                    value="hard", label="难度分级",
                )
                all_tiers = gr.Checkbox(value=False, label="同时输出全部难度（打包 5 档）")
                key_mode = gr.Dropdown([("自动 Auto","auto"),("2K 双轨","2k"),("4K 四轨","4k"),("6K 六轨","6k")],
                                       value="auto", label="判定线轨道数")
        with gr.Accordion("高级", open=False):
            density = gr.Slider(0.7, 1.6, value=1.0, step=0.05, label="写谱密度/难度倍率")
            line_fx = gr.Dropdown(
                [("无 None","none"),("脉冲呼吸 alpha_pulse","alpha_pulse"),("风车旋转 pinwheel","pinwheel"),
                 ("网格 grid","grid"),("曲线轨迹 curve","curve"),("变色流 color_flow","color_flow"),
                 ("光晕呼吸 glow","glow"),("弹跳 bounce","bounce"),("呼吸缩放 breathe","breathe"),
                 ("流星 meteor","meteor"),("回音残影 echo_trail","echo_trail"),("聚光 spotlight","spotlight"),
                 ("组合 mix","mix")],
                value="none", label="判定线动效",
            )
            pulse_style = gr.Dropdown([("链式 chain","chain"),("横扫 sweep","sweep")], value="chain", label="pulse 侧闪形态")
            deco_when = gr.Dropdown(
                [("前奏+副歌 intro_chorus","intro_chorus"),("前奏 intro","intro"),("副歌 chorus","chorus"),
                 ("主歌 verse","verse"),("循环 repeat","repeat"),("全部 all","all")],
                value="intro_chorus", label="旋转装饰出现段落",
            )
            main_y = gr.Slider(-600, 0, value=-300, step=25, label="主判定线初始Y")
            mix_spec = gr.Textbox(value="grid@all; sweep@all; pinwheel@climax", label="mix 特效顺序（effect@段落; …）")
            main_swing = gr.Checkbox(value=False, label="主判定线左右摆动")
            nt_custom = gr.Checkbox(value=False, label="自定义音符类型权重")
        with gr.Row():
            tap_weight = gr.Slider(0.0, 1.0, value=1.0, step=0.05, label="Tap 权重")
            hold_weight = gr.Slider(0.0, 1.0, value=0.30, step=0.05, label="Hold 权重")
            flick_weight = gr.Slider(0.0, 1.0, value=0.60, step=0.05, label="Flick 权重")
            drag_weight = gr.Slider(0.0, 1.0, value=0.0, step=0.05, label="Drag 权重")
        gen_btn = gr.Button("生成谱面", variant="primary")
        files = gr.Files(label="下载 .pez（可导入 Phira）")
        log = gr.Textbox(label="处理日志", lines=12, interactive=False)
        gen_btn.click(
            _run,
            inputs=[audio, cover, title, artist, charter, tier, all_tiers, density, line_fx,
                    pulse_style, deco_when, main_y, mix_spec, key_mode, main_swing,
                    tap_weight, hold_weight, flick_weight, drag_weight, nt_custom],
            outputs=[files, log],
        )
    return demo


if __name__ == "__main__":
    build_demo().launch(server_name="127.0.0.1", server_port=7860)
