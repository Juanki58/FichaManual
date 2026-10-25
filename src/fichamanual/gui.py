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
from .report import save_summary_docx
from .summarizer import (
    LENGTH_LONG,
    LENGTH_MEDIUM,
    LENGTH_SHORT,
    summarize_manual,
)


APP_TITLE = "FichaManual"
APP_MIN_SIZE = (980, 640)

_LENGTH_UI = (
    ("Corto", LENGTH_SHORT),
    ("Medio", LENGTH_MEDIUM),
    ("Detallado", LENGTH_LONG),
)


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
        self._api_disclosure_accepted = False
        self.source_name = "Texto pegado"
        self._last_engine_label = "Motor local"
        self._build_ui()

    def _build_ui(self) -> None:
        self.master.title(APP_TITLE)
        self.master.minsize(*APP_MIN_SIZE)
        self.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text="FichaManual", font=("Segoe UI", 20, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Label(
            header,
            text="Resume y ordena textos / manuales en una ficha clara",
            font=("Segoe UI", 11),
        ).pack(side=tk.LEFT, padx=(12, 0))

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="Abrir archivo...", command=self.open_file).pack(
            side=tk.LEFT
        )
        ttk.Button(toolbar, text="Pegar portapapeles", command=self.paste_clipboard).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Button(toolbar, text="Limpiar", command=self.clear_input).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        # API solo tras elección explícita; al activarla se informa del envío del texto.
        self.use_api = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            toolbar,
            text="Usar API (OPENAI_API_KEY)",
            variable=self.use_api,
            command=self._on_api_toggle,
        ).pack(side=tk.LEFT, padx=(16, 0))

        length_box = ttk.Frame(toolbar)
        length_box.pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(length_box, text="Longitud:").pack(side=tk.LEFT)
        self.length_var = tk.StringVar(value=LENGTH_MEDIUM)
        for label, value in _LENGTH_UI:
            ttk.Radiobutton(
                length_box,
                text=label,
                value=value,
                variable=self.length_var,
            ).pack(side=tk.LEFT, padx=(6, 0))

        self.btn_summarize = ttk.Button(
            toolbar, text="Crear ficha", command=self.start_summary
        )
        self.btn_summarize.pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Limpiar ficha", command=self.clear_output).pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Copiar ficha", command=self.copy_output).pack(
            side=tk.RIGHT, padx=(0, 6)
        )
        ttk.Button(toolbar, text="Guardar ficha...", command=self.save_output).pack(
            side=tk.RIGHT, padx=(0, 6)
        )

        panes = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(panes, padding=(0, 0, 6, 0))
        right = ttk.Frame(panes, padding=(6, 0, 0, 0))
        panes.add(left, weight=1)
        panes.add(right, weight=1)

        ttk.Label(left, text="Texto / manual", font=("Segoe UI", 10)).pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(
            left, wrap=tk.WORD, font=("Segoe UI", 11), undo=True
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        # Ctrl+V / menú Pegar: recordar que hay que pulsar «Crear ficha».
        self.input_text.bind("<<Paste>>", self._on_input_paste, add="+")

        ttk.Label(right, text="Ficha resumen", font=("Segoe UI", 10)).pack(anchor=tk.W)
        self.output_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Segoe UI", 13), undo=True
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.status = ttk.Label(self, text="", relief=tk.SUNKEN, anchor=tk.W, padding=4)
        self.status.pack(fill=tk.X, pady=(8, 0))

        tip = (
            "Motor local listo. Activa «Usar API» si quieres procesar el texto con OpenAI. "
            "Pega o escribe el texto y pulsa «Crear ficha»."
        )
        self._set_status(f"Listo. {tip}")

    def _set_status(self, message: str) -> None:
        self.status.configure(text=message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.btn_summarize.configure(state=(tk.DISABLED if busy else tk.NORMAL))

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Abrir texto o manual",
            filetypes=[
                ("Documentos compatibles", "*.txt *.md *.markdown *.docx *.pdf"),
                ("Texto", "*.txt"),
                ("Markdown", "*.md *.markdown"),
                ("Word", "*.docx"),
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
        self.source_name = Path(path).name
        self._set_status(
            f"Cargado: {Path(path).name} ({len(text)} caracteres). "
            "Pulsa «Crear ficha»."
        )

    def paste_clipboard(self) -> None:
        try:
            text = self.master.clipboard_get()
        except tk.TclError:
            messagebox.showinfo(APP_TITLE, "El portapapeles está vacío.")
            return
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, text)
        self.source_name = "Texto pegado"
        self._set_status(
            f"Texto pegado ({len(text)} caracteres). Pulsa «Crear ficha»."
        )

    def _on_input_paste(self, _event: object = None) -> None:
        """Tras Ctrl+V u otro pegado nativo, indicar el siguiente paso."""
        if self._busy:
            return
        self.source_name = "Texto pegado"
        self.master.after(50, self._remind_create_ficha)

    def _remind_create_ficha(self) -> None:
        if self._busy:
            return
        raw = self.input_text.get("1.0", tk.END).strip()
        if raw:
            self._set_status(
                f"Texto listo ({len(raw)} caracteres). Pulsa «Crear ficha»."
            )

    def clear_input(self) -> None:
        self.input_text.delete("1.0", tk.END)
        self.source_name = "Texto pegado"
        self._set_status("Entrada limpia.")

    def clear_output(self) -> None:
        self.output_text.delete("1.0", tk.END)
        self._set_status("Ficha limpiada.")

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
            defaultextension=".docx",
            filetypes=[("Informe Word", "*.docx"), ("Texto", "*.txt"), ("Markdown", "*.md"), ("Todos", "*.*")],
            initialfile="sintesis-ejecutiva.docx",
        )
        if not path:
            return
        try:
            if Path(path).suffix.lower() == ".docx":
                save_summary_docx(text, path, source_name=self.source_name, engine=self._last_engine_label)
            else:
                Path(path).write_text(text + "\n", encoding="utf-8")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"No se pudo guardar el archivo.\n\n{exc}")
            return
        self._set_status(f"Guardado: {Path(path).name}")

    def _on_api_toggle(self) -> None:
        if not self.use_api.get() or self._api_disclosure_accepted:
            return
        if not os.getenv("OPENAI_API_KEY", "").strip():
            messagebox.showinfo(
                "API no configurada",
                "Para usar OpenAI API, primero hay que configurar OPENAI_API_KEY. "
                "Mientras tanto puedes crear síntesis con el motor local.",
            )
            self.use_api.set(False)
            return
        accepted = messagebox.askyesno(
            "Procesamiento con OpenAI API",
            "Al crear la ficha, el texto se enviará a OpenAI API para generar el resumen. "
            "Comprueba que tienes autorización para compartir ese contenido y que tu política "
            "lo permite. El uso puede generar costes asociados a la clave configurada.\n\n"
            "¿Quieres continuar usando la API?",
        )
        if accepted:
            self._api_disclosure_accepted = True
        else:
            self.use_api.set(False)

    def start_summary(self) -> None:
        if self._busy:
            return
        raw = self.input_text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showinfo(APP_TITLE, "Pega o abre un texto primero.")
            return
        self._set_busy(True)
        use_api = bool(self.use_api.get())
        length = self.length_var.get() or LENGTH_MEDIUM
        length_label = next(
            (lab for lab, val in _LENGTH_UI if val == length), "Medio"
        )
        has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
        if use_api and not has_key:
            self._set_status(
                f"Sin OPENAI_API_KEY: generando ficha {length_label.lower()} "
                "con motor local..."
            )
        elif use_api:
            self._set_status(f"Generando ficha {length_label.lower()} con API...")
        else:
            self._set_status(
                f"Generando ficha {length_label.lower()} con motor local..."
            )

        def worker() -> None:
            try:
                result = summarize_manual(raw, use_api=use_api, length=length)
                fixed = correct_text(result.text)
                engine = result.engine
                note = result.note
                self.master.after(
                    0, lambda: self._on_success(fixed, engine, note)
                )
            except Exception as exc:
                msg = str(exc)
                self.master.after(0, lambda m=msg: self._on_error(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, text: str, engine: str, note: str = "") -> None:
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self._last_engine_label = "OpenAI API" if engine == "api" else "Motor local"
        if note:
            self._set_status(note)
        else:
            label = "API OpenAI" if engine == "api" else "motor local"
            self._set_status(f"Ficha lista ({label}).")
        self._set_busy(False)

    def _on_error(self, message: str) -> None:
        self._set_busy(False)
        self._set_status("Error al generar la ficha. Revisa el mensaje.")
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
            root._icon_img = img
        except tk.TclError:
            pass

    FichaManualApp(root)
    root.mainloop()
