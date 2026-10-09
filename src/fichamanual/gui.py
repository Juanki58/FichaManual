"""Interfaz de escritorio de FichaManual."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .corrector import correct_text
from .extractor import extract_text
from .summarizer import summarize_manual


APP_TITLE = "FichaManual"
APP_MIN_SIZE = (980, 640)


def _resource_path(*parts: str) -> Path:
    """Ruta a recursos: desarrollo o empaquetado PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]
    return base.joinpath(*parts)


class FichaManualApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self._busy = False
        self._build_ui()
        self._set_status("Listo. Pega un manual o abre un archivo .txt / .pdf.")

    def _build_ui(self) -> None:
        self.master.title(APP_TITLE)
        self.master.minsize(*APP_MIN_SIZE)
        self.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="FichaManual", font=("Segoe UI", 18, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Label(
            header,
            text="Resume y ordena manuales largos en una ficha clara",
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(12, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="Abrir archivo…", command=self.open_file).pack(
            side=tk.LEFT
        )
        ttk.Button(toolbar, text="Pegar portapapeles", command=self.paste_clipboard).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(toolbar, text="Limpiar", command=self.clear_input).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        self.use_api = tk.BooleanVar(value=bool(os.getenv("OPENAI_API_KEY", "").strip()))
        ttk.Checkbutton(
            toolbar,
            text="Usar API (OPENAI_API_KEY)",
            variable=self.use_api,
        ).pack(side=tk.LEFT, padx=(16, 0))

        self.btn_summarize = ttk.Button(
            toolbar, text="Crear ficha", command=self.start_summary
        )
        self.btn_summarize.pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Copiar ficha", command=self.copy_output).pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Guardar ficha…", command=self.save_output).pack(
            side=tk.RIGHT, padx=(0, 6)
        )

        panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes, padding=(0, 0, 6, 0))
        right = ttk.Frame(panes, padding=(6, 0, 0, 0))
        panes.add(left, weight=1)
        panes.add(right, weight=1)

        ttk.Label(left, text="Texto del manual").pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(
            left, wrap=tk.WORD, font=("Consolas", 10), undo=True
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        ttk.Label(right, text="Ficha resumen").pack(anchor=tk.W)
        self.output_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Segoe UI", 10), undo=True
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.status = ttk.Label(self, text="", relief=tk.SUNKEN, anchor=tk.W, padding=4)
        self.status.pack(fill=tk.X, pady=(8, 0))

        has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
        tip = "API detectada." if has_key else "Sin API: se usará el motor local."
        self._set_status(f"Listo. {tip}")

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.btn_summarize.configure(state=state)

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Abrir manual",
            filetypes=[
                ("Manuales", "*.txt *.pdf"),
                ("Texto", "*.txt"),
                ("PDF", "*.pdf"),
                ("Todos", "*.*"),
            ],
        )
        if not path:
            return
        try:
            text = extract_text(path)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, text)
        self._set_status(f"Cargado: {Path(path).name} ({len(text)} caracteres)")

    def paste_clipboard(self) -> None:
        try:
            text = self.master.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(APP_TITLE, "El portapapeles está vacío.")
            return
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, text)
        self._set_status(f"Texto pegado ({len(text)} caracteres)")

    def clear_input(self) -> None:
        self.input_text.delete("1.0", tk.END)
        self._set_status("Entrada limpia.")

    def copy_output(self) -> None:
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo(APP_TITLE, "No hay ficha para copiar.")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        self._set_status("Ficha copiada al portapapeles.")

    def save_output(self) -> None:
        text = self.output_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo(APP_TITLE, "No hay ficha para guardar.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar ficha",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Markdown", "*.md"), ("Todos", "*.*")],
            initialfile="ficha-manual.txt",
        )
        if not path:
            return
        Path(path).write_text(text + "\n", encoding="utf-8")
        self._set_status(f"Guardado: {Path(path).name}")

    def start_summary(self) -> None:
        if self._busy:
            return
        raw = self.input_text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showinfo(APP_TITLE, "Pega o abre un manual primero.")
            return
        self._set_busy(True)
        self._set_status("Generando ficha…")
        use_api = bool(self.use_api.get())

        def worker() -> None:
            try:
                result = summarize_manual(raw, use_api=use_api)
                fixed = correct_text(result.text)
                self.master.after(0, lambda: self._on_success(fixed, result.engine))
            except Exception as exc:
                self.master.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, text: str, engine: str) -> None:
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        label = "API OpenAI" if engine == "api" else "motor local"
        self._set_status(f"Ficha lista ({label}).")
        self._set_busy(False)

    def _on_error(self, message: str) -> None:
        self._set_busy(False)
        self._set_status("Error al generar la ficha.")
        messagebox.showerror(APP_TITLE, message)


def run_app() -> None:
    root = tk.Tk()
    try:
        root.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass

    icon_ico = _resource_path("assets", "fichamanual.ico")
    icon_png = _resource_path("assets", "fichamanual.png")
    if icon_ico.exists():
        try:
            root.iconbitmap(default=str(icon_ico))
        except tk.TclError:
            pass
    if icon_png.exists():
        try:
            img = tk.PhotoImage(file=str(icon_png))
            root.iconphoto(True, img)
            root._icon_img = img  # noqa: SLF001 — evitar GC
        except tk.TclError:
            pass

    FichaManualApp(root)
    root.mainloop()
