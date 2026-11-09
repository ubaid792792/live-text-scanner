#!/usr/bin/env python3
"""
LiveText Scanner - Real-time OCR application
A cross-platform GUI application that captures camera feed, performs
real-time text recognition, and allows copying detected text.

Based on the Android LiveText Scanner app by Google AI Studio.

Dependencies:
  pip install opencv-python pillow pytesseract pyperclip numpy

Also install Tesseract OCR:
  macOS: brew install tesseract
  Ubuntu/Debian: sudo apt install tesseract-ocr
  Windows: https://github.com/UB-Mannheim/tesseract/wiki
"""

import tkinter as tk
from tkinter import ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import pytesseract
import pyperclip
import threading
import time
import re
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple
from enum import Enum

# ── Color Constants (matching Android app's dark theme) ──────────────
DARK_BG = "#09090B"
PANEL_BG = "#171717"
EMERALD_400 = "#34D399"
EMERALD_500 = "#10B981"
OVERLAY_FILL = "#2D8B6D"
OVERLAY_BORDER = "#34D399"
OVERLAY_UNSELECTED_FILL = "#2A2A2E"
OVERLAY_UNSELECTED_BORDER = "#555555"
SCAN_BORDER = "#999999"
SCRIM_COLOR = "#2A2A2E"
HANDLE_COLOR = "#34D399"
HANDLE_OUTLINE = "#FFFFFF"
TEXT_COLOR = "#FFFFFF"
TEXT_SECONDARY = "#A1A1AA"
BUTTON_BG = "#333333"
WHITE = "#FFFFFF"

# ── Geometry ──────────────────────────────────────────────────────────
CORNER_BRACKET_SIZE = 60
HANDLE_RADIUS = 18
TOUCH_RADIUS = 80
TOUCH_SLOP = 12
MIN_SCAN_SIZE = 150
OCR_INTERVAL = 0.12
SMOOTHING_ALPHA = 0.32
BLOCK_LIFE_CYCLES = 5
FRAME_BURST_SIZE = 6
MIN_OCR_HEIGHT = 650
MAX_OCR_WIDTH = 1500
MAX_OCR_HEIGHT = 1100
HIGHLIGHT_ALPHA = 0.16
CAM_WIDTH = 1920
CAM_HEIGHT = 1080


class TouchMode(Enum):
    NONE = 0
    RESIZING_TOP_LEFT = 1
    RESIZING_TOP_RIGHT = 2
    RESIZING_BOTTOM_LEFT = 3
    RESIZING_BOTTOM_RIGHT = 4
    MOVING_RECT = 5


@dataclass
class OverlayBlock:
    rect: Tuple[float, float, float, float]
    text: str
    is_selected: bool = True


@dataclass
class TrackedBlock:
    rect: Tuple[float, float, float, float]
    text: str
    is_selected: bool = True
    confidence: float = 0.0
    age: int = 0
    smoothed_rect: Optional[Tuple[float, float, float, float]] = None


@dataclass
class ScanRect:
    left: float = 0
    top: float = 0
    right: float = 0
    bottom: float = 0


class LiveTextScanner:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LiveText Scanner")
        self.root.geometry("480x800")
        self.root.configure(bg=DARK_BG)
        self.root.minsize(360, 600)

        # State
        self.running = True
        self.is_paused = False
        self.is_front_camera = False
        self.is_reversed = False
        self.current_camera_id = 0

        # Threading
        self.frame_lock = threading.Lock()
        self.latest_frame: Optional[np.ndarray] = None
        self.frame_buffer: Deque[np.ndarray] = deque(maxlen=FRAME_BURST_SIZE)
        self.ocr_lock = threading.Lock()
        self.latest_blocks: List[OverlayBlock] = []
        self.all_text: str = ""
        self.selected_text: str = ""

        # Touch state
        self.touch_mode = TouchMode.NONE
        self.drag_start_x = 0.0
        self.drag_start_y = 0.0
        self.last_touch_x = 0.0
        self.last_touch_y = 0.0
        self.is_dragging = False

        # Coordinate system
        self.frame_w = CAM_WIDTH
        self.frame_h = CAM_HEIGHT
        self.canvas_w = 0
        self.canvas_h = 0
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.scan_rect = ScanRect()
        self.camera_error = ""

        # Temporal smoothing & block tracking
        self.tracked_blocks: Dict[Tuple, "TrackedBlock"] = {}
        self.prev_frame_gray: Optional[np.ndarray] = None
        self.prev_ocr_roi: Optional[np.ndarray] = None

        # Build UI
        self._build_ui()

        # Start threads
        self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.camera_thread.start()
        self.ocr_thread = threading.Thread(target=self._ocr_loop, daemon=True)
        self.ocr_thread.start()

        # Start display loop
        self._update_display()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI Building ───────────────────────────────────────────────────

    def _build_ui(self):
        # Top toolbar
        toolbar = tk.Frame(self.root, bg=DARK_BG, height=56)
        toolbar.pack(fill=tk.X, padx=4, pady=(4, 0))

        self._make_tool_button(toolbar, "\u21C4", "Switch camera", self._switch_camera).pack(side=tk.LEFT, padx=2)
        self.btn_pause = self._make_tool_button(toolbar, "\u23F8", "Pause/Resume", self._toggle_pause)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        self.btn_reverse = self._make_tool_button(toolbar, "\u21C5", "Reverse order", self._toggle_reverse)
        self.btn_reverse.pack(side=tk.LEFT, padx=2)
        self._make_tool_button(toolbar, "\u2398", "Copy text", self._copy_text).pack(side=tk.RIGHT, padx=2)

        # Camera preview + overlay
        self.canvas = tk.Canvas(self.root, bg=DARK_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.canvas.bind("<Button-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Bottom panel
        bottom_frame = tk.Frame(self.root, bg=PANEL_BG)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Status bar
        status_frame = tk.Frame(bottom_frame, bg=PANEL_BG)
        status_frame.pack(fill=tk.X, padx=16, pady=(8, 4))

        self.scanning_dot = tk.Canvas(status_frame, width=10, height=10, bg=PANEL_BG, highlightthickness=0)
        self.scanning_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_id = self.scanning_dot.create_oval(0, 0, 10, 10, fill=EMERALD_400, outline="")

        self.status_label = tk.Label(status_frame, text="LIVE SCANNING", fg=EMERALD_400, bg=PANEL_BG,
                                     font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side=tk.LEFT)

        # Text preview
        preview_label = tk.Label(bottom_frame, text="Detected Text", fg=TEXT_SECONDARY, bg=PANEL_BG,
                                 font=("Segoe UI", 10), anchor=tk.W)
        preview_label.pack(fill=tk.X, padx=16, pady=(4, 0))

        self.text_preview = tk.Text(bottom_frame, height=5, bg="#1A1A1E", fg=TEXT_COLOR,
                                    font=("Segoe UI", 11), wrap=tk.WORD, relief=tk.FLAT,
                                    padx=8, pady=8, highlightthickness=0,
                                    borderwidth=0, insertbackground=TEXT_COLOR)
        self.text_preview.pack(fill=tk.X, padx=12, pady=(4, 12))
        self.text_preview.insert("1.0", "...")
        self.text_preview.configure(state=tk.DISABLED)

    def _make_tool_button(self, parent, text, tooltip, command):
        btn = tk.Label(parent, text=text, fg=TEXT_COLOR, bg=BUTTON_BG,
                       font=("Segoe UI", 16), padx=12, pady=8, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg="#33FFFFFF"))
        btn.bind("<Leave>", lambda e: btn.configure(bg=BUTTON_BG))
        return btn

    def _status_text(self):
        if self.is_paused:
            return "SCANNING PAUSED"
        return "LIVE SCANNING"

    def _status_color(self):
        if self.is_paused:
            return "#FF8C00"
        return EMERALD_400

    def _update_status(self):
        color = self._status_color()
        self.status_label.configure(text=self._status_text(), fg=color)
        self.scanning_dot.itemconfig(self.dot_id, fill=color, outline=color)
        icon = "\u25B6" if self.is_paused else "\u23F8"
        self.btn_pause.configure(text=icon)

        rev_bg = EMERALD_400 if self.is_reversed else BUTTON_BG
        rev_fg = DARK_BG if self.is_reversed else TEXT_COLOR
        self.btn_reverse.configure(bg=rev_bg, fg=rev_fg)

    # ── Camera ────────────────────────────────────────────────────────

    def _open_camera(self, camera_id: int) -> Optional[cv2.VideoCapture]:
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Try to set auto-focus
        cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        return cap

    def _camera_loop(self):
        cap = None
        for attempt in range(30):
            if not self.running:
                return
            cap = self._open_camera(self.current_camera_id)
            if cap is not None:
                break
            time.sleep(1.0)

        if cap is None:
            self.camera_error = "Camera not found.\nCheck camera permissions:\nSystem Settings > Privacy > Camera"
            return

        self.camera_error = ""

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            if self.is_front_camera:
                frame = cv2.flip(frame, 1)

            with self.frame_lock:
                self.latest_frame = frame
                self.frame_buffer.append(frame.copy())
                self.frame_h, self.frame_w = frame.shape[:2]

            time.sleep(0.005)

        cap.release()

    def _switch_camera(self):
        alt_id = 1 if self.current_camera_id == 0 else 0
        test = self._open_camera(alt_id)
        if test is not None:
            test.release()
            self.current_camera_id = alt_id
            self.is_front_camera = (alt_id != 0)
        else:
            # If alt camera fails just toggle front flag for mirroring
            self.is_front_camera = not self.is_front_camera

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        self.root.after(0, self._update_status)

    def _toggle_reverse(self):
        self.is_reversed = not self.is_reversed
        self._refilter_text()
        self.root.after(0, self._update_status)

    # ── OCR ───────────────────────────────────────────────────────────

    def _compute_blur_score(self, img: np.ndarray) -> float:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def _preprocess_adaptive(self, img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.bilateralFilter(gray, 5, 35, 35)
        gray = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 9
        )
        return gray

    def _preprocess_raw(self, img: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        blurred = cv2.GaussianBlur(gray, (0, 0), 1.2)
        gray = cv2.addWeighted(gray, 1.8, blurred, -0.8, 0)
        return gray

    def _preprocess_natural(self, img: np.ndarray) -> np.ndarray:
        """Preserve normal letter shapes for clean, well-lit English text."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        return cv2.fastNlMeansDenoising(gray, None, 7, 7, 21)

    def _best_frame_from_burst(self) -> Optional[np.ndarray]:
        """Select a crisp recent frame instead of rejecting a shaky instant."""
        with self.frame_lock:
            frames = list(self.frame_buffer)
        if not frames:
            return None
        return max(frames, key=lambda frame: self._compute_blur_score(
            cv2.resize(frame, None, fx=0.25, fy=0.25,
                       interpolation=cv2.INTER_AREA)
        )).copy()

    def _prepare_ocr_image(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """Upscale small text and return the scale for correcting OCR boxes."""
        h, w = img.shape[:2]
        scale = max(1.0, min(2.0, MIN_OCR_HEIGHT / max(1, h)))
        scale = min(scale, MAX_OCR_WIDTH / max(1, w),
                    MAX_OCR_HEIGHT / max(1, h))
        if abs(scale - 1.0) > 0.01:
            img = cv2.resize(img, None, fx=scale, fy=scale,
                             interpolation=(cv2.INTER_CUBIC if scale > 1
                                            else cv2.INTER_AREA))
        return img, scale

    def _rescale_ocr_data(self, data: dict, scale: float) -> dict:
        if abs(scale - 1.0) <= 0.01:
            return data
        result = dict(data)
        for key in ("left", "top", "width", "height"):
            result[key] = [int(round(float(v) / scale)) for v in data[key]]
        return result

    def _isolate_document(
            self, img: np.ndarray) -> Tuple[np.ndarray, int, int, bool]:
        """Crop and mask a visible page so background texture is not sent to OCR."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        if h < 80 or w < 80:
            return img, 0, 0, False

        blurred = cv2.GaussianBlur(gray, (9, 9), 0)
        _, bright = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel_size = max(9, int(min(h, w) * 0.025) | 1)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (kernel_size, kernel_size))
        bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel,
                                  iterations=2)

        contours, _ = cv2.findContours(
            bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        image_area = h * w
        candidates = [
            contour for contour in contours
            if cv2.contourArea(contour) >= image_area * 0.06
        ]
        if not candidates:
            return img, 0, 0, False

        contour = max(candidates, key=cv2.contourArea)
        contour_area = cv2.contourArea(contour)
        if contour_area > image_area * 0.92:
            return img, 0, 0, False

        hull = cv2.convexHull(contour)
        x, y, box_w, box_h = cv2.boundingRect(hull)
        if box_w < 80 or box_h < 80:
            return img, 0, 0, False

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillConvexPoly(mask, hull, 255)
        # White outside the page is neutral for Tesseract; black background
        # otherwise generates hundreds of false character-like components.
        isolated = np.full_like(img, 255)
        isolated[mask > 0] = img[mask > 0]
        return isolated[y:y + box_h, x:x + box_w], x, y, True

    def _estimate_motion(self, previous: np.ndarray,
                         current: np.ndarray) -> Tuple[float, float]:
        """Estimate small camera/page movement between OCR cycles."""
        try:
            size = (320, 180)
            before = cv2.resize(previous, size, interpolation=cv2.INTER_AREA)
            after = cv2.resize(current, size, interpolation=cv2.INTER_AREA)
            before = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY).astype(np.float32)
            after = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY).astype(np.float32)
            (dx, dy), response = cv2.phaseCorrelate(before, after)
            if response < 0.08 or abs(dx) > 70 or abs(dy) > 50:
                return 0.0, 0.0
            return (dx * current.shape[1] / size[0],
                    dy * current.shape[0] / size[1])
        except cv2.error:
            return 0.0, 0.0

    def _shift_tracked_blocks(self, blocks: List[TrackedBlock],
                              dx: float, dy: float) -> None:
        for block in blocks:
            x1, y1, x2, y2 = block.rect
            block.rect = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
            if block.smoothed_rect:
                x1, y1, x2, y2 = block.smoothed_rect
                block.smoothed_rect = (x1 + dx, y1 + dy,
                                       x2 + dx, y2 + dy)

    def _run_ocr_once(self, img: np.ndarray, page_segmentation: int) -> dict:
        try:
            return pytesseract.image_to_data(
                img,
                output_type=pytesseract.Output.DICT,
                config=f"--oem 3 --psm {page_segmentation} --dpi 300",
            )
        except Exception:
            return {"text": [], "conf": [], "left": [], "top": [],
                    "width": [], "height": [], "level": [],
                    "block_num": [], "line_num": [], "par_num": []}

    def _ocr_quality(self, data: dict) -> float:
        """Score complete, readable text above symbol-heavy false detections."""
        words = []
        for text, confidence in zip(data.get("text", []), data.get("conf", [])):
            text = text.strip()
            confidence = float(confidence)
            if text and confidence >= 20 and re.search(r"[A-Za-z0-9]", text):
                words.append((text, confidence))
        if not words:
            return 0.0
        confidence_score = sum(c for _, c in words) / len(words)
        characters = "".join(text for text, _ in words)
        readable_ratio = (sum(ch.isalnum() for ch in characters) /
                          max(1, len(characters)))
        return confidence_score + min(len(words), 35) * 1.25 + readable_ratio * 18

    def _match_blocks(self, new_blocks: List[TrackedBlock],
                      old_blocks: List[TrackedBlock]) -> List[TrackedBlock]:
        if not old_blocks:
            for b in new_blocks:
                b.age = 1
                b.smoothed_rect = b.rect
            return new_blocks

        matched_new = [False] * len(new_blocks)
        matched_old = [False] * len(old_blocks)
        results = []

        for i, new_b in enumerate(new_blocks):
            best_iou = 0.0
            best_j = -1
            nx1, ny1, nx2, ny2 = new_b.rect
            n_area = max(1, (nx2 - nx1) * (ny2 - ny1))
            for j, old_b in enumerate(old_blocks):
                if matched_old[j]:
                    continue
                ox1, oy1, ox2, oy2 = old_b.rect
                ox1s, oy1s, ox2s, oy2s = old_b.smoothed_rect or old_b.rect
                ix1 = max(nx1, ox1s)
                iy1 = max(ny1, oy1s)
                ix2 = min(nx2, ox2s)
                iy2 = min(ny2, oy2s)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    o_area = max(1, (ox2s - ox1s) * (oy2s - oy1s))
                    iou = inter / (n_area + o_area - inter)
                    if iou > best_iou:
                        best_iou = iou
                        best_j = j
            if best_iou > 0.3 and best_j >= 0:
                matched_new[i] = True
                matched_old[best_j] = True
                old_b = old_blocks[best_j]
                alpha = SMOOTHING_ALPHA
                sx1 = old_b.smoothed_rect[0] * (1 - alpha) + nx1 * alpha
                sy1 = old_b.smoothed_rect[1] * (1 - alpha) + ny1 * alpha
                sx2 = old_b.smoothed_rect[2] * (1 - alpha) + nx2 * alpha
                sy2 = old_b.smoothed_rect[3] * (1 - alpha) + ny2 * alpha
                # A motion-blurred pass often produces a plausible but incorrect
                # spelling. Retain the stable reading unless the replacement has
                # comparable confidence.
                stable_text = (old_b.text
                               if new_b.confidence + 8 < old_b.confidence
                               else new_b.text)
                merged = TrackedBlock(
                    rect=new_b.rect,
                    text=stable_text,
                    is_selected=old_b.is_selected,
                    confidence=max(new_b.confidence, old_b.confidence),
                    age=old_b.age + 1,
                    smoothed_rect=(sx1, sy1, sx2, sy2)
                )
                results.append(merged)

        for i, new_b in enumerate(new_blocks):
            if not matched_new[i]:
                new_b.age = 1
                new_b.smoothed_rect = new_b.rect
                results.append(new_b)

        for j, old_b in enumerate(old_blocks):
            if not matched_old[j] and old_b.age < BLOCK_LIFE_CYCLES:
                old_b.age += 1
                results.append(old_b)

        return results

    def _ocr_loop(self):
        tracked_blocks: List[TrackedBlock] = []

        while self.running:
            if self.is_paused:
                time.sleep(0.1)
                continue

            frame = self._best_frame_from_burst()
            if frame is None:
                time.sleep(0.1)
                continue

            roi_l, roi_t, roi_r, roi_b = self._scan_roi(frame)
            scan_img = frame[roi_t:roi_b, roi_l:roi_r]
            if scan_img is None or scan_img.size == 0:
                time.sleep(0.1)
                continue

            try:
                if self.prev_ocr_roi is not None:
                    dx, dy = self._estimate_motion(self.prev_ocr_roi, scan_img)
                    self._shift_tracked_blocks(tracked_blocks, dx, dy)
                self.prev_ocr_roi = scan_img.copy()

                ocr_region, doc_x, doc_y, document_found = (
                    self._isolate_document(scan_img))
                enlarged, ocr_scale = self._prepare_ocr_image(ocr_region)

                # One normal pass is both faster and less prone to merging
                # contradictory results than the previous six-pass approach.
                natural = self._preprocess_natural(enlarged)
                data = self._run_ocr_once(
                    natural, 6 if document_found else 11)
                if self._ocr_quality(data) < 75:
                    fallback = self._run_ocr_once(
                        self._preprocess_adaptive(enlarged), 11)
                    if self._ocr_quality(fallback) > self._ocr_quality(data):
                        data = fallback
                data = self._rescale_ocr_data(data, ocr_scale)

                effective_roi = (
                    roi_l + doc_x, roi_t + doc_y,
                    roi_l + doc_x + ocr_region.shape[1],
                    roi_t + doc_y + ocr_region.shape[0],
                )
                new_blocks = self._process_ocr_data(data, effective_roi)

                tracked_blocks = self._match_blocks(new_blocks, tracked_blocks)

                display_blocks = []
                for tb in tracked_blocks:
                    rect = tb.smoothed_rect if tb.smoothed_rect else tb.rect
                    display_blocks.append(OverlayBlock(
                        rect=rect,
                        text=tb.text,
                        is_selected=tb.is_selected
                    ))

                with self.ocr_lock:
                    self.latest_blocks = display_blocks

                self._refilter_text()

            except Exception as e:
                print(f"OCR error: {e}")

            time.sleep(OCR_INTERVAL)

    def _scan_roi(self, frame: np.ndarray) -> Tuple[int, int, int, int]:
        h, w = frame.shape[:2]
        s = self.scale
        ox = self.offset_x
        oy = self.offset_y
        left = int((self.scan_rect.left - ox) / s)
        top = int((self.scan_rect.top - oy) / s)
        right = int((self.scan_rect.right - ox) / s)
        bottom = int((self.scan_rect.bottom - oy) / s)
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))
        return left, top, right, bottom

    def _process_ocr_data(self, data: dict, roi: Tuple[int, int, int, int]) -> List[TrackedBlock]:
        blocks: List[TrackedBlock] = []
        n = len(data["text"])
        if n == 0:
            return blocks

        roi_l, roi_t, _, _ = roi
        min_confidence = 42

        for i in range(n):
            level = data["level"][i]
            text = data["text"][i].strip()
            conf = float(data["conf"][i])
            has_content = bool(re.search(r"[A-Za-z0-9]", text))
            letters = "".join(char for char in text if char.isalpha())
            likely_heading = (
                len(letters) >= 4 and letters.isupper() and conf >= 25)
            short_is_reliable = len(text) > 2 or conf >= 65
            confidence_is_reliable = conf >= min_confidence or likely_heading
            readable_ratio = sum(char.isalnum() for char in text) / max(
                1, len(text))
            if (level == 5 and has_content and short_is_reliable and
                    confidence_is_reliable and readable_ratio >= 0.55):
                x = data["left"][i] + roi_l
                y = data["top"][i] + roi_t
                w = data["width"][i]
                h = data["height"][i]
                if w >= 3 and h >= 3:
                    # Word boxes avoid highlighting the empty gaps that occur
                    # when an entire OCR line is represented by one rectangle.
                    pad_x = max(1, int(w * 0.015))
                    pad_y = max(1, int(h * 0.06))
                    blocks.append(TrackedBlock(
                        rect=(x - pad_x, y - pad_y,
                              x + w + pad_x, y + h + pad_y),
                        text=text,
                        is_selected=True,
                        confidence=conf,
                        age=0,
                        smoothed_rect=None
                    ))

        if not blocks:
            return blocks

        # Suppress contained duplicates occasionally produced by sparse-text OCR.
        filtered: List[TrackedBlock] = []
        for candidate in sorted(blocks, key=lambda block: block.confidence,
                                reverse=True):
            cx1, cy1, cx2, cy2 = candidate.rect
            duplicate = False
            for accepted in filtered:
                ax1, ay1, ax2, ay2 = accepted.rect
                intersection = max(0, min(cx2, ax2) - max(cx1, ax1)) * max(
                    0, min(cy2, ay2) - max(cy1, ay1))
                candidate_area = max(1, (cx2 - cx1) * (cy2 - cy1))
                if intersection / candidate_area > 0.75:
                    duplicate = True
                    break
            if not duplicate:
                filtered.append(candidate)

        blocks = filtered

        return blocks

    def _blocks_in_scan(self) -> List[OverlayBlock]:
        sr = self.scan_rect
        result = []
        with self.ocr_lock:
            for block in self.latest_blocks:
                l, t, r, b = block.rect
                canvas_l, canvas_t, canvas_r, canvas_b = self._img_to_canvas_rect(l, t, r, b)
                if self._rects_intersect(canvas_l, canvas_t, canvas_r, canvas_b, sr.left, sr.top, sr.right, sr.bottom):
                    result.append(block)
        return result

    def _refilter_text(self):
        blocks = self._blocks_in_scan()
        selected = [b for b in blocks if b.is_selected]
        raw_text = self._blocks_to_text(selected)
        final_text = self._reverse_sentences(raw_text) if self.is_reversed else raw_text
        self.all_text = final_text
        self._update_text_preview(final_text)

    # ── Text Utilities ────────────────────────────────────────────────

    def _group_blocks_into_lines(
            self, blocks: List[OverlayBlock]) -> List[List[OverlayBlock]]:
        sorted_init = sorted(blocks, key=lambda block: (
            (block.rect[1] + block.rect[3]) / 2, block.rect[0]))
        lines: List[List[OverlayBlock]] = []
        for block in sorted_init:
            block_height = max(1, block.rect[3] - block.rect[1])
            block_center = (block.rect[1] + block.rect[3]) / 2
            best_line = None
            best_distance = float("inf")
            for line in lines:
                centers = [(word.rect[1] + word.rect[3]) / 2 for word in line]
                heights = [word.rect[3] - word.rect[1] for word in line]
                distance = abs(block_center - sum(centers) / len(centers))
                tolerance = max(block_height, sum(heights) / len(heights)) * 0.6
                if distance <= tolerance and distance < best_distance:
                    best_line = line
                    best_distance = distance
            if best_line is None:
                lines.append([block])
            else:
                best_line.append(block)
        for line in lines:
            line.sort(key=lambda block: block.rect[0])
        lines.sort(key=lambda line: sum(
            (block.rect[1] + block.rect[3]) / 2 for block in line) / len(line))
        return lines

    def _blocks_to_text(self, blocks: List[OverlayBlock]) -> str:
        lines = self._group_blocks_into_lines(blocks)
        return "\n".join(" ".join(block.text for block in line)
                         for line in lines)

    def _sort_blocks(self, blocks: List[OverlayBlock]) -> List[OverlayBlock]:
        lines = self._group_blocks_into_lines(blocks)
        if self.is_reversed:
            lines.reverse()
        return [b for line in lines for b in line]

    def _reverse_sentences(self, text: str) -> str:
        if not text.strip():
            return text
        sentences = []
        current = []
        i = 0
        while i < len(text):
            current.append(text[i])
            if text[i] in ".!?":
                while i + 1 < len(text) and text[i + 1] in " \n\r.!?":
                    i += 1
                    current.append(text[i])
                sentences.append("".join(current).strip())
                current = []
            elif text[i] == "\n":
                trimmed = "".join(current).strip()
                if trimmed:
                    sentences.append(trimmed)
                current = []
            i += 1
        remaining = "".join(current).strip()
        if remaining:
            sentences.append(remaining)
        return "\n".join(s for s in reversed(sentences) if s)

    def _update_text_preview(self, text: str):
        def _update():
            self.text_preview.configure(state=tk.NORMAL)
            self.text_preview.delete("1.0", tk.END)
            self.text_preview.insert("1.0", text if text else "...")
            self.text_preview.configure(state=tk.DISABLED)

        self.root.after(0, _update)

    # ── Coordinate Transforms ─────────────────────────────────────────

    def _update_canvas_geometry(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            cw, ch = 480, 640
        self.canvas_w = cw
        self.canvas_h = ch

        fw = self.frame_w
        fh = self.frame_h
        if fw < 1 or fh < 1:
            fw, fh = 640, 480

        s = min(cw / fw, ch / fh)
        self.scale = s
        self.offset_x = (cw - fw * s) / 2.0
        self.offset_y = (ch - fh * s) / 2.0

    def _img_to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def _canvas_to_img(self, x: float, y: float) -> Tuple[float, float]:
        return (x - self.offset_x) / self.scale, (y - self.offset_y) / self.scale

    def _img_to_canvas_rect(self, l: float, t: float, r: float, b: float) -> Tuple[float, float, float, float]:
        x1, y1 = self._img_to_canvas(l, t)
        x2, y2 = self._img_to_canvas(r, b)
        return x1, y1, x2, y2

    def _rects_intersect(self, l1, t1, r1, b1, l2, t2, r2, b2) -> bool:
        return not (r1 < l2 or l1 > r2 or b1 < t2 or t1 > b2)

    # ── Display ───────────────────────────────────────────────────────

    def _update_display(self):
        if not self.running:
            return

        self._update_canvas_geometry()
        cw = self.canvas_w
        ch = self.canvas_h
        self.canvas.delete("all")

        with self.frame_lock:
            frame = self.latest_frame.copy() if self.latest_frame is not None else None

        if frame is not None:
            fh, fw = frame.shape[:2]
            disp_w = int(fw * self.scale)
            disp_h = int(fh * self.scale)
            resized = cv2.resize(frame, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)
            resized = self._apply_translucent_highlights(resized)
            resized_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(resized_rgb)
            self._tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self._tk_img)
            self._draw_overlays()
        else:
            err = self.camera_error
            if err:
                msg = err
            else:
                msg = "Starting camera..."
            self.canvas.create_text(cw / 2, ch / 2, text=msg, fill=TEXT_SECONDARY,
                                    font=("Segoe UI", 16), justify=tk.CENTER)

        self.root.after(30, self._update_display)

    def _apply_translucent_highlights(self, image: np.ndarray) -> np.ndarray:
        """Blend highlights into the preview so camera text remains readable."""
        overlay = image.copy()
        painted = False
        with self.ocr_lock:
            blocks = list(self.latest_blocks)
        for block in blocks:
            if not block.is_selected:
                continue
            x1, y1, x2, y2 = block.rect
            left = max(0, min(image.shape[1] - 1, int(x1 * self.scale)))
            top = max(0, min(image.shape[0] - 1, int(y1 * self.scale)))
            right = max(left + 1, min(image.shape[1], int(x2 * self.scale)))
            bottom = max(top + 1, min(image.shape[0], int(y2 * self.scale)))
            cv2.rectangle(overlay, (left, top), (right, bottom),
                          (153, 211, 52), thickness=-1)
            painted = True
        if not painted:
            return image
        return cv2.addWeighted(overlay, HIGHLIGHT_ALPHA,
                               image, 1.0 - HIGHLIGHT_ALPHA, 0)

    def _draw_overlays(self):
        cw = self.canvas_w
        ch = self.canvas_h
        sr = self.scan_rect

        # 1. Scrim outside scan area
        if sr.right > sr.left and sr.bottom > sr.top:
            self.canvas.create_rectangle(0, 0, cw, sr.top, fill=SCRIM_COLOR, outline="")
            self.canvas.create_rectangle(0, sr.bottom, cw, ch, fill=SCRIM_COLOR, outline="")
            self.canvas.create_rectangle(0, sr.top, sr.left, sr.bottom, fill=SCRIM_COLOR, outline="")
            self.canvas.create_rectangle(sr.right, sr.top, cw, sr.bottom, fill=SCRIM_COLOR, outline="")

            # 2. Scan area border
            self.canvas.create_rectangle(sr.left, sr.top, sr.right, sr.bottom,
                                         outline=SCAN_BORDER, width=2, tags="scan_border")

        # 3. Text blocks (only within scan area)
        with self.ocr_lock:
            blocks = list(self.latest_blocks)

        for block in blocks:
            l, t, r, b = self._img_to_canvas_rect(*block.rect)
            if self._rects_intersect(l, t, r, b, sr.left, sr.top, sr.right, sr.bottom):
                border = OVERLAY_BORDER if block.is_selected else OVERLAY_UNSELECTED_BORDER
                self.canvas.create_rectangle(l, t, r, b, fill="", outline=border, width=1,
                                             tags="text_block")

        if sr.right > sr.left and sr.bottom > sr.top:
            # 4. Corner brackets
            bs = CORNER_BRACKET_SIZE
            # Top-left
            self.canvas.create_line(sr.left, sr.top, sr.left + bs, sr.top, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            self.canvas.create_line(sr.left, sr.top, sr.left, sr.top + bs, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            # Top-right
            self.canvas.create_line(sr.right, sr.top, sr.right - bs, sr.top, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            self.canvas.create_line(sr.right, sr.top, sr.right, sr.top + bs, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            # Bottom-left
            self.canvas.create_line(sr.left, sr.bottom, sr.left + bs, sr.bottom, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            self.canvas.create_line(sr.left, sr.bottom, sr.left, sr.bottom - bs, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            # Bottom-right
            self.canvas.create_line(sr.right, sr.bottom, sr.right - bs, sr.bottom, fill=EMERALD_400, width=10, capstyle=tk.ROUND)
            self.canvas.create_line(sr.right, sr.bottom, sr.right, sr.bottom - bs, fill=EMERALD_400, width=10, capstyle=tk.ROUND)

            # 5. Corner handles
            for cx, cy in [(sr.left, sr.top), (sr.right, sr.top),
                           (sr.left, sr.bottom), (sr.right, sr.bottom)]:
                self.canvas.create_oval(cx - HANDLE_RADIUS, cy - HANDLE_RADIUS,
                                        cx + HANDLE_RADIUS, cy + HANDLE_RADIUS,
                                        fill=HANDLE_COLOR, outline=HANDLE_OUTLINE, width=3)

    # ── Mouse Handling ────────────────────────────────────────────────

    def _on_canvas_configure(self, event):
        self._update_canvas_geometry()
        cw = event.width
        ch = event.height
        if cw > 10 and ch > 10 and self.scan_rect.left == 0 and self.scan_rect.right == 0:
            margin = 8
            self.scan_rect.left = margin
            self.scan_rect.top = margin
            self.scan_rect.right = cw - margin
            self.scan_rect.bottom = ch - margin

    def _dist(self, x1, y1, x2, y2):
        return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

    def _on_mouse_down(self, event):
        tx, ty = event.x, event.y
        self.drag_start_x = tx
        self.drag_start_y = ty
        self.last_touch_x = tx
        self.last_touch_y = ty
        self.is_dragging = False
        sr = self.scan_rect

        if self._dist(tx, ty, sr.left, sr.top) < TOUCH_RADIUS:
            self.touch_mode = TouchMode.RESIZING_TOP_LEFT
        elif self._dist(tx, ty, sr.right, sr.top) < TOUCH_RADIUS:
            self.touch_mode = TouchMode.RESIZING_TOP_RIGHT
        elif self._dist(tx, ty, sr.left, sr.bottom) < TOUCH_RADIUS:
            self.touch_mode = TouchMode.RESIZING_BOTTOM_LEFT
        elif self._dist(tx, ty, sr.right, sr.bottom) < TOUCH_RADIUS:
            self.touch_mode = TouchMode.RESIZING_BOTTOM_RIGHT
        elif sr.left <= tx <= sr.right and sr.top <= ty <= sr.bottom:
            self.touch_mode = TouchMode.MOVING_RECT
        else:
            self.touch_mode = TouchMode.NONE

    def _on_mouse_move(self, event):
        tx, ty = event.x, event.y
        sr = self.scan_rect
        cw, ch = self.canvas_w, self.canvas_h

        if self.touch_mode == TouchMode.RESIZING_TOP_LEFT:
            sr.left = max(0, min(tx, sr.right - MIN_SCAN_SIZE))
            sr.top = max(0, min(ty, sr.bottom - MIN_SCAN_SIZE))
        elif self.touch_mode == TouchMode.RESIZING_TOP_RIGHT:
            sr.right = min(cw, max(tx, sr.left + MIN_SCAN_SIZE))
            sr.top = max(0, min(ty, sr.bottom - MIN_SCAN_SIZE))
        elif self.touch_mode == TouchMode.RESIZING_BOTTOM_LEFT:
            sr.left = max(0, min(tx, sr.right - MIN_SCAN_SIZE))
            sr.bottom = min(ch, max(ty, sr.top + MIN_SCAN_SIZE))
        elif self.touch_mode == TouchMode.RESIZING_BOTTOM_RIGHT:
            sr.right = min(cw, max(tx, sr.left + MIN_SCAN_SIZE))
            sr.bottom = min(ch, max(ty, sr.top + MIN_SCAN_SIZE))
        elif self.touch_mode == TouchMode.MOVING_RECT:
            dx = tx - self.last_touch_x
            dy = ty - self.last_touch_y
            if not self.is_dragging:
                if self._dist(tx, ty, self.drag_start_x, self.drag_start_y) > TOUCH_SLOP:
                    self.is_dragging = True
            if self.is_dragging:
                w = sr.right - sr.left
                h = sr.bottom - sr.top
                nl = sr.left + dx
                nt = sr.top + dy
                if nl < 0:
                    nl = 0
                if nt < 0:
                    nt = 0
                if nl + w > cw:
                    nl = cw - w
                if nt + h > ch:
                    nt = ch - h
                sr.left = nl
                sr.top = nt
                sr.right = nl + w
                sr.bottom = nt + h

        if self.touch_mode != TouchMode.NONE:
            self.last_touch_x = tx
            self.last_touch_y = ty
            self._refilter_text()

    def _on_mouse_up(self, event):
        tx, ty = event.x, event.y

        if self.touch_mode == TouchMode.MOVING_RECT and not self.is_dragging:
            # Click inside scan area -> toggle text block selection
            clicked = None
            with self.ocr_lock:
                for i, block in enumerate(self.latest_blocks):
                    l, t, r, b = self._img_to_canvas_rect(*block.rect)
                    if self._rects_intersect(l, t, r, b, self.scan_rect.left, self.scan_rect.top,
                                             self.scan_rect.right, self.scan_rect.bottom):
                        expanded = (l - 20, t - 20, r + 20, b + 20)
                        if expanded[0] <= tx <= expanded[2] and expanded[1] <= ty <= expanded[3]:
                            clicked = i
                            break
                if clicked is not None:
                    self.latest_blocks[clicked].is_selected = not self.latest_blocks[clicked].is_selected
                    self._refilter_text()

        self.touch_mode = TouchMode.NONE
        self.is_dragging = False

    # ── Copy ──────────────────────────────────────────────────────────

    def _copy_text(self):
        text = self.all_text
        if text.strip():
            pyperclip.copy(text)
            self._flash_animation()
        else:
            self._show_toast("No text detected")

    def _flash_animation(self):
        """Quick flash overlay to confirm copy"""
        self._show_toast("Text copied to clipboard!")

    def _show_toast(self, message: str):
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.configure(bg=DARK_BG)
        toast.attributes("-topmost", True)
        label = tk.Label(toast, text=message, fg=TEXT_COLOR, bg="#333333",
                         font=("Segoe UI", 12), padx=24, pady=12)
        label.pack()
        toast.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - toast.winfo_width() // 2
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - toast.winfo_height() // 2
        toast.geometry(f"+{x}+{y}")
        self.root.after(1500, toast.destroy)

    # ── Lifecycle ─────────────────────────────────────────────────────

    def _on_close(self):
        self.running = False
        self.root.destroy()


def check_dependencies():
    missing = []
    try:
        import cv2
    except ImportError:
        missing.append("opencv-python")
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    try:
        import pytesseract
    except ImportError:
        missing.append("pytesseract")
    try:
        import pyperclip
    except ImportError:
        missing.append("pyperclip")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    if missing:
        print("Missing dependencies. Install with:")
        print(f"  pip install {' '.join(missing)}")
        print()
        print("Also install Tesseract OCR:")
        print("  macOS: brew install tesseract")
        print("  Ubuntu: sudo apt install tesseract-ocr")
        print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

    # Check if tesseract binary is accessible
    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError:
        print("Tesseract OCR is not installed or not in PATH.")
        print()
        print("Install it:")
        print("  macOS: brew install tesseract")
        print("  Ubuntu: sudo apt install tesseract-ocr")
        print("  Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print()
        print("After installing, you may need to configure pytesseract:")
        print('  pytesseract.pytesseract.tesseract_cmd = r"/path/to/tesseract"')
        return False

    return True


def main():
    if not check_dependencies():
        input("\nPress Enter to exit...")
        sys.exit(1)

    root = tk.Tk()
    app = LiveTextScanner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
