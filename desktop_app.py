"""Local native Chinese desktop front end. No generator imports or network services."""
from __future__ import annotations

import ctypes
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import traceback
import uuid

BASE = Path(__file__).resolve().parent
STATE = BASE / '.desktop'
SETTINGS = STATE / 'settings.json'


def startup_error(exc_type, exc_value, exc_tb):
    detail = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with (STATE / 'startup.log').open('a', encoding='utf-8') as stream:
            stream.write(detail + '\n')
    except Exception:
        pass
    try:
        ctypes.windll.user32.MessageBoxW(None, '桌面程序发生错误。\n\n' + str(exc_value) + '\n\n诊断日志：' + str(STATE / 'startup.log'), 'Audio2Phira · 启动错误', 0x10)
    except Exception:
        print(detail, file=sys.stderr)


sys.excepthook = startup_error
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winsound

import anime_theme as theme

MODES = {'标准 · 混合谱面': 'standard', '鼓点 · 实验模式': 'drums'}
TIERS = {'简单 EASY': 'easy', '普通 NORMAL': 'normal', '困难 HARD': 'hard', '专家 EXPERT': 'expert', '大师 MASTER': 'master'}
KEYS = {'自动': 'auto', '2K': '2k', '4K': '4k', '6K': '6k'}
FX = {'无': 'none', '混合演出': 'mix', '呼吸缩放': 'breathe', '透明度脉冲': 'alpha_pulse'}
DEFAULTS = dict(audio='', cover='', title='', artist='', charter='', mode='standard', difficulty='hard', all_tiers=False,
                key_mode='auto', density='1.0', bpm='', chorus='', points='', line_fx='none', offset_ms='0',
                preview_start='0', preview_duration='20', output_dir=str(BASE / 'output'), seed='42')


class DesktopApp:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.process_lock = threading.Lock()
        self.process = None
        self.cancel_event = threading.Event()
        self.running = False
        self.closing = False
        self.result = None
        self.chart_paths = []
        self.editables = []
        self.loaded_warning = None
        values = dict(DEFAULTS)
        try:
            if SETTINGS.exists():
                saved = json.loads(SETTINGS.read_text(encoding='utf-8'))
                if not isinstance(saved, dict):
                    raise ValueError('设置文件应是 JSON 对象')
                values.update({k: v for k, v in saved.items() if k in values})
        except Exception as exc:
            self.loaded_warning = f'无法读取上次设置，已使用默认值：{exc}'
        self.vars = {}
        for key, value in values.items():
            self.vars[key] = tk.BooleanVar(root, value=value is True) if key == 'all_tiers' else tk.StringVar(root, value='' if value is None else str(value))
        for key, mapping in [('mode', MODES), ('difficulty', TIERS), ('key_mode', KEYS), ('line_fx', FX)]:
            if self.vars[key].get() not in mapping.values():
                self.vars[key].set(DEFAULTS[key])
        self.status = tk.StringVar(value='就绪 · 所有处理均在本机完成')
        self._style()
        self._build()
        self._mode_changed()
        self._result_controls(False)
        root.protocol('WM_DELETE_WINDOW', self._close)
        root.report_callback_exception = self._callback_error
        root.after(80, self._poll)
        if self.loaded_warning:
            self._log(self.loaded_warning)

    def _style(self):
        self.root.title('Audio2Phira ♪ 本地制谱工作台')
        self.root.geometry('1200x880')
        self.root.minsize(920, 680)
        icon = STATE / 'app.ico'
        if icon.is_file():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass
        # 配色、字体与全部 ttk 样式统一交给二次元主题层，业务逻辑不受影响
        self.style = theme.apply(self.root)

    def _build(self):
        self.header = theme.AnimeHeader(
            self.root,
            title='Audio2Phira',
            subtitle='本地制谱工作台    /    歌曲 → 谱面 → Phira',
            badge='MUSE POP · LOCAL CHART LAB',
        )
        self.header.pack(fill='x')
        body = ttk.Frame(self.root, padding=(22, 16, 22, 10))
        body.pack(fill='both', expand=True)
        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill='both', expand=True)
        self.basic = self._scroll_tab('◆ 歌曲与谱面')
        self.advanced = self._scroll_tab('◇ 高级设置')
        result_tab = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(result_tab, text='★ 生成结果')
        log_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(log_tab, text='⊙ 运行日志')
        self.result_tab = result_tab
        self.log_tab = log_tab
        self._basic_fields()
        self._advanced_fields()
        self._results(result_tab)
        self.log_text = tk.Text(log_tab, bg=theme.C.LOG_BG, fg=theme.C.LOG_FG, insertbackground=theme.C.PINK, relief='flat', wrap='word', font=(theme.MONO, 10), state='disabled', padx=14, pady=12, selectbackground=theme.C.PURPLE_DEEP, selectforeground='#ffffff')
        log_scroll = ttk.Scrollbar(log_tab, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)
        footer = ttk.Frame(body, padding=(0, 12, 0, 0))
        footer.pack(fill='x')
        self.progress = ttk.Progressbar(footer, mode='indeterminate', length=160)
        self.progress.pack(side='left', padx=(0, 12))
        ttk.Label(footer, textvariable=self.status, style='Pill.TLabel', wraplength=560).pack(side='left', fill='x', expand=True, padx=(0, 8))
        self.cancel_button = ttk.Button(footer, text='× 取消任务', command=self._cancel, state='disabled')
        self.cancel_button.pack(side='right', padx=(10, 0))
        self.generate_button = ttk.Button(footer, text='★ 开始生成', style='Accent.TButton', command=self._generate)
        self.generate_button.pack(side='right')

    def _scroll_tab(self, title):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        canvas = tk.Canvas(tab, bg=theme.C.BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        content = ttk.Frame(canvas, padding=16)
        window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        def wheel(event):
            pointer = self.root.winfo_containing(event.x_root, event.y_root)
            if pointer and (str(pointer).startswith(str(tab))):
                canvas.yview_scroll(int(-event.delta / 120), 'units')
        self.root.bind('<MouseWheel>', wheel, add='+')
        return content

    def _group(self, parent, title):
        group = ttk.LabelFrame(parent, text=title, padding=(14, 10))
        group.pack(fill='x', pady=(0, 13))
        group.columnconfigure(1, weight=1)
        return group

    def _field(self, parent, row, label, key, browse=None, mapping=None):
        ttk.Label(parent, text=label, width=15).grid(row=row, column=0, sticky='w', pady=5)
        if mapping:
            display = tk.StringVar(value=next(k for k, v in mapping.items() if v == self.vars[key].get()))
            widget = ttk.Combobox(parent, textvariable=display, values=list(mapping), state='readonly')
            def changed(event=None):
                self.vars[key].set(mapping[display.get()])
                if key == 'mode':
                    self._mode_changed()
            widget.bind('<<ComboboxSelected>>', changed)
            self.editables.append((widget, 'readonly'))
        else:
            widget = ttk.Entry(parent, textvariable=self.vars[key])
            self.editables.append((widget, 'normal'))
        widget.grid(row=row, column=1, sticky='ew', pady=5)
        button = None
        if browse:
            button = ttk.Button(parent, text='浏览…', command=lambda: self._browse(key, browse))
            button.grid(row=row, column=2, padx=(8, 0))
            self.editables.append((button, 'normal'))
        return widget, button

    def _basic_fields(self):
        group = self._group(self.basic, '01  音源与信息')
        self._field(group, 0, '音频文件 *', 'audio', 'audio')
        self._field(group, 1, '封面（可选）', 'cover', 'cover')
        self._field(group, 2, '歌曲标题', 'title')
        self._field(group, 3, '曲师 / 艺术家', 'artist')
        self._field(group, 4, '谱师', 'charter')
        group = self._group(self.basic, '02  生成方式')
        self._field(group, 0, '制谱模式', 'mode', mapping=MODES)
        self.mode_hint = ttk.Label(group, style='Muted.TLabel', wraplength=700, justify='left')
        self.mode_hint.grid(row=1, column=0, columnspan=3, sticky='w', pady=(2, 9))
        self._field(group, 2, '目标难度', 'difficulty', mapping=TIERS)
        all_check = ttk.Checkbutton(group, text='同时生成全部五档难度（EASY → MASTER）', variable=self.vars['all_tiers'], command=self._tier_changed)
        all_check.grid(row=3, column=1, sticky='w', pady=7)
        self.editables.append((all_check, 'normal'))
        self._field(group, 4, '键位布局', 'key_mode', mapping=KEYS)
        self._field(group, 5, '音符密度', 'density')
        ttk.Label(group, text='0.7–1.6；1.0 为默认密度。自动生成后仍建议人工检查。', style='Muted.TLabel').grid(row=6, column=1, sticky='w')
        group = self._group(self.basic, '03  保存位置')
        self._field(group, 0, '输出目录 *', 'output_dir', 'directory')
        ttk.Label(group, text='每次任务会在此目录内创建独立子文件夹，保留历史结果。', style='Muted.TLabel', wraplength=700).grid(row=1, column=1, sticky='w')

    def _advanced_fields(self):
        ttk.Label(self.advanced, text='可保留默认值。手动 BPM、高潮区间与打点用于更精细的节奏控制。', style='Muted.TLabel', wraplength=750).pack(anchor='w', pady=(0, 14))
        group = self._group(self.advanced, '节奏与结构')
        self._field(group, 0, '手动 BPM', 'bpm')
        ttk.Label(group, text='留空自动分析；手动范围 30–300。', style='Muted.TLabel').grid(row=1, column=1, sticky='w')
        self.chorus_entry, _ = self._field(group, 2, '高潮区间（秒）', 'chorus')
        ttk.Label(group, text='示例：30-60,90-120 或 0:51.3-1:25.5；起点须小于终点。', style='Muted.TLabel').grid(row=3, column=1, sticky='w')
        self.points_entry, self.points_browse = self._field(group, 4, '打点 JSON', 'points', 'points')
        ttk.Label(group, text='仅标准模式可用；鼓点模式下不提交此项。', style='Muted.TLabel').grid(row=5, column=1, sticky='w')
        self._field(group, 6, '谱面偏移（毫秒）', 'offset_ms')
        self._field(group, 7, '随机种子', 'seed')
        group = self._group(self.advanced, '演出与音频预览')
        self.fx_combo, _ = self._field(group, 0, '判定线演出', 'line_fx', mapping=FX)
        self._field(group, 1, '预览起点（秒）', 'preview_start')
        self._field(group, 2, '预览长度（秒）', 'preview_duration')
        ttk.Label(group, text='长度 5–60 秒；预览播放生成的 WAV 音频，不包含谱面试玩。', style='Muted.TLabel', wraplength=700).grid(row=3, column=1, sticky='w')

    def _results(self, parent):
        self.result_summary = tk.StringVar(value='尚未生成谱面')
        ttk.Label(parent, textvariable=self.result_summary, font=theme.font(13, 'bold'), wraplength=900).pack(anchor='w', pady=(0, 12))
        ttk.Label(parent, text='生成后请在 Phira 中手动导入 .pez 文件。启动 Phira 不会自动导入或试玩。', style='Muted.TLabel', wraplength=850).pack(anchor='w', pady=(0, 12))
        self.chart_tree = ttk.Treeview(parent, columns=('tier', 'notes', 'level', 'name'), show='headings', selectmode='browse', height=6)
        for column, label, width in [('tier', '难度', 100), ('notes', '音符数', 100), ('level', '定数', 100), ('name', '谱面文件', 460)]:
            self.chart_tree.heading(column, text=label)
            self.chart_tree.column(column, width=width, stretch=column == 'name')
        self.chart_tree.pack(fill='both', expand=True)
        self.chart_tree.bind('<<TreeviewSelect>>', lambda event: self._selection_changed())
        self.chart_tree.bind('<Double-1>', lambda event: self._reveal_chart())
        self.path_label = ttk.Label(parent, text='', style='Muted.TLabel', wraplength=850)
        self.path_label.pack(fill='x', pady=(9, 5))
        controls = ttk.Frame(parent)
        controls.pack(fill='x', pady=8)
        self.preview_button = ttk.Button(controls, text='▶ 播放音频预览', command=self._play)
        self.preview_button.pack(side='left', padx=(0, 7))
        self.stop_button = ttk.Button(controls, text='停止播放', command=self._stop)
        self.stop_button.pack(side='left', padx=(0, 7))
        self.output_button = ttk.Button(controls, text='打开输出文件夹', command=self._open_output)
        self.output_button.pack(side='left', padx=(0, 7))
        self.chart_button = ttk.Button(controls, text='定位选中谱面', command=self._reveal_chart)
        self.chart_button.pack(side='left')
        bottom = ttk.Frame(parent)
        bottom.pack(fill='x', pady=(4, 0))
        self.report_button = ttk.Button(bottom, text='查看生成报告', command=self._open_report)
        self.report_button.pack(side='left')
        ttk.Button(bottom, text='打开 Phira ↗', command=self._open_phira).pack(side='right')

    def _mode_changed(self):
        drums = self.vars['mode'].get() == 'drums'
        self.mode_hint.configure(text='鼓点模式（实验）：仅使用真实检测到的瞬态 Tap，不添加合成填充或演出；难度标签尚未经人工定级。' if drums else '标准模式：使用原有混合谱面生成，包含多种音符类型。')
        for widget in (self.points_entry, self.points_browse, self.chorus_entry):
            widget.configure(state='disabled' if drums or self.running else 'normal')
        self.fx_combo.configure(state='disabled' if drums or self.running else 'readonly')

    def _tier_changed(self):
        # Keep selected tier editable: it is remembered for the next single-tier run.
        pass

    def _browse(self, key, kind):
        options = dict(parent=self.root)
        if kind == 'directory':
            path = filedialog.askdirectory(title='选择输出目录', **options)
        else:
            filters = {'audio': [('音频文件', '*.wav *.mp3 *.flac *.ogg *.m4a *.aac'), ('所有文件', '*.*')], 'cover': [('图片文件', '*.png *.jpg *.jpeg *.webp *.bmp'), ('所有文件', '*.*')], 'points': [('JSON 打点文件', '*.json'), ('所有文件', '*.*')]}
            path = filedialog.askopenfilename(title='选择文件', filetypes=filters[kind], **options)
        if path:
            self.vars[key].set(path)
            if key == 'audio' and not self.vars['title'].get().strip():
                self.vars['title'].set(Path(path).stem)

    def _number(self, values, key, label, low, high=None, integer=False, optional=False):
        raw = values[key].strip()
        if optional and not raw:
            return None
        try:
            value = int(raw) if integer else float(raw)
            if not math.isfinite(value) or value < low or (high is not None and value > high):
                raise ValueError()
            return value
        except (ValueError, OverflowError):
            bounds = f'{low}–{high}' if high is not None else f'≥ {low}'
            raise ValueError(f'{label}请输入有效{"整数" if integer else "数值"}（{bounds}）。')

    def _make_job(self):
        values = {key: variable.get() for key, variable in self.vars.items()}
        job = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
        for key, label, required in [('audio', '音频文件', True), ('cover', '封面', False), ('points', '打点 JSON', False)]:
            if key == 'points' and job['mode'] == 'drums':
                job[key] = None
                continue
            if not job[key]:
                if required:
                    raise ValueError(f'请选择{label}。')
                job[key] = None
            else:
                path = Path(job[key]).expanduser().resolve()
                if not path.is_file():
                    raise ValueError(f'{label}不存在或不是文件：\n{path}')
                job[key] = str(path)
        if job['points']:
            try:
                json.loads(Path(job['points']).read_text(encoding='utf-8-sig'))
            except Exception as exc:
                raise ValueError(f'打点文件不是有效 JSON：{exc}')
        if job['mode'] == 'drums':
            job['chorus'] = ''
            job['line_fx'] = 'none'
        job['density'] = self._number(values, 'density', '音符密度', .7, 1.6)
        job['bpm'] = self._number(values, 'bpm', 'BPM', 30, 300, optional=True)
        job['offset_ms'] = self._number(values, 'offset_ms', '谱面偏移', -500, 500)
        job['preview_start'] = self._number(values, 'preview_start', '预览起点', 0)
        job['preview_duration'] = self._number(values, 'preview_duration', '预览长度', 5, 60)
        job['seed'] = self._number(values, 'seed', '随机种子', -2147483648, 2147483647, integer=True)
        if job['chorus']:
            def seconds(raw):
                if not re.fullmatch(r'(?:\d+:)?\d+(?:\.\d+)?', raw):
                    raise ValueError()
                parts = raw.split(':')
                if len(parts) == 2:
                    if float(parts[1]) >= 60:
                        raise ValueError()
                    return int(parts[0]) * 60 + float(parts[1])
                return float(raw)
            try:
                for part in job['chorus'].split(','):
                    start, end = (value.strip() for value in part.split('-'))
                    if not seconds(start) < seconds(end):
                        raise ValueError()
            except ValueError:
                raise ValueError('高潮区间应为 30-60,90-120 或 0:51.3-1:25.5，且每段起点小于终点。')
        if not job['output_dir']:
            raise ValueError('请选择输出目录。')
        output = Path(job['output_dir']).expanduser().resolve()
        if output.exists() and not output.is_dir():
            raise ValueError('输出路径已存在，但不是目录。')
        job['output_dir'] = str(output)
        return job

    def _save(self):
        STATE.mkdir(parents=True, exist_ok=True)
        temp = SETTINGS.with_suffix('.tmp')
        temp.write_text(json.dumps({key: var.get() for key, var in self.vars.items()}, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(SETTINGS)

    def _generate(self):
        if self.running:
            return
        try:
            job = self._make_job()
            worker = BASE / 'desktop_worker.py'
            if not worker.is_file():
                raise ValueError('未找到 desktop_worker.py，请确认桌面程序与工作进程在同一目录。')
            self._save()
            jobs = STATE / 'jobs'
            jobs.mkdir(parents=True, exist_ok=True)
            job_path = jobs / f'{uuid.uuid4().hex}.json'
            job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            messagebox.showerror('请检查生成设置', str(exc), parent=self.root)
            return
        self._stop()
        self.result = None
        self.chart_paths = []
        self.chart_tree.delete(*self.chart_tree.get_children())
        self.result_summary.set('正在生成，请稍候…')
        self.path_label.configure(text='')
        self._result_controls(False)
        self.running = True
        self.cancel_event.clear()
        self._set_busy(True)
        self._log('\n' + '─' * 48 + '\n新任务：' + str(job_path))
        self.status.set('正在分析音频并生成谱面…')
        threading.Thread(target=self._run_worker, args=(job_path,), daemon=True).start()

    def _run_worker(self, job_path):
        result = None
        code = -1
        try:
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            with self.process_lock:
                if self.cancel_event.is_set():
                    self.events.put(('done', (-1, None, True)))
                    return
                self.process = subprocess.Popen([sys.executable, '-u', str(BASE / 'desktop_worker.py'), str(job_path)], cwd=str(BASE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                process = self.process
            for line in process.stdout:
                line = line.rstrip('\r\n')
                if line.startswith('RESULT_JSON:'):
                    try:
                        result = json.loads(line[len('RESULT_JSON:'):])
                    except json.JSONDecodeError as exc:
                        self.events.put(('log', f'结果 JSON 无法解析：{exc}'))
                        result = None
                else:
                    self.events.put(('log', line))
            code = process.wait()
            process.stdout.close()
        except Exception as exc:
            self.events.put(('log', f'工作进程错误：{exc}\n{traceback.format_exc()}'))
        finally:
            with self.process_lock:
                self.process = None
        self.events.put(('done', (code, result, self.cancel_event.is_set())))

    def _cancel(self):
        if not self.running or self.cancel_event.is_set():
            return
        self.cancel_event.set()
        self.cancel_button.configure(state='disabled')
        self.status.set('正在取消任务并结束全部子进程…')
        self._log('收到取消请求，正在结束进程树。')
        threading.Thread(target=self._kill_tree, daemon=True).start()

    def _kill_tree(self):
        with self.process_lock:
            process = self.process
            if process is None or process.poll() is not None:
                return
            pid = process.pid
        try:
            completed = subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=20)
            if completed.returncode != 0 and process.poll() is None:
                self.events.put(('log', '终止进程树失败，请查看任务管理器。'))
                self.events.put(('kill_failed', None))
        except Exception as exc:
            self.events.put(('log', f'取消任务时出错：{exc}'))
            self.events.put(('kill_failed', None))

    def _set_busy(self, busy):
        for widget, default_state in self.editables:
            widget.configure(state='disabled' if busy else default_state)
        self.generate_button.configure(state='disabled' if busy else 'normal')
        self.cancel_button.configure(state='normal' if busy else 'disabled')
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        self._mode_changed()

    def _validate_result(self, result):
        if not isinstance(result, dict) or not isinstance(result.get('charts'), list) or not result['charts']:
            raise ValueError('工作进程未返回有效谱面列表。')
        for field in ('output_dir', 'preview', 'report'):
            if not isinstance(result.get(field), str) or not result[field]:
                raise ValueError(f'工作进程结果缺少 {field}。')
        if not Path(result['output_dir']).is_dir():
            raise ValueError('结果输出目录不存在。')
        for chart in result['charts']:
            if not isinstance(chart, dict) or not isinstance(chart.get('path'), str) or not Path(chart['path']).is_file():
                raise ValueError('结果中有谱面文件不存在。')
        for field in ('preview', 'report'):
            if not Path(result[field]).is_file():
                raise ValueError(f'结果文件不存在：{result[field]}')
        return result

    def _poll(self):
        try:
            for _ in range(250):
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self._log(value)
                elif kind == 'kill_failed':
                    self.cancel_event.clear()
                    self.cancel_button.configure(state='normal')
                    self.closing = False
                    self.status.set('取消失败，可重试取消；详情见运行日志')
                elif kind == 'done':
                    self._done(*value)
                    if self.closing:
                        self.root.destroy()
                        return
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _done(self, code, result, cancelled):
        self.running = False
        self._set_busy(False)
        if cancelled:
            self.status.set('任务已取消 · 可以调整设置后重试')
            self.result_summary.set('本次任务已取消')
            self._log('任务已取消，未启用本次结果。')
            return
        try:
            if code != 0:
                raise ValueError(f'工作进程退出码为 {code}，请查看运行日志。')
            self.result = self._validate_result(result)
        except Exception as exc:
            self.result = None
            self.status.set('生成失败 · 请查看运行日志')
            self.result_summary.set('生成失败，未获得完整结果')
            self._log(str(exc))
            if not self.closing:
                self.notebook.select(self.log_tab)
                messagebox.showerror('生成失败', str(exc), parent=self.root)
            return
        for chart in self.result['charts']:
            path = Path(chart['path'])
            self.chart_paths.append(path)
            self.chart_tree.insert('', 'end', iid=str(len(self.chart_paths) - 1), values=(str(chart.get('tier', '')).upper(), chart.get('notes', '—'), chart.get('level', '—'), path.name))
        self.chart_tree.selection_set('0')
        bpm = self.result.get('bpm', '—')
        duration = self.result.get('duration', '—')
        self.result_summary.set(f'生成完成 · {len(self.chart_paths)} 个谱面    BPM {bpm}    时长 {duration} 秒')
        self.path_label.configure(text=self.result['output_dir'])
        self._result_controls(True)
        self.status.set('生成完成 · 请在 Phira 中手动导入 .pez')
        self._log('生成完成。请手动导入 .pez；预览按钮仅播放音频。')
        if not self.closing:
            self.notebook.select(self.result_tab)

    def _log(self, text):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text + '\n')
        if int(self.log_text.index('end-1c').split('.')[0]) > 6000:
            self.log_text.delete('1.0', '1000.0')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _result_controls(self, enabled):
        for button in (self.preview_button, self.stop_button, self.output_button, self.chart_button, self.report_button):
            button.configure(state='normal' if enabled else 'disabled')

    def _selection_changed(self):
        self.chart_button.configure(state='normal' if self.result and self.chart_tree.selection() else 'disabled')

    def _play(self):
        if self.result:
            try:
                winsound.PlaySound(self.result['preview'], winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception as exc:
                messagebox.showerror('无法播放预览', str(exc), parent=self.root)

    def _stop(self):
        winsound.PlaySound(None, 0)

    def _open_path(self, path):
        try:
            if not Path(path).exists():
                raise FileNotFoundError(f'路径不存在：{path}')
            os.startfile(str(path))
        except Exception as exc:
            messagebox.showerror('无法打开', str(exc), parent=self.root)

    def _open_output(self):
        if self.result:
            self._open_path(self.result['output_dir'])

    def _open_report(self):
        if self.result:
            self._open_path(self.result['report'])

    def _reveal_chart(self):
        selected = self.chart_tree.selection()
        if not self.result or not selected:
            return
        path = self.chart_paths[int(selected[0])]
        try:
            if not path.is_file():
                raise FileNotFoundError(str(path))
            subprocess.Popen(['explorer.exe', '/select,', str(path)])
        except Exception as exc:
            messagebox.showerror('无法定位谱面', str(exc), parent=self.root)

    def _open_phira(self):
        executable = BASE.parent / 'Phira' / 'phira-main.exe'
        if not executable.is_file():
            messagebox.showinfo('未找到 Phira', f'请将 Phira 放在以下位置，或手动启动：\n{executable}\n\n谱面需在 Phira 内手动导入。', parent=self.root)
            return
        try:
            subprocess.Popen([str(executable)], cwd=str(executable.parent))
            self.status.set('已启动 Phira · 请手动导入生成的 .pez')
        except Exception as exc:
            messagebox.showerror('无法启动 Phira', str(exc), parent=self.root)

    def _callback_error(self, exc_type, exc_value, exc_tb):
        startup_error(exc_type, exc_value, exc_tb)
        self._log('界面错误：' + str(exc_value))

    def _close(self):
        if self.closing:
            return
        if self.running and not messagebox.askyesno('任务正在运行', '关闭窗口将终止当前任务及其全部子进程。确定关闭？', parent=self.root):
            return
        try:
            self._save()
        except Exception as exc:
            messagebox.showwarning('设置未保存', str(exc), parent=self.root)
        self._stop()
        if self.running:
            self.closing = True
            self._cancel()
        else:
            self.root.destroy()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    app = DesktopApp(root)
    if '--smoke-test' in sys.argv:
        root.update_idletasks()
        root.update()
        root.destroy()
        print('SMOKE_TEST_OK: Tk ' + tk.TkVersion.__str__() + ' / UI constructed and destroyed; no worker launched')
        return
    root.mainloop()


if __name__ == '__main__':
    main()
