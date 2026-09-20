"""Desktop GUI for weekly worship PPT generation."""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, scrolledtext, ttk

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_paths import ensure_app_dirs, get_app_root  # noqa: E402
from week_generator import (  # noqa: E402
    DEFAULT_EXTRACTED_JSON,
    DEFAULT_INPUT2_DIR,
    DEFAULT_INPUT_DIR,
    DEFAULT_INPUT_HYMS_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TEMPLATE,
    EDITABLE_FIELDS,
    GenerateOptions,
    discover_pdf,
    generate_week_ppt,
    parse_from_pdfs,
)
from scripture_parser import parse_scripture_range  # noqa: E402

SERMON_VERSE_FIELDS: tuple[str, ...] = tuple(
    f"verse_{prefix}{index}"
    for index in (1, 2, 3)
    for prefix in ("ref", "ko", "en")
)


class PptApp(tk.Tk):
    """Simple GUI: load PDFs, review fields, generate PPT."""

    def __init__(self) -> None:
        super().__init__()
        self.title("주일예배 PPT 생성기")
        self.geometry("1500x1000")
        self.minsize(960, 720)

        self.bulletin_var = tk.StringVar()
        self.sermon_var = tk.StringVar()
        self.translate_var = tk.BooleanVar(value=True)
        self.responsive_var = tk.BooleanVar(value=True)
        self.scripture_var = tk.BooleanVar(value=True)
        self.hymns_var = tk.BooleanVar(value=True)
        self.hymn_background_var = tk.StringVar()
        self.youth_sermon_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="PDF를 선택하고 [PDF 불러오기]를 누르세요.")

        self.field_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar() for key, _ in EDITABLE_FIELDS
        }

        self._pdf_loading = False
        self._generating = False
        self._loaded_data: dict = {}

        self._configure_fonts()
        self._build_ui()
        ensure_app_dirs()
        self._log(f"작업 폴더: {get_app_root()}")
        self._log(f"  input  → {DEFAULT_INPUT_DIR}")
        self._log(f"  input2 → {DEFAULT_INPUT2_DIR}")
        self._log(f"  input_hyms → {DEFAULT_INPUT_HYMS_DIR}")

        threading.Thread(target=self._warmup_korean_parser, daemon=True).start()
        self.after(200, self._startup_sequence)

    def _configure_fonts(self) -> None:
        """Force Noto Sans across the entire GUI."""
        size = 9
        available = set(font.families())
        family = next(
            (
                name
                for name in (
                    "Noto Sans KR",
                    "Noto Sans",
                    "Noto Sans CJK KR",
                )
                if name in available
            ),
            None,
        )
        if family is None:
            for fallback in ("Malgun Gothic", "맑은 고딕", "Segoe UI", "Arial"):
                if fallback in available:
                    family = fallback
                    break
            else:
                family = font.nametofont("TkDefaultFont").actual("family")

        font_spec = (family, size)
        self.ui_font = font.Font(family=family, size=size)
        self.text_font = self.ui_font

        font_string = f"{{{family}}} {size}"
        for pattern in (
            "*Font",
            "*Text*Font",
            "*Entry*Font",
            "*Listbox*Font",
            "*Menu*Font",
            "*Label*Font",
            "*Button*Font",
        ):
            try:
                self.option_add(pattern, font_string)
            except tk.TclError:
                pass

        for named in (
            "TkDefaultFont",
            "TkTextFont",
            "TkFixedFont",
            "TkMenuFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                font.nametofont(named).configure(family=family, size=size)
            except tk.TclError:
                pass

        style = ttk.Style(self)
        for widget_style in (
            ".",
            "TLabel",
            "TButton",
            "TCheckbutton",
            "TRadiobutton",
            "TEntry",
            "TLabelframe",
            "TLabelframe.Label",
            "TCombobox",
        ):
            style.configure(widget_style, font=font_spec)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        status_bar = ttk.Label(outer, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status_bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        content = ttk.Frame(outer)
        content.grid(row=0, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1, uniform="split")
        content.columnconfigure(1, weight=1, uniform="split")
        content.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(content, padding=(0, 0, 6, 0))
        right_panel = ttk.Frame(content, padding=(6, 0, 0, 0))
        left_panel.grid(row=0, column=0, sticky="nsew")
        right_panel.grid(row=0, column=1, sticky="nsew")

        left_panel.rowconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)
        left_panel.columnconfigure(0, weight=1)

        right_panel.rowconfigure(2, weight=1)
        right_panel.columnconfigure(0, weight=1)

        self.responsive_outer = ttk.LabelFrame(
            left_panel,
            text="교독문 본문 (한국어 전체 붙여넣기 · 한 줄 = 슬라이드 1장)",
            padding=10,
        )
        self.responsive_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.responsive_outer.rowconfigure(1, weight=1)
        self.responsive_outer.columnconfigure(0, weight=1)
        self.responsive_info_var = tk.StringVar(
            value="한 줄마다 슬라이드 1장이 생성됩니다. 마지막 줄은 RES_KO_LAST / RES_EN_LAST 슬라이드에 들어갑니다."
        )
        ttk.Label(self.responsive_outer, textvariable=self.responsive_info_var).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.responsive_ko_text = scrolledtext.ScrolledText(
            self.responsive_outer,
            height=14,
            wrap=tk.WORD,
            font=self.text_font,
        )
        self.responsive_ko_text.grid(row=1, column=0, sticky="nsew")

        self.verse_outer = ttk.LabelFrame(
            left_panel,
            text="성경 구절 본문 (한국어 / English 전체 붙여넣기)",
            padding=10,
        )
        self.verse_outer.grid(row=1, column=0, sticky="nsew")
        self.verse_outer.rowconfigure(1, weight=1)
        self.verse_outer.columnconfigure(0, weight=1)
        self.verse_info_var = tk.StringVar(
            value="슬라이드 21에는 구절 표시(수14:6-15 / Joshua 14:6-15)만 들어갑니다. 본문은 절별 슬라이드용입니다."
        )
        ttk.Label(self.verse_outer, textvariable=self.verse_info_var).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        verse_panes = ttk.Frame(self.verse_outer)
        verse_panes.grid(row=1, column=0, sticky="nsew")
        verse_panes.columnconfigure(0, weight=1)
        verse_panes.columnconfigure(1, weight=1)
        verse_panes.rowconfigure(1, weight=1)

        ttk.Label(verse_panes, text="한국어 본문").grid(row=0, column=0, sticky="w")
        ttk.Label(verse_panes, text="English").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.scripture_ko_text = scrolledtext.ScrolledText(
            verse_panes,
            height=14,
            wrap=tk.WORD,
            font=self.text_font,
        )
        self.scripture_en_text = scrolledtext.ScrolledText(
            verse_panes,
            height=14,
            wrap=tk.WORD,
            font=self.text_font,
        )
        self.scripture_ko_text.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.scripture_en_text.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(4, 0))

        pdf_frame = ttk.LabelFrame(right_panel, text="PDF 파일", padding=10)
        pdf_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self._add_file_row(pdf_frame, "주보 PDF", self.bulletin_var, self._browse_bulletin, 0)
        self._add_file_row(pdf_frame, "설교 PDF", self.sermon_var, self._browse_sermon, 1)

        pdf_actions = ttk.Frame(pdf_frame)
        pdf_actions.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.load_pdf_button = ttk.Button(
            pdf_actions,
            text="PDF 불러오기",
            command=lambda: self._load_from_pdf(auto=False),
        )
        self.load_pdf_button.pack(side=tk.LEFT, padx=(0, 8))
        self.find_pdf_button = ttk.Button(
            pdf_actions,
            text="폴더에서 PDF 찾기",
            command=self._find_pdfs_in_folders,
        )
        self.find_pdf_button.pack(side=tk.LEFT)

        help_label = ttk.Label(
            pdf_frame,
            text="※ PDF는 exe 옆 input / input2 폴더에 넣거나 [찾아보기]로 선택하세요.",
        )
        help_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        options_frame = ttk.LabelFrame(right_panel, text="옵션", padding=10)
        options_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=1)
        for index, (label, variable) in enumerate(
            (
                ("자동 영문 번역", self.translate_var),
                ("교독문 슬라이드 생성", self.responsive_var),
                ("찬송가 슬라이드 삽입", self.hymns_var),
                ("성경 구절 슬라이드 생성", self.scripture_var),
                ("Youth Sermon 주보", self.youth_sermon_var),
            )
        ):
            ttk.Checkbutton(
                options_frame,
                text=label,
                variable=variable,
            ).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 8), pady=2)

        bg_frame = ttk.Frame(options_frame)
        bg_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bg_frame.columnconfigure(1, weight=1)
        ttk.Label(bg_frame, text="찬송 배경 이미지").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(bg_frame, textvariable=self.hymn_background_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(0, 8),
        )
        ttk.Button(
            bg_frame,
            text="찾아보기",
            command=self._browse_hymn_background,
        ).grid(row=0, column=2, sticky="e")

        fields_outer = ttk.LabelFrame(right_panel, text="추출된 데이터 (수정 가능)", padding=10)
        fields_outer.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        fields_outer.rowconfigure(0, weight=1)
        fields_outer.columnconfigure(0, weight=1)

        self.fields_canvas = tk.Canvas(fields_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            fields_outer,
            orient=tk.VERTICAL,
            command=self.fields_canvas.yview,
        )
        self.fields_frame = ttk.Frame(self.fields_canvas)
        self.fields_window = self.fields_canvas.create_window(
            (0, 0),
            window=self.fields_frame,
            anchor="nw",
        )

        self.fields_frame.bind(
            "<Configure>",
            lambda _event: self.fields_canvas.configure(
                scrollregion=self.fields_canvas.bbox("all")
            ),
        )
        self.fields_canvas.bind(
            "<Configure>",
            self._on_fields_canvas_configure,
        )
        self.fields_canvas.configure(yscrollcommand=scrollbar.set)
        self.fields_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        for row_index, (field_key, label) in enumerate(EDITABLE_FIELDS):
            ttk.Label(self.fields_frame, text=label, width=18).grid(
                row=row_index,
                column=0,
                sticky="w",
                padx=(0, 8),
                pady=3,
            )
            entry = ttk.Entry(self.fields_frame, textvariable=self.field_vars[field_key])
            entry.grid(row=row_index, column=1, sticky="ew", pady=3)
            if field_key == "scripture":
                self.field_vars[field_key].trace_add(
                    "write",
                    lambda *_args: self._update_verse_info(),
                )
        self.fields_frame.columnconfigure(1, weight=1)

        action_frame = ttk.Frame(right_panel)
        action_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.generate_button = ttk.Button(
            action_frame,
            text="PPT 생성",
            command=self._start_generate,
        )
        self.generate_button.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(action_frame, text="출력 폴더 열기", command=self._open_output_dir).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Button(action_frame, text="종료", command=self.destroy).pack(side=tk.RIGHT)

        log_frame = ttk.LabelFrame(right_panel, text="로그", padding=10)
        log_frame.grid(row=4, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=6,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=self.text_font,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _set_responsive_text(self, text: str = "") -> None:
        self.responsive_ko_text.delete("1.0", tk.END)
        self.responsive_ko_text.insert("1.0", text)

    def _get_responsive_text(self) -> str:
        return self.responsive_ko_text.get("1.0", tk.END).strip()

    def _set_responsive_fields_from_data(self, data: dict) -> None:
        ko_text = str(data.get("responsive_ko_text", "")).strip()
        if not ko_text and isinstance(data.get("responsive_lines"), list):
            from responsive_parser import join_responsive_lines

            ko_text = join_responsive_lines(data["responsive_lines"], "ko")
        self._set_responsive_text(ko_text)

    def _update_verse_info(self) -> None:
        scripture = self.field_vars["scripture"].get().strip()
        parsed = parse_scripture_range(scripture)
        if not parsed:
            self.verse_info_var.set("성경 구절 형식 예: 수14:6-15")
            return
        self.verse_info_var.set(
            f"{parsed.chapter}장 {parsed.start}~{parsed.end}절 "
            f"({parsed.count}슬라이드) · 슬라이드 21: {scripture} / 영문 구절 표시"
        )

    def _set_scripture_bulk_text(self, ko_text: str = "", en_text: str = "") -> None:
        self.scripture_ko_text.delete("1.0", tk.END)
        self.scripture_ko_text.insert("1.0", ko_text)
        self.scripture_en_text.delete("1.0", tk.END)
        self.scripture_en_text.insert("1.0", en_text)

    def _get_scripture_bulk_text(self) -> tuple[str, str]:
        ko_text = self.scripture_ko_text.get("1.0", tk.END).strip()
        en_text = self.scripture_en_text.get("1.0", tk.END).strip()
        return ko_text, en_text

    def _set_verse_fields_from_data(self, data: dict) -> None:
        self._update_verse_info()

        ko_text = str(data.get("scripture_ko_text", "")).strip()
        en_text = str(data.get("scripture_en_text", "")).strip()
        if not ko_text and isinstance(data.get("scripture_verses"), list):
            from scripture_parser import join_verse_texts

            ko_text = join_verse_texts(data["scripture_verses"], "ko")
            en_text = join_verse_texts(data["scripture_verses"], "en")
        self._set_scripture_bulk_text(ko_text, en_text)

    def _collect_verse_data(self) -> tuple[str, str]:
        return self._get_scripture_bulk_text()

    def _on_fields_canvas_configure(self, event) -> None:
        self.fields_canvas.itemconfigure(self.fields_window, width=event.width)

    def _add_file_row(
        self,
        parent: ttk.LabelFrame,
        label: str,
        variable: tk.StringVar,
        browse_command,
        row: int,
    ) -> None:
        ttk.Label(parent, text=label, width=10).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", padx=(0, 8), pady=4
        )
        ttk.Button(parent, text="찾아보기", command=browse_command).grid(
            row=row, column=2, sticky="e", pady=4
        )
        parent.columnconfigure(1, weight=1)

    def _set_busy(self, busy: bool, message: str) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.load_pdf_button.config(state=state)
        self.find_pdf_button.config(state=state)
        if not self._generating:
            self.generate_button.config(state=state)
        self.status_var.set(message)

    def _warmup_korean_parser(self) -> None:
        try:
            from korean_text import space_korean_text

            space_korean_text("준비")
        except Exception as error:
            self.after(0, lambda: self._log(f"한국어 처리 준비 경고: {error}"))

    def _startup_sequence(self) -> None:
        self._find_pdfs_in_folders(silent=False)

    def _find_pdfs_in_folders(self, *, silent: bool = False) -> bool:
        bulletin = discover_pdf(DEFAULT_INPUT_DIR)
        sermon = discover_pdf(DEFAULT_INPUT2_DIR)

        if bulletin:
            self.bulletin_var.set(str(bulletin))
        if sermon:
            self.sermon_var.set(str(sermon))

        if bulletin and sermon:
            if not silent:
                self._log("input / input2 폴더에서 PDF 2개를 찾았습니다.")
                self.status_var.set("PDF 경로를 찾았습니다. [PDF 불러오기]를 누르세요.")
            return True

        missing = []
        if not bulletin:
            missing.append("input")
        if not sermon:
            missing.append("input2")
        if not silent:
            self._log(
                f"PDF를 찾지 못했습니다 ({', '.join(missing)}). "
                "폴더에 PDF를 넣거나 [찾아보기]로 선택하세요."
            )
            self.status_var.set("PDF 파일을 선택해 주세요.")
        return False

    def _browse_bulletin(self) -> None:
        path = filedialog.askopenfilename(
            title="주보 PDF 선택",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=str(DEFAULT_INPUT_DIR),
        )
        if path:
            self.bulletin_var.set(path)

    def _browse_sermon(self) -> None:
        path = filedialog.askopenfilename(
            title="설교 PDF 선택",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=str(DEFAULT_INPUT2_DIR),
        )
        if path:
            self.sermon_var.set(path)

    def _browse_hymn_background(self) -> None:
        initial_dir = DEFAULT_INPUT_HYMS_DIR
        initial_dir.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="찬송 배경 이미지 선택",
            filetypes=[
                ("Image files", "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp;*.tif;*.tiff"),
                ("All files", "*.*"),
            ],
            initialdir=str(initial_dir),
        )
        if path:
            self.hymn_background_var.set(path)

    def _load_from_pdf(self, *, auto: bool = False) -> None:
        if self._pdf_loading:
            return

        bulletin = self.bulletin_var.get().strip()
        sermon = self.sermon_var.get().strip()
        if not bulletin or not sermon:
            if not auto:
                messagebox.showwarning(
                    "PDF 필요",
                    "주보 PDF와 설교 PDF를 모두 선택해 주세요.\n\n"
                    f"작업 폴더: {get_app_root()}\n"
                    f"input / input2 폴더에 PDF를 넣거나 [찾아보기]를 사용하세요.",
                )
            return

        bulletin_path = Path(bulletin)
        sermon_path = Path(sermon)
        if not bulletin_path.is_file() or not sermon_path.is_file():
            if not auto:
                messagebox.showerror(
                    "PDF 없음",
                    "선택한 PDF 파일을 찾을 수 없습니다.\n"
                    f"주보: {bulletin}\n"
                    f"설교: {sermon}",
                )
            self._log("PDF 파일 경로가 올바르지 않습니다.")
            return

        self._pdf_loading = True
        self._set_busy(True, "PDF 불러오는 중... (처음 실행 시 10~30초 걸릴 수 있습니다)")
        if not auto:
            self._log("--- PDF 불러오기 시작 ---")

        thread = threading.Thread(
            target=self._load_pdf_worker,
            args=(bulletin, sermon, self.youth_sermon_var.get()),
            daemon=True,
        )
        thread.start()

    def _load_pdf_worker(
        self,
        bulletin: str,
        sermon: str,
        has_youth_sermon: bool,
    ) -> None:
        try:
            from pdf_parser import parse_sermon_pdf

            data = parse_from_pdfs(
                bulletin_pdf=bulletin,
                sermon_pdf=sermon,
                has_youth_sermon=has_youth_sermon,
            )
            # enrich_sermon_part_verses() drops raw quotes; keep them for PPT generation.
            raw_sermon = parse_sermon_pdf(sermon)
            if raw_sermon.get("_sermon_part_verses"):
                data["_sermon_part_verses"] = raw_sermon["_sermon_part_verses"]
        except Exception as error:
            self.after(0, lambda: self._on_load_pdf_error(error))
            return
        self.after(0, lambda: self._on_load_pdf_success(data))

    def _on_load_pdf_success(self, data: dict) -> None:
        self._pdf_loading = False
        self._set_busy(False, "PDF 데이터를 불러왔습니다. 확인 후 [PPT 생성]을 누르세요.")
        self._set_fields_from_data(data)
        self._set_responsive_fields_from_data(data)
        self._set_verse_fields_from_data(data)
        self._loaded_data = data

        filled = [key for key, _ in EDITABLE_FIELDS if data.get(key)]
        if not filled:
            self._log("PDF는 읽었지만 추출된 데이터가 없습니다. PDF 형식을 확인하세요.")
            messagebox.showwarning(
                "추출 데이터 없음",
                "PDF에서 필드를 추출하지 못했습니다.\n"
                "주보/설교 PDF 형식을 확인하거나 필드를 직접 입력하세요.",
            )
            return

        self._log("PDF에서 데이터를 추출했습니다.")
        for key, _ in EDITABLE_FIELDS:
            if data.get(key):
                self._log(f"  {key}: {data[key]}")

    def _on_load_pdf_error(self, error: Exception) -> None:
        self._pdf_loading = False
        self._set_busy(False, "PDF 불러오기 실패")
        self._log(f"PDF 파싱 실패: {error}")
        messagebox.showerror("PDF 파싱 실패", str(error))

    def _set_fields_from_data(self, data: dict) -> None:
        for key, _ in EDITABLE_FIELDS:
            self.field_vars[key].set(str(data.get(key, "")))

    def _collect_data(self) -> dict:
        data = {}
        for key, _ in EDITABLE_FIELDS:
            value = self.field_vars[key].get().strip()
            if value:
                data[key] = value

        scripture = self.field_vars["scripture"].get().strip()
        parsed = parse_scripture_range(scripture)
        if parsed:
            data["scripture_chapter"] = parsed.chapter
            data["scripture_verse_start"] = parsed.start
            data["scripture_verse_end"] = parsed.end

        ko_text, en_text = self._collect_verse_data()
        if ko_text:
            data["scripture_ko_text"] = ko_text
        if en_text:
            data["scripture_en_text"] = en_text

        from bible_fetcher import enrich_scripture_data, enrich_sermon_part_verses

        data = enrich_scripture_data(
            data,
            fetch=not ko_text and not en_text,
        )

        if self._loaded_data.get("_sermon_part_verses"):
            data["_sermon_part_verses"] = self._loaded_data["_sermon_part_verses"]
        data = enrich_sermon_part_verses(data)
        for field in SERMON_VERSE_FIELDS:
            if not str(data.get(field, "")).strip():
                loaded_value = self._loaded_data.get(field)
                if loaded_value:
                    data[field] = loaded_value

        responsive_ko_text = self._get_responsive_text()
        if responsive_ko_text:
            data["responsive_ko_text"] = responsive_ko_text

        from responsive_library import enrich_responsive_data

        data = enrich_responsive_data(data)

        from scripture_parser import build_scripture_verses

        verses = build_scripture_verses(data)
        if verses:
            data["scripture_verses"] = verses
        return data

    def _start_generate(self) -> None:
        if self._generating or self._pdf_loading:
            return

        data = self._collect_data()
        if not data.get("sermon_title"):
            messagebox.showwarning(
                "데이터 없음",
                "먼저 [PDF 불러오기]를 누르거나 필드를 직접 입력해 주세요.",
            )
            return

        self._generating = True
        self.generate_button.config(state=tk.DISABLED)
        self.load_pdf_button.config(state=tk.DISABLED)
        self.find_pdf_button.config(state=tk.DISABLED)
        self.status_var.set("PPT 생성 중...")
        self._log("--- PPT 생성 시작 ---")

        thread = threading.Thread(
            target=self._generate_worker,
            args=(data,),
            daemon=True,
        )
        thread.start()

    def _progress_from_worker(self, message: str) -> None:
        self.after(0, lambda msg=message: self._apply_generate_progress(msg))

    def _apply_generate_progress(self, message: str) -> None:
        self._log(message)
        self.status_var.set(message)

    def _generate_worker(self, data: dict) -> None:
        import pythoncom

        pythoncom.CoInitialize()
        try:
            try:
                background_path = self.hymn_background_var.get().strip()
                options = GenerateOptions(
                    template=DEFAULT_TEMPLATE,
                    translate=self.translate_var.get(),
                    insert_responsive=self.responsive_var.get(),
                    insert_scripture=self.scripture_var.get(),
                    insert_hymns=self.hymns_var.get(),
                    hymn_background_image=Path(background_path) if background_path else None,
                    save_json=DEFAULT_EXTRACTED_JSON,
                    on_progress=self._progress_from_worker,
                )
                result = generate_week_ppt(data, options)
            except Exception as error:
                self.after(0, lambda: self._on_generate_error(error))
                return
            self.after(0, lambda: self._on_generate_success(result))
        finally:
            pythoncom.CoUninitialize()

    def _on_generate_success(self, result) -> None:
        self._generating = False
        self._set_busy(False, f"완료: {result.output_path.name}")
        self._log(f"생성 완료: {result.output_path}")
        self._log(f"치환된 placeholder: {result.replaced_count}")
        if result.translated_fields:
            self._log(f"자동 번역: {', '.join(result.translated_fields)}")
        if result.remaining_tokens:
            self._log(f"미치환 토큰: {', '.join(result.remaining_tokens)}")
        if result.responsive_stats:
            self._log(
                "교독문 슬라이드: "
                f"{result.responsive_stats['responsive_slides']}장 생성"
            )
        if result.sermon_verse_stats and result.sermon_verse_stats.get("filled"):
            self._log(
                "설교 파트 구절: "
                f"{result.sermon_verse_stats['filled']}개 텍스트 박스 적용"
            )
        if result.scripture_stats:
            self._log(
                "성경 구절 슬라이드: "
                f"{result.scripture_stats['verse_slides']}장 생성"
            )
        if result.youth_sermon_stats:
            action = result.youth_sermon_stats.get("youth_sermon_slide")
            if action == "deleted":
                self._log("Youth Sermon 없음 → 말씀 선포 슬라이드 삭제")
            elif action == "kept":
                self._log(
                    "Youth Sermon: "
                    f"{result.youth_sermon_stats.get('title', '')}"
                )
        if result.hymn_stats:
            if result.hymn_stats.get("background_image"):
                self._log(
                    "찬송 배경: "
                    f"{result.hymn_stats['background_image']} "
                    f"(34-36: {result.hymn_stats.get('fixed_background_slides', 0)} slides)"
                )
            if result.hymn_stats.get("hymn1_file"):
                self._log(
                    "찬송가 삽입: "
                    f"{result.hymn_stats['hymn1_file']} ({result.hymn_stats['hymn1']} slides), "
                    f"{result.hymn_stats['hymn2_file']} ({result.hymn_stats['hymn2']} slides)"
                )
        if result.saved_json:
            self._log(f"JSON 저장: {result.saved_json}")
        if result.thumbnail_path:
            self._log(
                f"Thumbnail 생성: {result.thumbnail_path.name} "
                f"({result.thumbnail_replaced_count} replacements)"
            )
            if result.thumbnail_remaining_tokens:
                self._log(
                    "Thumbnail 미치환 토큰: "
                    f"{', '.join(result.thumbnail_remaining_tokens)}"
                )

        completion_message = f"PPT가 생성되었습니다.\n\n{result.output_path}"
        if result.thumbnail_path:
            completion_message += f"\n\n{result.thumbnail_path}"
        messagebox.showinfo(
            "생성 완료",
            completion_message,
        )

    def _format_error(self, error: Exception) -> str:
        message = str(error).strip()
        if message and message != "None":
            return message
        if error.args:
            parts = [str(arg) for arg in error.args if arg is not None and str(arg).strip()]
            if parts:
                return "; ".join(parts)
        return type(error).__name__

    def _on_generate_error(self, error: Exception) -> None:
        import traceback

        from app_paths import get_app_root

        self._generating = False
        self._set_busy(False, "생성 실패")
        detail = self._format_error(error)
        log_path = get_app_root() / "config" / "generate_error.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"{detail}\n\n{traceback.format_exc()}",
            encoding="utf-8",
        )
        self._log(f"오류: {detail}")
        self._log(f"자세한 로그: {log_path}")
        messagebox.showerror("생성 실패", f"{detail}\n\n자세한 로그:\n{log_path}")

    def _open_output_dir(self) -> None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(DEFAULT_OUTPUT_DIR)])

    def _log(self, message: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

        # Keep the log from growing without bound.
        line_count = int(float(self.log_text.index("end-1c").split(".")[0]))
        if line_count > 120:
            self.log_text.delete("1.0", f"{line_count - 80}.0")

        self.log_text.config(state=tk.DISABLED)


def main() -> None:
    from app_paths import ensure_app_dirs, load_app_env

    ensure_app_dirs()
    load_app_env()

    if not DEFAULT_TEMPLATE.exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "템플릿 없음",
            f"템플릿 파일이 없습니다:\n{DEFAULT_TEMPLATE}",
        )
        root.destroy()
        raise SystemExit(1)

    app = PptApp()
    app.mainloop()


if __name__ == "__main__":
    main()
