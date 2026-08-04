"""
YouTube Bundle Downloader
Developed by Kaushalya

Optional (for MP3 / audio-only downloads, and for merging video+audio into mp4):
    ffmpeg must be installed and available on PATH.
"""

import io
import os
import threading
import webbrowser

import customtkinter as ctk
import requests
import yt_dlp
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

THUMB_SIZE = (80, 45)  # 16:9 small thumbnail

QUALITY_OPTIONS = {
    "Best Quality": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "Audio Only (MP3)": "bestaudio/best",
}

DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "YT_Bundle")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class VideoRow:
    """Represents one video entry in the playlist list."""

    def __init__(self, parent, index, entry):
        self.entry = entry
        self.video_id = entry.get("id")
        self.url = f"https://www.youtube.com/watch?v={self.video_id}" if self.video_id else entry.get("url")
        title = entry.get("title") or "Untitled video"
        duration = entry.get("duration")
        duration_str = self._format_duration(duration)

        self.frame = ctk.CTkFrame(parent, fg_color="#2b2b2b")
        self.frame.pack(fill="x", padx=8, pady=4)

        # Thumbnail placeholder — real image loads asynchronously so the list stays snappy.
        self.thumb_label = ctk.CTkLabel(
            self.frame,
            text="",
            width=THUMB_SIZE[0],
            height=THUMB_SIZE[1],
            fg_color="#1e1e1e",
            corner_radius=4,
        )
        self.thumb_label.pack(side="left", padx=(10, 8), pady=8)
        self._load_thumbnail_async(self._get_thumbnail_url(entry))

        self.var = ctk.BooleanVar(value=True)
        self.checkbox = ctk.CTkCheckBox(
            self.frame,
            text=f"{index}. {title}  [{duration_str}]",
            variable=self.var,
            font=("Segoe UI", 12),
        )
        self.checkbox.pack(side="left", padx=10, pady=8, fill="x", expand=True)

        self.preview_btn = ctk.CTkButton(
            self.frame,
            text="Preview",
            width=80,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            command=self.preview,
        )
        self.preview_btn.pack(side="right", padx=10, pady=8)

    @staticmethod
    def _get_thumbnail_url(entry):
        # yt-dlp gives either a single 'thumbnail' or a 'thumbnails' list — try both.
        if entry.get("thumbnail"):
            return entry["thumbnail"]
        thumbs = entry.get("thumbnails") or []
        if thumbs:
            return thumbs[-1].get("url")
        vid = entry.get("id")
        return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else None

    def _load_thumbnail_async(self, url):
        if not url:
            return
        threading.Thread(target=self._fetch_thumbnail, args=(url,), daemon=True).start()

    def _fetch_thumbnail(self, url):
        try:
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img = img.resize(THUMB_SIZE, Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=THUMB_SIZE)
            # Update the label back on the main thread.
            self.frame.after(0, lambda: self._set_thumbnail(ctk_img))
        except Exception:
            pass  # Thumbnail is a nice-to-have — silently skip on failure.

    def _set_thumbnail(self, ctk_img):
        self.thumb_label.configure(image=ctk_img, text="")
        self.thumb_label.image = ctk_img  # keep a reference alive

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return "--:--"
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def preview(self):
        # Opens the video in the default browser so the user can watch before downloading.
        if self.url:
            webbrowser.open(self.url)

    def is_selected(self):
        return self.var.get()


class YouTubeBundleDownloader:
    def __init__(self):
        self.app = ctk.CTk()
        self.app.title("YouTube Bundle Downloader")
        self.app.geometry("650x650")

        self.video_rows = []

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        header = ctk.CTkLabel(
            self.app, text="YouTube Bundle Downloader", font=("Segoe UI", 20, "bold")
        )
        header.pack(pady=(15, 5))

        url_frame = ctk.CTkFrame(self.app, fg_color="transparent")
        url_frame.pack(fill="x", padx=20, pady=(5, 10))

        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="Enter YouTube Playlist / Video URL", width=420
        )
        self.url_entry.pack(side="left", padx=(0, 10), fill="x", expand=True)

        self.load_btn = ctk.CTkButton(url_frame, text="View", width=90, command=self.load_playlist)
        self.load_btn.pack(side="right")

        # Quality + select-all row
        options_frame = ctk.CTkFrame(self.app, fg_color="transparent")
        options_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(options_frame, text="Quality:").pack(side="left", padx=(0, 5))
        self.quality_menu = ctk.CTkOptionMenu(options_frame, values=list(QUALITY_OPTIONS.keys()))
        self.quality_menu.set("720p")
        self.quality_menu.pack(side="left", padx=(0, 20))

        self.select_all_btn = ctk.CTkButton(
            options_frame, text="Select All", width=90, command=self.select_all
        )
        self.select_all_btn.pack(side="left", padx=(0, 5))

        self.deselect_all_btn = ctk.CTkButton(
            options_frame, text="Deselect All", width=100, command=self.deselect_all
        )
        self.deselect_all_btn.pack(side="left")

        # Scrollable list of videos
        self.list_frame = ctk.CTkScrollableFrame(self.app, label_text="Playlist Videos")
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Status + progress
        self.status_label = ctk.CTkLabel(self.app, text="Enter a playlist URL and click View.")
        self.status_label.pack(pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(self.app, width=500)
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=(0, 10))

        # Download button
        self.download_btn = ctk.CTkButton(
            self.app, text="Download Selected", command=self.start_download, height=38
        )
        self.download_btn.pack(pady=(0, 5))

        # Footer credit
        footer = ctk.CTkLabel(
            self.app,
            text="Developed by Kaushalya",
            font=("Segoe UI", 11, "italic"),
            text_color="#888888",
        )
        footer.pack(pady=(5, 10))

    # ---------- Playlist loading ----------
    def load_playlist(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_label.configure(text="Please enter a URL first.")
            return

        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.video_rows.clear()

        self.status_label.configure(text="Loading playlist, please wait...")
        self.load_btn.configure(state="disabled")

        threading.Thread(target=self._fetch_playlist, args=(url,), daemon=True).start()

    def _fetch_playlist(self, url):
        ydl_opts = {"quiet": True, "extract_flat": True, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            entries = info.get("entries") if info.get("entries") is not None else [info]
            entries = [e for e in entries if e]
            self.app.after(0, lambda: self._populate_list(entries))
        except Exception as e:
            self.app.after(0, lambda: self.status_label.configure(text=f"Error: {e}"))
            self.app.after(0, lambda: self.load_btn.configure(state="normal"))

    def _populate_list(self, entries):
        for i, entry in enumerate(entries, start=1):
            row = VideoRow(self.list_frame, i, entry)
            self.video_rows.append(row)
        self.status_label.configure(text=f"Found {len(entries)} video(s). Select what you want and download.")
        self.load_btn.configure(state="normal")

    def select_all(self):
        for row in self.video_rows:
            row.var.set(True)

    def deselect_all(self):
        for row in self.video_rows:
            row.var.set(False)

    # ---------- Downloading ----------
    def start_download(self):
        selected = [row for row in self.video_rows if row.is_selected()]
        if not selected:
            self.status_label.configure(text="No videos selected.")
            return

        self.download_btn.configure(state="disabled")
        quality_key = self.quality_menu.get()
        format_str = QUALITY_OPTIONS[quality_key]

        threading.Thread(
            target=self._download_videos, args=(selected, format_str, quality_key), daemon=True
        ).start()

    def _download_videos(self, rows, format_str, quality_key):
        total = len(rows)
        for idx, row in enumerate(rows, start=1):
            self.app.after(0, lambda t=row.entry.get("title", "video"), i=idx: self.status_label.configure(
                text=f"Downloading ({i}/{total}): {t}"
            ))

            ydl_opts = {
                "format": format_str,
                "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
                "quiet": True,
                "noplaylist": True,
                "merge_output_format": "mp4",
            }

            if quality_key == "Audio Only (MP3)":
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([row.url])
            except Exception as e:
                self.app.after(0, lambda err=str(e), t=row.entry.get("title", "video"): self.status_label.configure(
                    text=f"Failed: {t} ({err})"
                ))
                continue

            self.app.after(0, lambda i=idx, t=total: self.progress_bar.set(i / t))

        self.app.after(0, lambda: self.status_label.configure(
            text=f"Done! {total} video(s) saved to {DOWNLOAD_DIR}"
        ))
        self.app.after(0, lambda: self.download_btn.configure(state="normal"))

    def run(self):
        self.app.mainloop()


if __name__ == "__main__":
    YouTubeBundleDownloader().run()