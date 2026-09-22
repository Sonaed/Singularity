#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Singularity V2
Convertisseur d'images simple et léger pour portfolio / site web.

Dépendances :
    python -m pip install PySide6 Pillow

Fonctionnement :
- Ajout de fichiers ou d'un dossier
- Drag & drop depuis Dolphin
- Sortie WebP
- Maximum 2560 x 1440 px
- 72 DPI
- RGB / RGBA si transparence
- Qualité 80 %
- Suppression des métadonnées inutiles
- Les originaux ne sont jamais modifiés
- Les fichiers sont placés dans un dossier "Singularity"
"""

import sys
from math import cos, sin
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from PIL import Image, ImageOps


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp",
    ".bmp", ".tif", ".tiff"
}

MAX_WIDTH = 2560
MAX_HEIGHT = 1440
DEFAULT_QUALITY = 80
DPI = 72


def format_size(size):
    units = ("B", "KB", "MB", "GB")
    value = float(size)

    for unit in units:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{value:.1f} TB"


def prepare_image(image):
    """
    Corrige l'orientation EXIF et prépare l'image.
    RGB si aucune transparence.
    RGBA si transparence.
    """

    image = ImageOps.exif_transpose(image)

    has_alpha = (
        image.mode in ("RGBA", "LA")
        or (
            image.mode == "P"
            and "transparency" in image.info
        )
    )

    if has_alpha:
        return image.convert("RGBA")

    return image.convert("RGB")


def resize_image(image):
    """
    Redimensionne uniquement si l'image dépasse
    2560x1440, sans jamais déformer l'image.
    """

    width, height = image.size

    if width <= MAX_WIDTH and height <= MAX_HEIGHT:
        return image

    ratio = min(
        MAX_WIDTH / width,
        MAX_HEIGHT / height
    )

    new_width = max(1, round(width * ratio))
    new_height = max(1, round(height * ratio))

    return image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )


def collect_images(folder):
    """Retourne les images directement présentes dans un dossier."""

    if not folder.is_dir():
        return []

    return sorted(
        [
            path for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ],
        key=lambda p: p.name.lower()
    )


class ConverterWorker(QThread):

    progress = Signal(int)
    status = Signal(str)
    finished_conversion = Signal(
        int, int, int, int, str
    )

    def __init__(self, files, output_dir, quality):
        super().__init__()

        self.files = files
        self.output_dir = output_dir
        self.quality = quality

    def run(self):

        success = 0
        errors = 0

        total_before = 0
        total_after = 0

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        total = len(self.files)

        for index, source in enumerate(self.files):

            try:
                self.status.emit(
                    f"Conversion de {source.name}..."
                )

                before = source.stat().st_size

                with Image.open(source) as original:

                    image = prepare_image(original)
                    image = resize_image(image)

                    destination = (
                        self.output_dir
                        / f"{source.stem}.webp"
                    )

                    # WebP :
                    # - beaucoup plus compact que PNG
                    # - souvent plus compact que JPEG
                    # - conserve la transparence
                    #
                    # On ne transmet volontairement
                    # pas les métadonnées EXIF.
                    image.save(
                        destination,
                        "WEBP",
                        quality=self.quality,
                        method=6,
                        lossless=False,
                    )

                after = destination.stat().st_size

                total_before += before
                total_after += after

                success += 1

            except Exception as error:

                errors += 1

                self.status.emit(
                    f"Erreur : {source.name} — {error}"
                )

            percentage = int(
                ((index + 1) / total) * 100
            )

            self.progress.emit(percentage)

        self.finished_conversion.emit(
            success,
            errors,
            total_before,
            total_after,
            str(self.output_dir)
        )


class DropListWidget(QListWidget):

    paths_dropped = Signal(list)

    def __init__(self):
        super().__init__()

        self.setAcceptDrops(True)
        self.setSpacing(4)
        self.phase = 0.0
        self.animation = QTimer(self)
        self.animation.setInterval(35)
        self.animation.timeout.connect(self.advance_singularity)
        self.animation.start()

    def advance_singularity(self):
        """Animation lente : une présence, pas une distraction."""

        self.phase = (self.phase + 0.018) % 1.0
        if not self.count():
            self.viewport().update()

    def paintEvent(self, event):
        """Affiche une invitation claire tant que le sas de dépôt est vide."""

        super().paintEvent(event)

        if self.count():
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.viewport().rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) * 0.18

        # Le noyau est noir : la lumière autour est seule déformée.
        for index, scale in enumerate((1.55, 1.28, 1.04)):
            painter.setPen(QPen(QColor(132, 110, 255, 22 + index * 28), 1.2))
            painter.save()
            painter.translate(center)
            painter.rotate(self.phase * 360 * (1 if index % 2 else -1) + index * 37)
            painter.drawEllipse(
                int(-radius * scale), int(-radius * scale * 0.28),
                int(radius * scale * 2), int(radius * scale * 0.56),
            )
            painter.restore()

        for index in range(8):
            angle = self.phase * 6.28 + index * 0.785
            distance = radius * (1.06 + (index % 3) * 0.22)
            x = center.x() + cos(angle) * distance
            y = center.y() + sin(angle) * distance * 0.29
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(175, 229, 255, 110 + (index % 2) * 70))
            painter.drawEllipse(int(x - 1.5), int(y - 1.5), 3, 3)

        painter.setPen(QPen(QColor("#8069dc"), 1))
        painter.setBrush(QColor("#02030b"))
        painter.drawEllipse(
            int(center.x() - radius * 0.54), int(center.y() - radius * 0.54),
            int(radius * 1.08), int(radius * 1.08),
        )

        painter.setPen(QColor("#d9f7ff"))
        painter.setFont(QFont("Noto Sans", 14, QFont.Weight.DemiBold))
        painter.drawText(
            rect.adjusted(20, int(radius * 0.82), -20, -8),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "DÉPOSE TES IMAGES ICI",
        )

        painter.setPen(QColor("#7893b3"))
        painter.setFont(QFont("Noto Sans", 10))
        painter.drawText(
            rect.adjusted(20, int(radius * 0.82 + 44), -20, -8),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "ou utilise les commandes d'importation ci-dessus",
        )

    def dragEnterEvent(self, event):

        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):

        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):

        paths = []

        for url in event.mimeData().urls():

            if url.isLocalFile():
                paths.append(
                    Path(url.toLocalFile())
                )

        if paths:
            self.paths_dropped.emit(paths)

        event.acceptProposedAction()


class SingularityMark(QWidget):
    """Emblème abstrait : disque d'accrétion et horizon des événements."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(132, 88)
        self.phase = 0.0
        self.animation = QTimer(self)
        self.animation.setInterval(40)
        self.animation.timeout.connect(self.advance)
        self.animation.start()

    def advance(self):
        self.phase = (self.phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2

        # Les ellipses aplaties forment la lumière courbée autour du noyau.
        for index, (width, alpha, thickness) in enumerate((
            (108, 32, 1), (94, 54, 2), (79, 108, 2), (66, 180, 2),
        )):
            painter.setPen(QPen(QColor(100, 226, 255, alpha), thickness))
            y_offset = sin(self.phase * 6.28 + index) * 1.8
            painter.drawEllipse(
                int(center_x - width / 2), int(center_y - 16 + y_offset),
                width, 32,
            )

        # Partie lumineuse de l'anneau d'accrétion, devant l'horizon.
        painter.setPen(QPen(QColor("#d2fbff"), 3))
        painter.drawArc(27, 25, 78, 32, int(2020 + self.phase * 1200), 1600)
        painter.setPen(QPen(QColor("#8a62ff"), 2))
        painter.drawArc(20, 22, 88, 37, int(5350 - self.phase * 1000), 1100)

        # Horizon : volontairement opaque, il absorbe le décor sous-jacent.
        painter.setPen(QPen(QColor("#29476d"), 1))
        painter.setBrush(QColor("#02040c"))
        painter.drawEllipse(int(center_x - 20), int(center_y - 20), 40, 40)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0a1028"))
        painter.drawEllipse(int(center_x - 12), int(center_y - 12), 24, 24)


class Singularity(QMainWindow):

    def __init__(self):

        super().__init__()

        self.files = []
        self.worker = None

        self.setWindowTitle(
            "Singularity — Image Optimizer"
        )

        self.setMinimumSize(780, 640)
        self.resize(920, 720)

        self.build_interface()

    def build_interface(self):

        central = QWidget()
        central.setObjectName("spaceCanvas")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        layout.setContentsMargins(
            30, 28, 30, 30
        )

        layout.setSpacing(16)

        # -----------------------------
        # HEADER — identite de console orbitale
        # -----------------------------

        header = QFrame()
        header.setObjectName("orbitalHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 17, 22, 17)

        identity = QVBoxLayout()
        identity.setSpacing(2)

        eyebrow = QLabel("SINGULARITY  /  HORIZON DES ÉVÉNEMENTS")
        eyebrow.setObjectName("eyebrow")

        title = QLabel("Singularity")

        title.setFont(
            QFont(
                "Noto Sans",
                26,
                QFont.Weight.Bold
            )
        )

        subtitle = QLabel("Comprime la matière visuelle. Les originaux restent hors de l'horizon.")

        subtitle.setObjectName(
            "subtitle"
        )

        identity.addWidget(eyebrow)
        identity.addWidget(title)
        identity.addWidget(subtitle)

        system_state = QLabel("●  HORIZON STABLE")
        system_state.setObjectName("systemState")

        header_layout.addLayout(identity)
        header_layout.addStretch()
        header_layout.addWidget(SingularityMark(), 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addSpacing(14)
        header_layout.addWidget(system_state, 0, Qt.AlignmentFlag.AlignTop)

        layout.addWidget(header)

        # -----------------------------
        # SETTINGS
        # -----------------------------

        settings = QFrame()

        settings.setObjectName(
            "settingsCard"
        )

        settings_layout = QHBoxLayout(
            settings
        )

        settings_layout.setContentsMargins(
            18, 15, 18, 15
        )

        format_label = QLabel("<span class='metricLabel'>FORMAT</span><br><b>WebP</b>")

        resolution_label = QLabel("<span class='metricLabel'>MAXIMUM</span><br><b>2560 × 1440</b>")

        dpi_label = QLabel("<span class='metricLabel'>DPI</span><br><b>72</b>")

        quality_container = QVBoxLayout()

        quality_text = QLabel("QUALITÉ")
        quality_text.setObjectName("qualityLabel")

        self.quality = QSpinBox()

        self.quality.setRange(
            40, 100
        )

        self.quality.setValue(
            DEFAULT_QUALITY
        )

        self.quality.setSuffix(" %")

        quality_container.addWidget(
            quality_text
        )

        quality_container.addWidget(
            self.quality
        )

        settings_layout.addWidget(
            format_label
        )

        settings_layout.addWidget(
            resolution_label
        )

        settings_layout.addWidget(
            dpi_label
        )

        settings_layout.addLayout(
            quality_container
        )

        settings_layout.addStretch()

        layout.addWidget(settings)

        # -----------------------------
        # BUTTONS
        # -----------------------------

        buttons = QHBoxLayout()

        add_files = QPushButton(
            "＋  IMPORTER DES IMAGES"
        )

        add_folder = QPushButton(
            "＋  IMPORTER UN DOSSIER"
        )

        clear = QPushButton(
            "RÉINITIALISER"
        )

        add_files.clicked.connect(
            self.select_files
        )

        add_folder.clicked.connect(
            self.select_folder
        )

        clear.clicked.connect(
            self.clear_files
        )

        buttons.addWidget(
            add_files
        )

        buttons.addWidget(
            add_folder
        )

        buttons.addStretch()

        buttons.addWidget(
            clear
        )

        layout.addLayout(buttons)

        # -----------------------------
        # DROP AREA
        # -----------------------------

        self.file_list = DropListWidget()

        self.file_list.setObjectName(
            "fileList"
        )

        self.file_list.paths_dropped.connect(
            self.add_dropped_paths
        )

        layout.addWidget(
            self.file_list,
            1
        )

        # -----------------------------
        # STATUS
        # -----------------------------

        self.status = QLabel("HORIZON VIDE — AJOUTE DE LA MATIÈRE VISUELLE")

        self.status.setObjectName(
            "status"
        )

        layout.addWidget(
            self.status
        )

        self.progress = QProgressBar()

        self.progress.setRange(
            0, 100
        )

        self.progress.setValue(
            0
        )

        self.progress.setTextVisible(
            False
        )

        self.progress.setFixedHeight(
            7
        )

        layout.addWidget(
            self.progress
        )

        # -----------------------------
        # CONVERT BUTTON
        # -----------------------------

        self.convert_button = QPushButton(
            "FRANCHIR L'HORIZON  →"
        )

        self.convert_button.setObjectName(
            "convertButton"
        )

        self.convert_button.setMinimumHeight(
            50
        )

        self.convert_button.clicked.connect(
            self.start_conversion
        )

        layout.addWidget(
            self.convert_button
        )

        self.apply_style()

    def apply_style(self):

        self.setStyleSheet("""
            QWidget {
                color: #e7f5ff;
                font-family:
                    "Noto Sans",
                    "DejaVu Sans",
                    sans-serif;
                font-size: 13px;
            }

            QWidget#spaceCanvas {
                background: qradialgradient(cx: 0.84, cy: 0.04, radius: 1.08,
                    fx: 0.84, fy: 0.04, stop: 0 #17123b, stop: 0.34 #0b0e27,
                    stop: 0.72 #050716, stop: 1 #02030a);
            }

            QFrame#orbitalHeader {
                background: rgba(7, 11, 32, 215);
                border: 1px solid #433b83;
                border-radius: 16px;
            }

            QLabel#eyebrow, QLabel#qualityLabel {
                color: #aa8aff;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1.4px;
            }

            QLabel#systemState {
                color: #b6f9ff;
                background: rgba(87, 71, 184, 38);
                border: 1px solid #5d57a8;
                border-radius: 12px;
                padding: 5px 9px;
                font-size: 10px;
                font-weight: bold;
            }

            QLabel#subtitle {
                color: #9db4d1;
                font-size: 14px;
            }

            QFrame#settingsCard {
                background: rgba(9, 13, 38, 222);
                border: 1px solid #3d407a;
                border-radius: 14px;
            }

            QFrame#settingsCard QLabel {
                color: #aab1dc;
            }

            QFrame#settingsCard QLabel b { color: #f2f1ff; font-size: 15px; }
            QFrame#settingsCard .metricLabel { color: #958cca; font-size: 10px; font-weight: bold; }

            QPushButton {
                background: rgba(30, 28, 76, 205);
                border: 1px solid #514a95;
                border-radius: 9px;
                padding: 10px 16px;
                color: #e1dcff;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }

            QPushButton:hover {
                background: #423891;
                border-color: #a3edff;
            }

            QPushButton:pressed {
                background: #211d58;
            }

            QPushButton:disabled {
                color: #625d94;
                background: #0a0b27;
            }

            QPushButton#convertButton {
                background: #d9ccff;
                color: #120b2e;
                border: 1px solid #f0eaff;
                border-radius: 12px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton#convertButton:hover {
                background: #f0eaff;
            }

            QListWidget#fileList {
                background: rgba(3, 5, 20, 185);
                border: 1px dashed #6156a6;
                border-radius: 14px;
                padding: 12px;
                outline: none;
            }

            QListWidget#fileList:focus {
                border: 1px solid #b3a0ff;
            }

            QListWidget::item {
                background: rgba(31, 28, 77, 180);
                border: 1px solid #45438b;
                padding: 10px;
                margin: 2px;
                border-radius: 7px;
            }

            QListWidget::item:selected {
                background: #4d429d;
                border-color: #baaeff;
            }

            QLabel#status {
                color: #aea7e2;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.7px;
            }

            QProgressBar {
                background: #090a25;
                border: 1px solid #3c3979;
                border-radius: 3px;
            }

            QProgressBar::chunk {
                background: #bca7ff;
                border-radius: 3px;
            }

            QSpinBox {
                background: #1a1947;
                color: #f0eeff;
                border: 1px solid #5b55a4;
                border-radius: 6px;
                padding: 5px;
            }
        """)

    # =================================
    # FILE MANAGEMENT
    # =================================

    def select_files(self):

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des images",
            str(Path.home()),
            (
                "Images (*.jpg *.jpeg *.png "
                "*.webp *.bmp *.tif *.tiff)"
            ),
        )

        self.add_paths(
            [Path(path) for path in files]
        )

    def select_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner un dossier",
            str(Path.home()),
        )

        if not folder:
            return

        paths = collect_images(
            Path(folder)
        )

        self.add_paths(paths)

    def add_dropped_paths(self, paths):

        files = []

        for path in paths:

            if path.is_dir():
                files.extend(
                    collect_images(path)
                )

            elif (
                path.is_file()
                and path.suffix.lower()
                in SUPPORTED_EXTENSIONS
            ):
                files.append(path)

        self.add_paths(files)

    def add_paths(self, paths):

        existing = {
            str(path.resolve())
            for path in self.files
        }

        added = 0

        for path in paths:

            if not path.exists():
                continue

            if path.suffix.lower() not in (
                SUPPORTED_EXTENSIONS
            ):
                continue

            resolved = str(
                path.resolve()
            )

            if resolved in existing:
                continue

            self.files.append(path)
            existing.add(resolved)

            try:
                size = format_size(
                    path.stat().st_size
                )
            except OSError:
                size = "?"

            item = QListWidgetItem(
                f"{path.name}   ·   {size}"
            )

            self.file_list.addItem(
                item
            )

            added += 1

        self.update_status()

    def clear_files(self):

        self.files.clear()

        self.file_list.clear()

        self.progress.setValue(
            0
        )

        self.status.setText(
            "HORIZON VIDE — AJOUTE DE LA MATIÈRE VISUELLE"
        )

    def update_status(self):

        count = len(self.files)

        if count == 0:

            self.status.setText(
                "HORIZON VIDE — AJOUTE DE LA MATIÈRE VISUELLE"
            )

        elif count == 1:

            self.status.setText(
                "1 CORPS VISUEL PRÊT À FRANCHIR L'HORIZON"
            )

        else:

            self.status.setText(
                f"{count} CORPS VISUELS PRÊTS À FRANCHIR L'HORIZON"
            )

    # =================================
    # CONVERSION
    # =================================

    def start_conversion(self):

        if not self.files:

            QMessageBox.information(
                self,
                "Aucune image",
                "Ajoute des images avant de lancer "
                "l'optimisation."
            )

            return

        # Le dossier de destination est choisi une seule fois.
        base_folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination",
            str(self.files[0].parent),
        )

        if not base_folder:
            return

        output_dir = (
            Path(base_folder)
            / "Singularity"
        )

        self.convert_button.setEnabled(
            False
        )

        self.status.setText(
            "COMPRESSION EN COURS À L'INTÉRIEUR DE L'HORIZON..."
        )

        self.progress.setValue(
            0
        )

        self.worker = ConverterWorker(
            self.files.copy(),
            output_dir,
            self.quality.value(),
        )

        self.worker.progress.connect(
            self.progress.setValue
        )

        self.worker.status.connect(
            self.status.setText
        )

        self.worker.finished_conversion.connect(
            self.conversion_finished
        )

        self.worker.start()

    def conversion_finished(
        self,
        success,
        errors,
        before,
        after,
        output_dir,
    ):

        self.convert_button.setEnabled(
            True
        )

        if before > 0:

            reduction = (
                1 - (after / before)
            ) * 100

        else:

            reduction = 0

        saved = max(
            0,
            before - after
        )

        self.status.setText(
            f"HORIZON TRAVERSÉ — {success} image(s) optimisée(s)."
        )

        QMessageBox.information(
            self,
            "Singularity — Terminé",
            (
                "<b>Conversion terminée.</b><br><br>"
                f"Images : {success}<br>"
                f"Erreurs : {errors}<br><br>"
                f"Avant : {format_size(before)}<br>"
                f"Après : {format_size(after)}<br>"
                f"Économie : {format_size(saved)}<br>"
                f"Réduction : {reduction:.1f} %<br><br>"
                f"<b>Dossier :</b><br>{output_dir}"
            ),
        )

        self.worker = None


def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "Singularity"
    )

    app.setApplicationDisplayName(
        "Singularity"
    )

    window = Singularity()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()
