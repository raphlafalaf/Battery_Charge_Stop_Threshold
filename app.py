import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QSlider, QPushButton,
    QVBoxLayout, QHBoxLayout, QDialog, QGraphicsDropShadowEffect,
    QFrame, QButtonGroup, QSystemTrayIcon, QMenu
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QPen

# Directory of this script — used so the app works no matter where it is
# launched from (e.g. a pinned .desktop shortcut, not just the project folder).
APP_DIR = os.path.dirname(os.path.abspath(__file__))

ACCENT = "#6c7ae0"
SUCCESS = "#3ad29f"
DANGER = "#ff6b6b"

STYLE = """
#card {
    background-color: #1e1f29;
    border-radius: 18px;
}
#title {
    color: #f2f3f7;
    font-size: 16px;
    font-weight: 600;
}
#subtitle {
    color: #8b8d98;
    font-size: 12px;
}
#value {
    color: #ffffff;
    font-size: 56px;
    font-weight: 700;
}
#percent {
    color: #6c7ae0;
    font-size: 22px;
    font-weight: 600;
}
#status {
    color: #8b8d98;
    font-size: 12px;
}
QSlider::groove:horizontal {
    height: 6px;
    border-radius: 3px;
    background: #33343f;
}
QSlider::sub-page:horizontal {
    height: 6px;
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #6c7ae0, stop:1 #8e9bff);
}
QSlider::handle:horizontal {
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    background: #ffffff;
}
QSlider::handle:horizontal:hover {
    background: #e8eaff;
}
QPushButton#preset {
    background-color: #2a2b38;
    color: #c5c7d4;
    border: none;
    border-radius: 9px;
    padding: 8px 0;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#preset:hover {
    background-color: #34354a;
}
QPushButton#preset:checked {
    background-color: #6c7ae0;
    color: #ffffff;
}
QPushButton#apply {
    background-color: #6c7ae0;
    color: #ffffff;
    border: none;
    border-radius: 11px;
    padding: 12px 0;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#apply:hover {
    background-color: #7d8af0;
}
QPushButton#apply:pressed {
    background-color: #5b68cf;
}
QPushButton#close {
    background-color: transparent;
    color: #8b8d98;
    border: none;
    font-size: 18px;
    font-weight: 700;
}
QPushButton#close:hover {
    color: #ff6b6b;
}
#dlgTitle {
    color: #f2f3f7;
    font-size: 16px;
    font-weight: 700;
}
#dlgText {
    color: #b6b8c4;
    font-size: 13px;
}
QPushButton#dlgOk {
    background-color: #6c7ae0;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 0;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#dlgOk:hover {
    background-color: #7d8af0;
}
QMenu {
    background-color: #1e1f29;
    color: #e6e7ee;
    border: 1px solid #33343f;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 6px 22px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #6c7ae0;
}
QMenu::separator {
    height: 1px;
    background: #33343f;
    margin: 4px 8px;
}
"""


def make_battery_icon(level=80, size=64):
    """Draw a battery glyph filled to `level`%, returned as a QIcon.

    Generated at runtime so the app ships no image assets and the tray
    icon can reflect the currently selected threshold.
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    bw, bh = size * 0.62, size * 0.34
    x = (size - bw) / 2 - size * 0.04
    y = (size - bh) / 2
    body = QRectF(x, y, bw, bh)

    pen = QPen(QColor("#f2f3f7"))
    pen.setWidthF(size * 0.05)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    radius = size * 0.06
    p.drawRoundedRect(body, radius, radius)

    # Positive terminal nub on the right.
    tw, th = size * 0.05, bh * 0.42
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#f2f3f7"))
    p.drawRoundedRect(QRectF(x + bw + size * 0.012, y + (bh - th) / 2, tw, th), tw / 2, tw / 2)

    # Charge fill.
    pad = size * 0.05
    fill_w = (bw - 2 * pad) * max(level, 0) / 100.0
    color = QColor(SUCCESS) if level >= 95 else QColor(ACCENT)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(x + pad, y + pad, max(fill_w, 1.0), bh - 2 * pad),
                      radius * 0.5, radius * 0.5)
    p.end()
    return QIcon(pix)


class StyledMessage(QDialog):
    """Frameless dark-card confirmation dialog matching the main window."""

    def __init__(self, parent, title, text, accent=ACCENT, glyph="✓"):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(320, 240)

        card = QFrame(self)
        card.setObjectName("card")
        card.setGeometry(10, 10, 300, 220)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(36)
        shadow.setColor(QColor(0, 0, 0, 170))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        badge = QLabel(glyph)
        badge.setFixedSize(52, 52)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{accent}; border-radius:26px; color:#ffffff;"
            "font-size:26px; font-weight:700;"
        )

        title_label = QLabel(title)
        title_label.setObjectName("dlgTitle")
        title_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel(text)
        text_label.setObjectName("dlgText")
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(True)

        ok = QPushButton("Got it")
        ok.setObjectName("dlgOk")
        ok.setCursor(Qt.PointingHandCursor)
        ok.setFixedWidth(120)
        ok.clicked.connect(self.accept)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        layout.addWidget(badge, alignment=Qt.AlignCenter)
        layout.addWidget(title_label)
        layout.addWidget(text_label)
        layout.addStretch()
        layout.addWidget(ok, alignment=Qt.AlignCenter)

    def showEvent(self, event):
        # Center over the parent window.
        if self.parent():
            pg = self.parent().frameGeometry()
            self.move(pg.center().x() - self.width() // 2,
                      pg.center().y() - self.height() // 2)
        super().showEvent(event)

    @staticmethod
    def success(parent, title, text):
        StyledMessage(parent, title, text, accent=SUCCESS, glyph="✓").exec_()

    @staticmethod
    def error(parent, title, text):
        StyledMessage(parent, title, text, accent=DANGER, glyph="✕").exec_()


class BatteryChargeThresholdApp(QWidget):
    PRESETS = [60, 80, 100]

    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 380)
        self.setWindowIcon(make_battery_icon(80))
        self._drag_pos = None

        # ---- Card container ----
        card = QFrame(self)
        card.setObjectName("card")
        card.setGeometry(10, 10, 340, 360)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)

        # ---- Header ----
        title = QLabel("Battery Charge Limit")
        title.setObjectName("title")
        subtitle = QLabel("Protects long-term battery health")
        subtitle.setObjectName("subtitle")

        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        close_btn = QPushButton("×")
        close_btn.setObjectName("close")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)

        header = QHBoxLayout()
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(close_btn, alignment=Qt.AlignTop)

        # ---- Big value display ----
        self.value_label = QLabel("80")
        self.value_label.setObjectName("value")
        percent_label = QLabel("%")
        percent_label.setObjectName("percent")

        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        value_row.addStretch()
        value_row.addWidget(self.value_label, alignment=Qt.AlignBottom)
        value_row.addWidget(percent_label, alignment=Qt.AlignBottom)
        value_row.addStretch()

        # ---- Slider ----
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(20, 100)
        self.slider.setValue(80)
        self.slider.valueChanged.connect(self.on_slider_change)
        self.slider.setCursor(Qt.PointingHandCursor)

        # ---- Presets ----
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        self.preset_group = QButtonGroup(self)
        self.preset_group.setExclusive(True)
        for val in self.PRESETS:
            btn = QPushButton(f"{val}%")
            btn.setObjectName("preset")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, v=val: self.slider.setValue(v))
            self.preset_group.addButton(btn, val)
            preset_row.addWidget(btn)

        # ---- Apply ----
        self.apply_btn = QPushButton("Apply Threshold")
        self.apply_btn.setObjectName("apply")
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.clicked.connect(self.set_threshold)

        # ---- Status footer ----
        self.status_label = QLabel(self.battery_status_text())
        self.status_label.setObjectName("status")
        self.status_label.setAlignment(Qt.AlignCenter)

        # ---- Assemble ----
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addLayout(value_row)
        layout.addWidget(self.slider)
        layout.addLayout(preset_row)
        layout.addStretch()
        layout.addWidget(self.apply_btn)
        layout.addWidget(self.status_label)

        self._init_tray()

        # Initialise from the system's current threshold.
        current = self.get_current_threshold()
        if current:
            self.slider.setValue(current)
        self.on_slider_change(self.slider.value())

    # ---------- Tray ----------
    def _init_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(make_battery_icon(self.slider.value()), self)
        self.tray.setToolTip("Battery Charge Limit")

        menu = QMenu()
        menu.addAction("Show window", self.show_and_raise)
        menu.addSeparator()
        for val in self.PRESETS:
            menu.addAction(f"Set limit to {val}%", lambda _=False, v=val: self._apply_from_tray(v))
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_raise()

    def _apply_from_tray(self, value):
        self.slider.setValue(value)
        self.set_threshold()

    def show_and_raise(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------- UI helpers ----------
    def on_slider_change(self, value):
        self.value_label.setText(str(value))
        btn = self.preset_group.button(value)
        if btn:
            btn.setChecked(True)
        elif self.preset_group.checkedButton():
            self.preset_group.setExclusive(False)
            self.preset_group.checkedButton().setChecked(False)
            self.preset_group.setExclusive(True)

        icon = make_battery_icon(value)
        self.setWindowIcon(icon)
        if self.tray:
            self.tray.setIcon(icon)
            self.tray.setToolTip(f"Battery charge limit: {value}%")

    def battery_status_text(self):
        capacity = self.read_battery_file("capacity")
        if capacity is not None:
            return f"Current charge: {capacity}%"
        return "Battery status unavailable"

    # ---------- Frameless window dragging ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.set_threshold()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # With a tray icon, closing hides to the tray instead of quitting so
        # the indicator stays available. Without one, closing quits.
        if self.tray:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Battery Charge Limit",
                "Still running in the tray — click the icon to reopen.",
                make_battery_icon(self.slider.value()), 3000,
            )
        else:
            QApplication.quit()

    # ---------- System interaction ----------
    def battery_name(self):
        base = "/sys/class/power_supply"
        for name in sorted(os.listdir(base)):
            if name.startswith("BAT"):
                return name
        return None

    def read_battery_file(self, filename):
        try:
            name = self.battery_name()
            if not name:
                return None
            with open(f"/sys/class/power_supply/{name}/{filename}", "r") as f:
                return int(f.read().strip())
        except Exception:
            return None

    def get_current_threshold(self):
        return self.read_battery_file("charge_control_end_threshold")

    def set_threshold(self):
        new_threshold = self.slider.value()
        try:
            script_path = os.path.join(APP_DIR, "modify_threshold.sh")

            if not os.path.isfile(script_path) or not os.access(script_path, os.X_OK):
                raise Exception("Shell script not found or not executable")

            subprocess.run(
                ["pkexec", "bash", script_path, str(new_threshold)],
                check=True,
            )

        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                StyledMessage.error(self, "Error", "Please run as root.")
            elif e.returncode == 2:
                StyledMessage.error(self, "Error", "Threshold must be between 20 and 100.")
            elif e.returncode == 3:
                StyledMessage.error(self, "Device not compatible",
                                    "charge_control_end_threshold file not found.")
            elif e.returncode == 126:
                # pkexec dismissed / authorisation declined — stay silent.
                return
            else:
                StyledMessage.error(self, "Error", str(e))
        except Exception as e:
            StyledMessage.error(self, "Error", str(e))
        else:
            self.status_label.setText(f"Charge limit set to {new_threshold}%")
            StyledMessage.success(
                self,
                "Threshold Updated",
                f"Battery charge limit is now {new_threshold}%. "
                "This setting persists across reboots.",
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Sans Serif", 10))
    app.setWindowIcon(make_battery_icon(80))

    window = BatteryChargeThresholdApp()
    # Keep running in the tray (if present) after the window is closed.
    app.setQuitOnLastWindowClosed(window.tray is None)
    window.show()

    sys.exit(app.exec_())
