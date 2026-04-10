"""HEIC to PNG Converter — simple desktop app for single and bulk conversion."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

HEIC_EXTENSIONS = {".heic", ".heif"}


class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HEIC → PNG Converter")
        self.resizable(False, False)
        self.configure(padx=20, pady=20)
        self._build_ui()
        self._center_window()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        # --- Single file ---
        single_frame = ttk.LabelFrame(self, text="Single File", padding=12)
        single_frame.pack(fill="x", pady=(0, 12))

        self.single_path = tk.StringVar()
        ttk.Entry(single_frame, textvariable=self.single_path, width=56).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(single_frame, text="Browse…", command=self._browse_file).grid(
            row=0, column=1
        )
        ttk.Button(single_frame, text="Convert", command=self._convert_single).grid(
            row=0, column=2, padx=(8, 0)
        )

        # --- Bulk folder ---
        bulk_frame = ttk.LabelFrame(self, text="Bulk (Folder)", padding=12)
        bulk_frame.pack(fill="x", pady=(0, 12))

        self.bulk_path = tk.StringVar()
        ttk.Entry(bulk_frame, textvariable=self.bulk_path, width=56).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(bulk_frame, text="Browse…", command=self._browse_folder).grid(
            row=0, column=1
        )
        ttk.Button(bulk_frame, text="Convert All", command=self._convert_bulk).grid(
            row=0, column=2, padx=(8, 0)
        )

        # --- Output folder ---
        out_frame = ttk.LabelFrame(self, text="Output Folder (optional)", padding=12)
        out_frame.pack(fill="x", pady=(0, 12))

        self.out_path = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.out_path, width=56).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(out_frame, text="Browse…", command=self._browse_output).grid(
            row=0, column=1
        )

        # --- Conversion settings ---
        settings_frame = ttk.LabelFrame(self, text="Conversion Settings", padding=12)
        settings_frame.pack(fill="x", pady=(0, 12))

        # Row 0: Format + Resize
        ttk.Label(settings_frame, text="Format:").grid(row=0, column=0, sticky="w")
        self.format_var = tk.StringVar(value="PNG")
        fmt_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.format_var,
            values=["PNG", "JPEG", "WebP"],
            state="readonly",
            width=8,
        )
        fmt_combo.grid(row=0, column=1, padx=(4, 16), sticky="w")
        fmt_combo.bind("<<ComboboxSelected>>", self._on_format_changed)

        ttk.Label(settings_frame, text="Max size:").grid(row=0, column=2, sticky="w")
        self.resize_var = tk.StringVar(value="Original")
        ttk.Combobox(
            settings_frame,
            textvariable=self.resize_var,
            values=["Original", "4096", "2048", "1920", "1080"],
            state="readonly",
            width=8,
        ).grid(row=0, column=3, padx=(4, 0), sticky="w")

        # Row 1: Quality slider + metadata checkbox
        self.quality_label = ttk.Label(settings_frame, text="Quality: 85")
        self.quality_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.quality_var = tk.IntVar(value=85)
        self.quality_scale = ttk.Scale(
            settings_frame,
            from_=1,
            to=100,
            variable=self.quality_var,
            command=self._on_quality_changed,
        )
        self.quality_scale.grid(row=1, column=2, columnspan=2, sticky="ew", pady=(8, 0))
        # Hide quality controls initially (PNG is lossless)
        self.quality_label.grid_remove()
        self.quality_scale.grid_remove()

        self.strip_meta_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Strip metadata (EXIF/GPS)", variable=self.strip_meta_var
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        # --- Progress ---
        self.progress = ttk.Progressbar(self, length=480, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(fill="x")

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Settings callbacks ────────────────────────────────────────────

    def _on_format_changed(self, _event=None):
        if self.format_var.get() == "PNG":
            self.quality_label.grid_remove()
            self.quality_scale.grid_remove()
        else:
            self.quality_label.grid()
            self.quality_scale.grid()

    def _on_quality_changed(self, _value=None):
        self.quality_label.config(text=f"Quality: {self.quality_var.get()}")

    # ── Browse helpers ────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select HEIC file",
            filetypes=[("HEIC files", "*.heic *.heif"), ("All files", "*.*")],
        )
        if path:
            self.single_path.set(path)

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select folder with HEIC files")
        if path:
            self.bulk_path.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.out_path.set(path)

    # ── Conversion logic ──────────────────────────────────────────────

    def _output_for(self, src_path: str) -> str:
        """Return the destination path for a given source file."""
        ext_map = {"PNG": ".png", "JPEG": ".jpg", "WebP": ".webp"}
        ext = ext_map[self.format_var.get()]
        src = Path(src_path)
        if self.out_path.get():
            dest_dir = Path(self.out_path.get())
        else:
            dest_dir = src.parent
        return str(dest_dir / (src.stem + ext))

    def _convert_file(self, src: str, dst: str) -> None:
        img = Image.open(src)

        # Resize if requested
        max_dim = self.resize_var.get()
        if max_dim != "Original":
            max_dim = int(max_dim)
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # Strip metadata if requested
        if self.strip_meta_var.get():
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
            img = clean

        # Save with format-specific options
        fmt = self.format_var.get()
        if fmt == "PNG":
            img.save(dst, "PNG", optimize=True, compress_level=9)
        elif fmt == "JPEG":
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(dst, "JPEG", quality=self.quality_var.get(), optimize=True)
        elif fmt == "WebP":
            img.save(dst, "WebP", quality=self.quality_var.get(), method=6)

    # ── Single conversion ─────────────────────────────────────────────

    def _convert_single(self):
        src = self.single_path.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showwarning("No file", "Please select a valid HEIC file.")
            return
        dst = self._output_for(src)
        self.progress["value"] = 0
        self.status_var.set("Converting…")
        threading.Thread(target=self._do_single, args=(src, dst), daemon=True).start()

    def _do_single(self, src, dst):
        try:
            self._convert_file(src, dst)
            self.progress["value"] = 100
            self.status_var.set(f"Saved → {dst}")
            self.after(0, lambda: messagebox.showinfo("Done", f"Saved:\n{dst}"))
        except Exception as exc:
            self.progress["value"] = 0
            self.status_var.set("Error")
            self.after(
                0, lambda: messagebox.showerror("Error", f"Conversion failed:\n{exc}")
            )

    # ── Bulk conversion ───────────────────────────────────────────────

    def _convert_bulk(self):
        folder = self.bulk_path.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No folder", "Please select a valid folder.")
            return

        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if Path(f).suffix.lower() in HEIC_EXTENSIONS
        ]
        if not files:
            messagebox.showinfo("Nothing found", "No HEIC files found in that folder.")
            return

        self.progress["value"] = 0
        self.status_var.set(f"Converting 0/{len(files)}…")
        threading.Thread(target=self._do_bulk, args=(files,), daemon=True).start()

    def _do_bulk(self, files):
        total = len(files)
        errors = []
        for i, src in enumerate(files, 1):
            dst = self._output_for(src)
            try:
                self._convert_file(src, dst)
            except Exception as exc:
                errors.append(f"{os.path.basename(src)}: {exc}")
            pct = int(i / total * 100)
            self.progress["value"] = pct
            self.status_var.set(f"Converting {i}/{total}…")

        if errors:
            self.status_var.set(f"Done with {len(errors)} error(s)")
            msg = "\n".join(errors[:20])
            self.after(
                0,
                lambda: messagebox.showwarning(
                    "Completed with errors", f"{len(errors)} file(s) failed:\n{msg}"
                ),
            )
        else:
            self.status_var.set(f"Done — {total} file(s) converted")
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done", f"Successfully converted {total} file(s)."
                ),
            )


if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()
