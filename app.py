import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk
from file_manager import scan_folder, move_unique, move_exact, validate_name
from image_preview import load_preview
from models import Action


class ImageSorter:
    def __init__(self, root):
        self.root = root
        self.folder = None
        self.images, self.categories, self.undo_stack = [], [], []
        self.index = 0
        self.preview = self.photo = None
        self.resize_job = None
        self.path_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.info = tk.StringVar(value='請先選擇圖片資料夾')
        self.status = tk.StringVar(value='分類會移動原始檔案；本次操作可按 Ctrl+Z 復原。')
        root.title('圖片快速分類工具 v0.1')
        root.geometry('1050x780')
        root.minsize(760, 620)
        style = ttk.Style(root)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TButton', padding=(10, 7))
        style.configure('TLabel', font=('Microsoft JhengHei UI', 10))
        outer = ttk.Frame(root, padding=16)
        outer.pack(fill='both', expand=True)
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 12))
        ttk.Label(top, text='圖片資料夾').pack(side='left', padx=(0, 8))
        self.path_entry = ttk.Entry(top, textvariable=self.path_var)
        self.path_entry.pack(side='left', fill='x', expand=True)
        self.path_entry.bind('<Return>', lambda e: self.load())
        ttk.Button(top, text='瀏覽', command=self.browse).pack(side='left', padx=6)
        ttk.Button(top, text='載入', command=self.load).pack(side='left')
        self.canvas = tk.Canvas(outer, bg='#202630', highlightthickness=0, takefocus=True)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', self.schedule_render)
        self.canvas.bind('<Button-1>', lambda e: self.canvas.focus_set())
        ttk.Label(outer, textvariable=self.info, anchor='center').pack(fill='x', pady=8)
        category_box = ttk.LabelFrame(outer, text='分類到子資料夾（1–9 快捷鍵）', padding=8)
        category_box.pack(fill='x')
        self.category_canvas = tk.Canvas(category_box, height=100, highlightthickness=0)
        scroll = ttk.Scrollbar(category_box, orient='vertical', command=self.category_canvas.yview)
        scroll.pack(side='right', fill='y')
        self.category_canvas.pack(side='left', fill='x', expand=True)
        self.category_canvas.configure(yscrollcommand=scroll.set)
        self.category_frame = ttk.Frame(self.category_canvas)
        self.category_window = self.category_canvas.create_window((0, 0), window=self.category_frame, anchor='nw')
        self.category_frame.bind('<Configure>', lambda e: self.category_canvas.configure(scrollregion=self.category_canvas.bbox('all')))
        self.category_canvas.bind('<Configure>', lambda e: self.category_canvas.itemconfigure(self.category_window, width=e.width))
        rename = ttk.Frame(outer)
        rename.pack(fill='x', pady=12)
        ttk.Label(rename, text='新檔名').pack(side='left', padx=(0, 8))
        self.name_entry = ttk.Entry(rename, textvariable=self.name_var)
        self.name_entry.pack(side='left', fill='x', expand=True)
        self.name_entry.bind('<Return>', lambda e: self.rename())
        self.suffix_label = ttk.Label(rename, text='')
        self.suffix_label.pack(side='left', padx=8)
        ttk.Button(rename, text='套用名稱 ↵', command=self.rename).pack(side='left')
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        ttk.Button(controls, text='← 上一張', command=lambda: self.navigate(-1)).pack(side='left')
        ttk.Button(controls, text='略過／下一張 →', command=lambda: self.navigate(1)).pack(side='left', padx=8)
        ttk.Button(controls, text='復原 Ctrl+Z', command=self.undo).pack(side='left')
        ttk.Label(outer, text='F2：編輯檔名　Esc：回到看圖　輸入文字時暫停分類快捷鍵', foreground='#566579').pack(anchor='w', pady=(10, 4))
        ttk.Label(outer, textvariable=self.status, wraplength=950).pack(fill='x')
        root.bind('<KeyPress>', self.keypress)
        root.bind('<Control-z>', self.undo_key)
        self.render_categories()
        self.render()

    def report_error(self, exc):
        self.status.set(f'操作未完成：{exc}')
        messagebox.showerror('操作未完成', str(exc), parent=self.root)

    def browse(self):
        path = filedialog.askdirectory(parent=self.root, initialdir=str(self.folder) if self.folder else None)
        if path:
            self.path_var.set(path)
            self.load()

    def load(self):
        raw = self.path_var.get().strip().strip('"')
        if not raw:
            self.report_error(ValueError('請先輸入或選擇資料夾路徑。'))
            return
        try:
            folder, images, categories = scan_folder(raw)
        except Exception as exc:
            self.report_error(exc)
            return
        if self.undo_stack and not messagebox.askyesno('重新載入', '重新載入會清除本次復原紀錄，是否繼續？', parent=self.root):
            return
        self.folder, self.images, self.categories = folder, images, categories
        self.undo_stack.clear()
        self.index = 0
        self.path_var.set(str(folder))
        self.render_categories()
        self.show_current()
        self.canvas.focus_set()
        self.status.set(f'已載入 {len(images)} 張圖片、{len(categories)} 個分類。只讀取第一層圖片。')

    def render_categories(self):
        for child in self.category_frame.winfo_children():
            child.destroy()
        for i, folder in enumerate(self.categories):
            text = f'[{i + 1}] {folder.name}' if i < 9 else folder.name
            ttk.Button(self.category_frame, text=text, command=lambda p=folder: self.classify(p)).grid(row=i // 4, column=i % 4, sticky='ew', padx=3, pady=3)
        n = len(self.categories)
        ttk.Button(self.category_frame, text='＋ 新增分類', command=self.add_category).grid(row=n // 4, column=n % 4, sticky='ew', padx=3, pady=3)
        for col in range(4):
            self.category_frame.columnconfigure(col, weight=1)

    def current(self):
        return self.images[self.index] if self.images else None

    def show_current(self):
        self.preview = None
        if not self.images:
            self.name_var.set('')
            self.suffix_label.configure(text='')
            self.info.set('沒有待分類圖片' if self.folder else '請先選擇圖片資料夾')
        else:
            self.index = max(0, min(self.index, len(self.images) - 1))
            path = self.current()
            self.name_var.set(path.stem)
            self.suffix_label.configure(text=path.suffix)
            self.info.set(f'{self.index + 1} / {len(self.images)}　｜　{path.name}')
            try:
                self.preview, size = load_preview(path)
                self.info.set(f'{self.info.get()}　｜　{size[0]} × {size[1]}')
            except Exception as exc:
                self.status.set(f'圖片無法預覽，可略過：{exc}')
        self.render()

    def schedule_render(self, event=None):
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(70, self.render)

    def render(self):
        self.resize_job = None
        self.canvas.delete('all')
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.preview is None:
            text = '圖片無法預覽，請略過或分類' if self.images else '選擇資料夾開始整理' if self.folder is None else '目前沒有待分類圖片'
            self.canvas.create_text(width / 2, height / 2, text=text, fill='#dbe3ef', font=('Microsoft JhengHei UI', 17))
            self.photo = None
            return
        image = self.preview.copy()
        image.thumbnail((max(1, width - 24), max(1, height - 24)), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(width / 2, height / 2, image=self.photo)

    def navigate(self, step):
        if not self.images:
            return
        self.index = (self.index + step) % len(self.images)
        self.show_current()
        self.canvas.focus_set()
        self.status.set('已切換圖片；未套用的檔名已捨棄。')

    def classify(self, category):
        self.apply_change(category, True)

    def rename(self):
        if self.folder:
            self.apply_change(self.folder, False)

    def apply_change(self, folder, classified):
        source = self.current()
        if source is None:
            return
        try:
            if folder.is_symlink() or not folder.is_dir() or (classified and folder.parent != self.folder):
                raise ValueError('分類資料夾已不存在或已被變更，請重新載入。')
            target = move_unique(source, folder, self.name_var.get())
            if target == source:
                self.status.set('檔名未變更。')
                return
        except Exception as exc:
            self.report_error(exc)
            return
        self.undo_stack.append(Action(source, target, self.index, classified))
        if classified:
            self.images.pop(self.index)
        else:
            self.images[self.index] = target
        self.show_current()
        self.canvas.focus_set()
        self.status.set(f'已移動至：{target.parent.name} / {target.name}' if classified else f'已重新命名：{target.name}')

    def add_category(self):
        if not self.folder:
            self.report_error(ValueError('請先載入圖片資料夾。'))
            return
        name = simpledialog.askstring('新增分類', '子資料夾名稱：', parent=self.root)
        if name is None:
            return
        try:
            validate_name(name)
            category = self.folder / name
            category.mkdir()
        except Exception as exc:
            self.report_error(exc)
            return
        self.categories.append(category)
        self.render_categories()
        self.canvas.focus_set()
        self.status.set(f'已新增分類：{name}。既有快捷鍵保持不變。')

    def undo(self):
        if not self.undo_stack:
            self.status.set('沒有可以復原的操作。')
            return
        action = self.undo_stack[-1]
        try:
            move_exact(action.new_path, action.old_path)
        except Exception as exc:
            self.report_error(exc)
            return
        self.undo_stack.pop()
        if action.classified:
            self.images.insert(min(action.index, len(self.images)), action.old_path)
        else:
            self.images[self.images.index(action.new_path)] = action.old_path
        self.index = self.images.index(action.old_path)
        self.show_current()
        self.canvas.focus_set()
        self.status.set(f'已復原：{action.old_path.name}')

    def is_typing(self):
        return isinstance(self.root.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox))

    def undo_key(self, event):
        if self.is_typing():
            return
        self.undo()
        return 'break'

    def keypress(self, event):
        if event.keysym == 'Escape':
            self.canvas.focus_set()
            return 'break'
        if self.is_typing() or event.state & (0x4 | 0x8):
            return
        if event.char in '123456789' and event.char:
            index = int(event.char) - 1
            if index < len(self.categories):
                self.classify(self.categories[index])
            return 'break'
        if event.keysym in ('Left', 'Right'):
            self.navigate(-1 if event.keysym == 'Left' else 1)
            return 'break'
        if event.keysym == 'F2' and self.images:
            self.name_entry.focus_set()
            self.name_entry.selection_range(0, 'end')
            return 'break'
