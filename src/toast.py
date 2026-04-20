"""
toast.py — A frameless, animated pop-up notification for user errors.
"""

import math
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPainterPath,
    QPen,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QBrush
)
from PyQt5.QtWidgets import QApplication, QWidget

class ToastWidget(QWidget):
    """A sleek floating warning toast notification."""

    def __init__(self, message: str, duration_ms: int = 2500):
        super().__init__(None)
        self.message = message
        self.duration_ms = duration_ms

        self._setup_window()

        self._anim_step = 0
        self._anim_direction = 1   # 1 = slide in, -1 = slide out
        self._closing = False
        self._hovered = False

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_tick)
        
        self.setWindowOpacity(0.0)
        self._anim_timer.start(10)  # Render very frequently (~100 FPS)

        # Auto-close timer
        self._life_timer = QTimer(self)
        self._life_timer.setSingleShot(True)
        self._life_timer.timeout.connect(self.close_animated)
        self._life_timer.start(self.duration_ms)

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # Calculate width based on text
        font = QFont("Segoe UI Variable Display", 11, QFont.Medium)
        if not font.exactMatch():
            font = QFont("Segoe UI", 11, QFont.Medium)
        self.setFont(font)
        
        fm = QFontMetrics(font)
        text_width = fm.width(self.message)
        
        self.w = text_width + 80
        self.h = 48
        self.setFixedSize(self.w, self.h)
        
        # Pre-generate high quality noise texture for Frosted Glass effect
        import numpy as np
        arr = np.zeros((self.h, self.w, 4), dtype=np.uint8)
        arr[..., 0:3] = 255  # White noise
        arr[..., 3] = np.random.randint(0, 35, (self.h, self.w), dtype=np.uint8)
        from PyQt5.QtGui import QImage, QPixmap
        img = QImage(arr.data, self.w, self.h, self.w * 4, QImage.Format_ARGB32).copy()
        self._noise_pixmap = QPixmap.fromImage(img)
        
        self._position_on_screen()

    def _position_on_screen(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.w) // 2
        # Position slightly near the top
        y = screen.y() + 80
        self._base_y = y
        self.move(x, y - 24)  # Start slightly above for drop-in effect

    def close_animated(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._anim_direction = -1
        self._anim_timer.start(16)

    def _anim_tick(self) -> None:
        self._anim_step += self._anim_direction
        anim_duration = 12.0  # Much FASTER, 12 frames instead of 20
        
        progress = max(0.0, min(1.0, self._anim_step / anim_duration))

        # Springy ease-out cubic
        if self._anim_direction == 1:
            # Snappy slide down with minor bounce
            t = progress - 1
            eased = (t * t * ((2.0 + 1) * t + 2.0) + 1)
            opacity = min(1.0, progress * 2.0) # rapidly hit full opacity
        else:
            # Snappy ease in out slide up
            t = progress
            eased = t * t * (3 - 2 * t)
            opacity = progress

        self.setWindowOpacity(opacity)

        offset = int((1.0 - eased) * (-24))
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.w) // 2
        self.move(x, self._base_y + offset)

        if progress >= 1.0 and self._anim_direction == 1:
            self._anim_timer.stop()

        if progress <= 0.0 and self._anim_direction == -1:
            self._anim_timer.stop()
            self.hide()
            self.deleteLater()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        
        # perfectly anti-aliased rendering
        p.setRenderHint(QPainter.Antialiasing)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.w - 1, self.h - 1), 12, 12)

        # 1. Premium Clear Glass gradient (translucent clear with slight reddish highlight)
        bg_grad = QLinearGradient(0, 0, 0, self.h)
        bg_grad.setColorAt(0.0, QColor(244, 63, 94, 30))
        bg_grad.setColorAt(0.5, QColor(244, 63, 94, 15))
        bg_grad.setColorAt(1.0, QColor(244, 63, 94, 5))
        p.fillPath(path, bg_grad)
        
        # 2. Textured Glass effect (Frosted Noise)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(0, 0, self._noise_pixmap)
        p.restore()

        # 3. Inner reflection for 3D depth of Liquid Glass
        inner_path = QPainterPath()
        inner_path.addRoundedRect(QRectF(1.5, 1.5, self.w - 3, self.h - 3), 11, 11)
        p.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        p.drawPath(inner_path)

        # 4. Warning Glass Rim border
        border_grad = QLinearGradient(0, 0, 0, self.h)
        border_grad.setColorAt(0.0, QColor(244, 63, 94, 250)) # Rose 500
        border_grad.setColorAt(1.0, QColor(244, 63, 94, 70))
        
        pen = QPen(QBrush(border_grad), 1.5)
        p.setPen(pen)
        p.drawPath(path)

        # Warning Icon (simple circle with exclamation)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(239, 68, 68, 255))
        icon_cx, icon_cy = 24, self.h / 2
        p.drawEllipse(QPointF(icon_cx, icon_cy), 8, 8)
        
        p.setPen(QPen(QColor(255, 255, 255), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(int(icon_cx), int(icon_cy - 3), int(icon_cx), int(icon_cy + 1))
        p.drawPoint(int(icon_cx), int(icon_cy + 4))

        # Text
        p.setPen(QColor(245, 245, 245))
        p.drawText(QRectF(44, 0, self.w - 50, self.h), Qt.AlignVCenter | Qt.AlignLeft, self.message)

        p.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.close_animated()
