import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QSlider, QPushButton,
    QVBoxLayout, QHBoxLayout, QMessageBox, QGraphicsDropShadowEffect,
    QFrame, QButtonGroup
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QFont

# Directory of this script — used so the app works no matter where it is
# launched from (e.g. a pinned .desktop shortcut, not just the project folder).
APP_DIR = os.path.dirname(os.path.abspath(__file__))

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
"""


class BatteryChargeThresholdApp(QWidget):
    PRESETS = [60, 80, 100]

    def __init__(self):
        super().__init__()

        # Frameless, translucent so we can draw a rounded card.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 380)
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

        # Initialise from the system's current threshold.
        current = self.get_current_threshold()
        if current:
            self.slider.setValue(current)
        self.on_slider_change(self.slider.value())

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
                QMessageBox.critical(self, "Error", "Please run as root")
            elif e.returncode == 2:
                QMessageBox.critical(self, "Error", "Invalid input: threshold must be between 20 and 100")
            elif e.returncode == 3:
                QMessageBox.critical(self, "Error", "Device not compatible\ncharge_control_end_threshold file not found")
            elif e.returncode == 126:
                # pkexec dismissed / authorisation declined — stay silent.
                return
            else:
                QMessageBox.critical(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        else:
            self.status_label.setText(f"Current charge: limit set to {new_threshold}%")
            QMessageBox.information(
                self,
                "Success",
                f"Battery charge threshold set to {new_threshold}%.\n\n"
                "Changes persist across reboots.",
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Sans Serif", 10))

    window = BatteryChargeThresholdApp()
    window.show()

    sys.exit(app.exec_())
