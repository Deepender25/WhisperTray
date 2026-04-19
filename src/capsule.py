"""
capsule.py — Floating black capsule UI with animated voice wave.

Design goals
------------
* Frameless, translucent, always-on-top pill shape
* ~420 × 72 px — compact but readable
* 22 spring-physics bars that react to microphone amplitude
* Smooth fade-in slide-up entrance / fade-out exit
* Recording (pulsing red dot) → Processing (amber dot) states
* No text clutter — pure iconic minimal design
"""

import math
import time

import numpy as np
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPainterPath,
    QLinearGradient,
    QBrush,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import QApplication, QWidget

# ── constants ────────────────────────────────────────────────────────────────
W, H = 420, 72
RADIUS = 36            # capsule corner radius
NUM_BARS = 22
BAR_AREA_W = 250       # total width used by wave bars
BAR_W = 5              # individual bar width
BAR_MIN_H = 3          # minimum bar height (px)
BAR_MAX_H = 28         # maximum bar height when amplitude = 1
SPRING_K = 0.28        # spring constant (higher = snappier)
DAMPING = 0.55         # velocity damping (higher = less bouncy)
FRAME_MS = 14          # ~70 fps

# Colour palette
BG_ALPHA = 245
BG_DARK = QColor(10, 10, 10, BG_ALPHA)
BORDER_COLOR = QColor(255, 255, 255, 18)
BAR_ACTIVE = QColor(240, 240, 240, 255)
BAR_QUIET = QColor(55, 55, 55, 200)
DOT_REC = QColor(239, 68, 68)
DOT_PROC = QColor(245, 158, 11)
DOT_DONE = QColor(34, 197, 94)
DOT_LLM = QColor(59, 130, 246)

# Slide-in / fade animation
ANIM_STEPS = 20        # frames for entrance / exit
ANIM_INTERVAL_MS = 12


class CapsuleWidget(QWidget):
    """The floating voice-input capsule."""

    closed = pyqtSignal()  # user dismissed (Escape / click × )

    # ── lifecycle ─────────────────────────────────────────────────────────

    def __init__(self) -> None:
        super().__init__(None)
        self._setup_window()
        self._init_state()
        self._position_on_screen()

        # Main animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(FRAME_MS)

        # Entrance animation
        self._anim_step = 0
        self._anim_direction = 1   # 1 = fade in, -1 = fade out
        self._closing = False
        self._entrance_timer = QTimer(self)
        self._entrance_timer.timeout.connect(self._anim_tick)
        self.setWindowOpacity(0.0)
        self._entrance_timer.start(ANIM_INTERVAL_MS)

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool                   # no taskbar entry
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # don't steal focus
        self.setFixedSize(W, H)

    def _init_state(self) -> None:
        self.amplitudes = np.zeros(NUM_BARS, dtype=float)
        self.velocities = np.zeros(NUM_BARS, dtype=float)
        self.targets = np.zeros(NUM_BARS, dtype=float)
        self.is_recording = True
        self.is_processing = False
        self.is_refining = False
        self._phase = 0.0    # general phase clock for pulsing effects

    def _position_on_screen(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - W) // 2
        y = screen.y() + screen.height() - H - 50   # 50 px above taskbar
        self._base_y = y
        self.move(x, y + 18)   # start slightly below for slide effect

    # ── public API ────────────────────────────────────────────────────────

    def update_amplitude(self, rms: float) -> None:
        """Called (via signal) from recorder thread with normalised RMS."""
        center = NUM_BARS / 2.0
        for i in range(NUM_BARS):
            dist = abs(i - center) / center          # 0 at centre, 1 at edge
            envelope = max(0.0, 1.0 - dist * 0.35)
            noise = np.random.random() * 0.28 * rms
            self.targets[i] = min(1.0, rms * envelope + noise)

    def set_processing(self) -> None:
        """Switch to the 'transcribing' visual state."""
        self.is_recording = False
        self.is_processing = True
        self.is_refining = False
        self.targets[:] = 0.25

    def set_refining(self) -> None:
        """Switch to the 'LLM refining' visual state."""
        self.is_recording = False
        self.is_processing = False
        self.is_refining = True
        self.targets[:] = 0.15

    def close_animated(self) -> None:
        """Trigger fade-out, then emit closed and hide."""
        if self._closing:
            return
        self._closing = True
        self._anim_direction = -1
        self._entrance_timer.start(ANIM_INTERVAL_MS)

    # ── animation ticks ───────────────────────────────────────────────────

    def _anim_tick(self) -> None:
        """Handles entrance (fade in + slide up) and exit animations."""
        self._anim_step += self._anim_direction
        progress = max(0.0, min(1.0, self._anim_step / ANIM_STEPS))

        # Ease-out cubic
        t = 1.0 - (1.0 - progress) ** 3
        self.setWindowOpacity(t)

        # Slide: move from base_y+18 → base_y
        offset = int((1.0 - t) * 18)
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - W) // 2
        self.move(x, self._base_y + offset)

        if progress >= 1.0 and self._anim_direction == 1:
            self._entrance_timer.stop()

        if progress <= 0.0 and self._anim_direction == -1:
            self._entrance_timer.stop()
            self.hide()
            self.closed.emit()

    def _tick(self) -> None:
        """Main physics + render tick at ~70 fps."""
        self._phase += 0.07

        # Idle breathing when quiet
        if not self.is_recording or self.targets.max() < 0.04:
            center = NUM_BARS / 2.0
            for i in range(NUM_BARS):
                dist = abs(i - center) / center
                envelope = max(0.0, 1.0 - dist * 0.65)
                idle = 0.06 * envelope * (
                    0.5 + 0.5 * math.sin(self._phase * 0.55 + i * 0.22)
                )
                if self.is_processing:
                    proc = 0.2 * envelope * (
                        0.5 + 0.5 * math.sin(self._phase * 1.2 + i * 0.35)
                    )
                    self.targets[i] = proc
                elif self.is_refining:
                    ref = 0.15 * envelope * (
                        0.5 + 0.5 * math.sin(self._phase * 0.8 + i * 0.5)
                    )
                    self.targets[i] = ref
                else:
                    self.targets[i] = idle

        # Spring physics per bar
        for i in range(NUM_BARS):
            force = (self.targets[i] - self.amplitudes[i]) * SPRING_K
            self.velocities[i] = self.velocities[i] * DAMPING + force
            self.amplitudes[i] = max(0.0, min(1.0, self.amplitudes[i] + self.velocities[i]))

        self.update()   # schedule repaint

    # ── painting ──────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        self._draw_capsule(painter)
        self._draw_wave(painter)
        self._draw_indicator(painter)

        painter.end()

    def _draw_capsule(self, p: QPainter) -> None:
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, W - 1, H - 1), RADIUS, RADIUS)

        # Background fill
        p.fillPath(path, BG_DARK)

        # Subtle border
        pen = QPen(BORDER_COLOR)
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.drawPath(path)

    def _draw_wave(self, p: QPainter) -> None:
        spacing = BAR_AREA_W / NUM_BARS
        start_x = (W - BAR_AREA_W) / 2.0
        cy = H / 2.0

        p.setPen(Qt.NoPen)

        for i in range(NUM_BARS):
            amp = float(self.amplitudes[i])
            center_factor = 1.0 - (abs(i - NUM_BARS / 2.0) / (NUM_BARS / 2.0)) * 0.2
            bar_h = max(float(BAR_MIN_H), amp * BAR_MAX_H * center_factor + BAR_MIN_H)

            x = start_x + i * spacing + spacing / 2.0

            if self.is_processing:
                phase = (self._phase * 0.9 + i * 0.28) % (2 * math.pi)
                brightness = int(80 + 70 * math.sin(phase))
                color = QColor(brightness, int(brightness * 0.75), 20, 200)
            elif self.is_refining:
                phase = (self._phase * 0.7 + i * 0.4) % (2 * math.pi)
                brightness = int(100 + 50 * math.sin(phase))
                color = QColor(20, brightness, 240, 200)
            elif self.is_recording and amp > 0.05:
                brightness = int(150 + 90 * amp)
                color = QColor(brightness, brightness, brightness, 255)
            else:
                color = BAR_QUIET

            p.setBrush(color)
            # Rounded-cap bars via drawRoundedRect
            bw = float(BAR_W)
            p.drawRoundedRect(
                QRectF(x - bw / 2, cy - bar_h / 2, bw, bar_h),
                bw / 2,
                bw / 2,
            )

    def _draw_indicator(self, p: QPainter) -> None:
        """Pulsing status dot on the left side."""
        cx, cy = 28, H / 2

        if self.is_processing:
            pulse = 0.5 + 0.5 * math.sin(self._phase * 1.5)
            alpha = int(150 + 105 * pulse)
            color = QColor(DOT_PROC.red(), DOT_PROC.green(), DOT_PROC.blue(), alpha)
            r = 4.5
        elif self.is_refining:
            pulse = 0.5 + 0.5 * math.sin(self._phase * 1.8)
            alpha = int(150 + 105 * pulse)
            color = QColor(DOT_LLM.red(), DOT_LLM.green(), DOT_LLM.blue(), alpha)
            r = 4.5
        elif self.is_recording:
            pulse = 0.5 + 0.5 * math.sin(self._phase * 2.2)
            alpha = int(160 + 95 * pulse)
            color = QColor(DOT_REC.red(), DOT_REC.green(), DOT_REC.blue(), alpha)
            r = 5.0
        else:
            color = QColor(80, 80, 80, 160)
            r = 4.0

        # Soft glow behind dot
        grad = QRadialGradient(QPointF(cx, cy), r * 2.8)
        glow = QColor(color)
        glow.setAlpha(30)
        grad.setColorAt(0.0, glow)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), r * 2.8, r * 2.8)

        # Solid dot
        p.setBrush(color)
        p.drawEllipse(QPointF(cx, cy), r, r)

    # ── keyboard / mouse events ───────────────────────────────────────────

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close_animated()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_start"):
            self.move(event.globalPos() - self._drag_start)
