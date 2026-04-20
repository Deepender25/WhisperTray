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
    QFontMetrics
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
        self._anim_timer.start(16)  # ~60 FPS

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
        anim_duration = 20.0
        
        progress = max(0.0, min(1.0, self._anim_step / anim_duration))

        # Ease-out back cubic
        if self._anim_direction == 1:
            # Drop in with slight bounce
            t = progress - 1
            eased = (t * t * ((1.70158 + 1) * t + 1.70158) + 1)
            opacity = min(1.0, progress * 1.5)
        else:
            # Ease in out slide up
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
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.w - 1, self.h - 1), 12, 12)

        # Premium translucent dark background
        bg_color = QColor(20, 20, 20, 240)
        p.fillPath(path, bg_color)

        # Amber / Reddish warning border
        pen = QPen(QColor(239, 68, 68, 180)) # Reddish border
        pen.setWidthF(1.2)
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
