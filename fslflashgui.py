#!/usr/bin/python3

import configparser
import os
import sys

from PyQt5.QtCore import Qt, QThread, QDir, QIODevice, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QProgressDialog, QMessageBox

from ui import Ui_main_window
from fslflash import flash

class FlashHandler(QThread):
    status = pyqtSignal(str)
    success = pyqtSignal()

    def __init__(self, files, serial, parent=None):
        QThread.__init__(self, parent)
        self.files = files
        self.serial = serial

    def run(self):
        f = self.files
        flash(f['bootstrap'], f['uboot'], f['ubootenv'], f['kernel'], f['rootfs'], f['userdata'], self.serial, statusio=self)
        self.success.emit()

    def write(self, text):
        self.status.emit(text.rstrip())

    def flush(self):
        pass


class MainWindow(QMainWindow, Ui_main_window):
    def __init__(self):
        QMainWindow.__init__(self)
        self.setupUi(self)
        self.bootstrap_button.setStyleSheet('text-align: left')
        self.uboot_button.setStyleSheet('text-align: left')
        self.ubootenv_button.setStyleSheet('text-align: left')
        self.kernel_button.setStyleSheet('text-align: left')
        self.rootfs_button.setStyleSheet('text-align: left')
        self.userdata_button.setStyleSheet('text-align: left')
        self.action_open.triggered.connect(self.open_config)
        self.action_save.triggered.connect(self.save_config)
        self.action_exit.triggered.connect(self.close)
        self.all_selected.stateChanged.connect(self.select_all)
        self.bootstrap_button.clicked.connect(lambda: self.open_file('bootstrap image', '*.imx;;*', self.bootstrap_button))
        self.uboot_button.clicked.connect(lambda: self.open_file('uboot image', '*.nand;;*', self.uboot_button))
        self.ubootenv_button.clicked.connect(lambda: self.open_file('uboot environment template', '*.tmpl;;*', self.ubootenv_button))
        self.kernel_button.clicked.connect(lambda: self.open_file('kernel image', 'uImage;;*', self.kernel_button))
        self.rootfs_button.clicked.connect(lambda: self.open_file('rootfs image', '*.jffs2;;*', self.rootfs_button))
        self.userdata_button.clicked.connect(lambda: self.open_file('userdata image', '*.jffs2;;*', self.userdata_button))
        self.flash_button.clicked.connect(self.do_flash)
        self.paths_relative_to = os.getcwd()
        self.open_path = os.getcwd()
        self.config_file = ''
        self.flash_thread = None
        self.flash_dialog = QMessageBox(self)
        self.flash_dialog.setWindowModality(Qt.ApplicationModal)
        self.flash_dialog.setWindowTitle('Flashing Device...')
        self.flash_dialog.setStandardButtons(QMessageBox.Cancel)
        self.flash_dialog.setMinimumWidth(600)
        self.flash_dialog.buttonClicked.connect(self.flash_cancel)

    def open_config(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Open fslflash config file', self.open_path, '*.config')
        if len(f) == 0:
            return
        self.set_config(f)

    def set_config(self, f):
        self.config_file = f
        self.paths_relative_to = os.path.dirname(f)
        config = configparser.ConfigParser()
        config.read(self.config_file)
        for key in config['files']:
            if key == 'bootstrap':
                self.bootstrap_button.setText(config['files'][key])
            if key == 'uboot':
                self.uboot_button.setText(config['files'][key])
            if key == 'ubootenv':
                self.ubootenv_button.setText(config['files'][key])
            if key == 'kernel':
                self.kernel_button.setText(config['files'][key])
            if key == 'rootfs':
                self.rootfs_button.setText(config['files'][key])
            if key == 'userdata':
                self.userdata_button.setText(config['files'][key])
        if 'device' in config and 'serial' in config['device']:
            self.serial_spinbox.setValue(int(config['device']['serial']))

    def save_config(self):
        f, _ = QFileDialog.getSaveFileName(self, 'Save fslflash config file', self.config_file, '*.config')
        if len(f) == 0:
            return
        self.config_file = f
        configdir = os.path.dirname(self.config_file)
        config = configparser.ConfigParser()
        config['device'] = {}
        config['files'] = {}
        if self.serial_spinbox.value() != 0:
            config['device']['serial'] = str(self.serial_spinbox.value())
        if self.bootstrap_button.text() != 'None Selected':
            config['files']['bootstrap'] = os.path.relpath(os.path.join(self.paths_relative_to, self.bootstrap_button.text()), configdir)
        if self.uboot_button.text() != 'None Selected':
            config['files']['uboot'] = os.path.relpath(os.path.join(self.paths_relative_to, self.uboot_button.text()), configdir)
        if self.ubootenv_button.text() != 'None Selected':
            config['files']['ubootenv'] = os.path.relpath(os.path.join(self.paths_relative_to, self.ubootenv_button.text()), configdir)
        if self.kernel_button.text() != 'None Selected':
            config['files']['kernel'] = os.path.relpath(os.path.join(self.paths_relative_to, self.kernel_button.text()), configdir)
        if self.rootfs_button.text() != 'None Selected':
            config['files']['rootfs'] = os.path.relpath(os.path.join(self.paths_relative_to, self.rootfs_button.text()), configdir)
        if self.userdata_button.text() != 'None Selected':
            config['files']['userdata'] = os.path.relpath(os.path.join(self.paths_relative_to, self.userdata_button.text()), configdir)
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)

    def select_all(self, checked):
        self.bootstrap_selected.setCheckState(checked)
        self.uboot_selected.setCheckState(checked)
        self.ubootenv_selected.setCheckState(checked)
        self.kernel_selected.setCheckState(checked)
        self.rootfs_selected.setCheckState(checked)
        self.userdata_selected.setCheckState(checked)

    def open_file(self, filetype, typefilter, button):
        f, _ = QFileDialog.getOpenFileName(self, 'Open {0} file'.format(filetype), self.open_path, typefilter)
        if len(f) == 0:
            return
        self.open_path = os.path.dirname(f)
        f = os.path.relpath(f, self.paths_relative_to)
        button.setText(f)

    def do_flash(self):
        files = {}
        files['bootstrap'] = os.path.join(self.paths_relative_to, self.bootstrap_button.text()) if self.bootstrap_selected.isChecked() else None
        files['uboot'] = os.path.join(self.paths_relative_to, self.uboot_button.text()) if self.uboot_selected.isChecked() else None
        files['ubootenv'] = os.path.join(self.paths_relative_to, self.ubootenv_button.text()) if self.ubootenv_selected.isChecked() else None
        files['kernel'] = os.path.join(self.paths_relative_to, self.kernel_button.text()) if self.kernel_selected.isChecked() else None
        files['rootfs'] = os.path.join(self.paths_relative_to, self.rootfs_button.text()) if self.rootfs_selected.isChecked() else None
        files['userdata'] = os.path.join(self.paths_relative_to, self.userdata_button.text()) if self.userdata_selected.isChecked() else None
        self.flash_thread = FlashHandler(files, self.serial_spinbox.value(), self)
        self.flash_thread.status.connect(self.flash_status)
        self.flash_thread.success.connect(self.flash_complete)
        self.flash_dialog.setText('Starting Flash')
        self.flash_dialog.show()
        self.flash_thread.start()

    def flash_status(self, status):
        self.flash_dialog.setText(status)

    def flash_complete(self):
        self.flash_dialog.accept()
        self.statusbar.showMessage('Flash Success!')
        self.serial_spinbox.setValue(self.serial_spinbox.value() + 1)

    def flash_cancel(self, button):
        if self.flash_thread.isRunning():
            self.flash_thread.terminate()
        self.statusbar.showMessage('Flash Cancelled')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        window.set_config(sys.argv[1])
    sys.exit(app.exec_())