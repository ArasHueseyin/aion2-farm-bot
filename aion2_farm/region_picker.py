from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk


class RegionPicker(tk.Toplevel):
    def __init__(self, root, image, instruction, callback):
        super().__init__(root)
        self.title("HUD-Bereich auswählen")
        self.configure(bg="#10151e")
        self.callback = callback
        self.image = image
        self.start = None
        self.box = None
        self.scale = min(1.0, (self.winfo_screenwidth() - 100) / image.width,
                         (self.winfo_screenheight() - 150) / image.height)
        self.photo = ImageTk.PhotoImage(image.resize((round(image.width * self.scale), round(image.height * self.scale)),
                                                    Image.Resampling.BILINEAR))
        ttk.Label(self, text=instruction + "  ·  Mit linker Maustaste einen Rahmen ziehen. Esc bricht ab.",
                  wraplength=self.photo.width() - 30, padding=12).pack(fill="x")
        self.canvas = tk.Canvas(self, width=self.photo.width(), height=self.photo.height(), highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.bind("<ButtonPress-1>", self._down)
        self.canvas.bind("<B1-Motion>", self._move)
        self.canvas.bind("<ButtonRelease-1>", self._up)
        self.bind("<Escape>", lambda event: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.update_idletasks()
        self.geometry(f"+{max(0, (self.winfo_screenwidth() - self.winfo_width()) // 2)}+30")
        self.lift()
        self.grab_set()

    def _down(self, event):
        self.start = (event.x, event.y)
        if self.box:
            self.canvas.delete(self.box)
        self.box = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#58d9b1", width=2)

    def _move(self, event):
        if self.start and self.box:
            self.canvas.coords(self.box, *self.start, event.x, event.y)

    def _up(self, event):
        if self.start is None:
            return
        x1, x2 = sorted((round(self.start[0] / self.scale), round(event.x / self.scale)))
        y1, y2 = sorted((round(self.start[1] / self.scale), round(event.y / self.scale)))
        x1, x2 = max(0, x1), min(self.image.width, x2)
        y1, y2 = max(0, y1), min(self.image.height, y2)
        if x2 - x1 < 3 or y2 - y1 < 3:
            return
        self.callback([x1, y1, x2 - x1, y2 - y1], self.image)
        self.destroy()

    def cancel(self):
        self.callback(None, self.image)
        self.destroy()
