"""Project version, repository and retained license."""

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from aim_tool import __version__


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 Auto Image Mark Tool")
        self.resize(470, 260)
        layout = QVBoxLayout(self)
        heading = QLabel("Auto Image Mark Tool")
        heading.setObjectName("title")
        layout.addWidget(heading)
        layout.addWidget(QLabel(f"版本 {__version__} · ©BG2FOU"))
        information = QLabel(
            'JPG 坐标与版权水印；NEF 仅坐标<br><br><a href="https://github.com/BG2FOU/Auto-Image-Mark-Tool">项目仓库与更新</a><br><a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a><br><br>字体、签名与照片由用户在本机提供。'
        )
        information.setWordWrap(True)
        information.setOpenExternalLinks(True)
        layout.addWidget(information)
        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
