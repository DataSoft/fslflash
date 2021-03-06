# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'fsl/ui/main.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_main_window(object):
    def setupUi(self, main_window):
        main_window.setObjectName("main_window")
        main_window.resize(420, 339)
        self.central_widget = QtWidgets.QWidget(main_window)
        self.central_widget.setObjectName("central_widget")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.central_widget)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.serial_box = QtWidgets.QGroupBox(self.central_widget)
        self.serial_box.setObjectName("serial_box")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.serial_box)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.serial_spinbox = QtWidgets.QSpinBox(self.serial_box)
        self.serial_spinbox.setSuffix("")
        self.serial_spinbox.setPrefix("")
        self.serial_spinbox.setMaximum(1000000)
        self.serial_spinbox.setObjectName("serial_spinbox")
        self.horizontalLayout_2.addWidget(self.serial_spinbox)
        self.program_button = QtWidgets.QPushButton(self.serial_box)
        self.program_button.setObjectName("program_button")
        self.horizontalLayout_2.addWidget(self.program_button)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.verticalLayout_3.addWidget(self.serial_box)
        spacerItem1 = QtWidgets.QSpacerItem(17, 13, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout_3.addItem(spacerItem1)
        self.flash_box = QtWidgets.QGroupBox(self.central_widget)
        self.flash_box.setObjectName("flash_box")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.flash_box)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.form_layout = QtWidgets.QFormLayout()
        self.form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.form_layout.setHorizontalSpacing(40)
        self.form_layout.setObjectName("form_layout")
        self.label = QtWidgets.QLabel(self.flash_box)
        self.label.setObjectName("label")
        self.form_layout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label)
        self.bootstrap_label = QtWidgets.QLabel(self.flash_box)
        self.bootstrap_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.bootstrap_label.setObjectName("bootstrap_label")
        self.form_layout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.bootstrap_label)
        self.label_3 = QtWidgets.QLabel(self.flash_box)
        self.label_3.setObjectName("label_3")
        self.form_layout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.uboot_label = QtWidgets.QLabel(self.flash_box)
        self.uboot_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.uboot_label.setObjectName("uboot_label")
        self.form_layout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.uboot_label)
        self.label_4 = QtWidgets.QLabel(self.flash_box)
        self.label_4.setObjectName("label_4")
        self.form_layout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_4)
        self.fdt_label = QtWidgets.QLabel(self.flash_box)
        self.fdt_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.fdt_label.setObjectName("fdt_label")
        self.form_layout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.fdt_label)
        self.label_5 = QtWidgets.QLabel(self.flash_box)
        self.label_5.setObjectName("label_5")
        self.form_layout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_5)
        self.kernel_label = QtWidgets.QLabel(self.flash_box)
        self.kernel_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.kernel_label.setObjectName("kernel_label")
        self.form_layout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.kernel_label)
        self.label_6 = QtWidgets.QLabel(self.flash_box)
        self.label_6.setObjectName("label_6")
        self.form_layout.setWidget(5, QtWidgets.QFormLayout.LabelRole, self.label_6)
        self.rootfs_label = QtWidgets.QLabel(self.flash_box)
        self.rootfs_label.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.rootfs_label.setObjectName("rootfs_label")
        self.form_layout.setWidget(5, QtWidgets.QFormLayout.FieldRole, self.rootfs_label)
        self.verticalLayout_2.addLayout(self.form_layout)
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.horizontal_layout.setObjectName("horizontal_layout")
        spacerItem2 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontal_layout.addItem(spacerItem2)
        self.flash_button = QtWidgets.QPushButton(self.flash_box)
        self.flash_button.setObjectName("flash_button")
        self.horizontal_layout.addWidget(self.flash_button)
        self.verticalLayout_2.addLayout(self.horizontal_layout)
        self.verticalLayout_3.addWidget(self.flash_box)
        main_window.setCentralWidget(self.central_widget)
        self.menubar = QtWidgets.QMenuBar(main_window)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 420, 26))
        self.menubar.setObjectName("menubar")
        self.menu_file = QtWidgets.QMenu(self.menubar)
        self.menu_file.setObjectName("menu_file")
        main_window.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(main_window)
        self.statusbar.setObjectName("statusbar")
        main_window.setStatusBar(self.statusbar)
        self.action_open = QtWidgets.QAction(main_window)
        self.action_open.setObjectName("action_open")
        self.action_exit = QtWidgets.QAction(main_window)
        self.action_exit.setObjectName("action_exit")
        self.action_save = QtWidgets.QAction(main_window)
        self.action_save.setObjectName("action_save")
        self.action_save_as = QtWidgets.QAction(main_window)
        self.action_save_as.setObjectName("action_save_as")
        self.menu_file.addAction(self.action_open)
        self.menu_file.addAction(self.action_exit)
        self.menubar.addAction(self.menu_file.menuAction())

        self.retranslateUi(main_window)
        QtCore.QMetaObject.connectSlotsByName(main_window)

    def retranslateUi(self, main_window):
        _translate = QtCore.QCoreApplication.translate
        main_window.setWindowTitle(_translate("main_window", "MainWindow"))
        self.serial_box.setTitle(_translate("main_window", "Serial"))
        self.program_button.setText(_translate("main_window", "Program"))
        self.flash_box.setTitle(_translate("main_window", "Firmware"))
        self.label.setText(_translate("main_window", "bootstrap"))
        self.bootstrap_label.setText(_translate("main_window", "None Selected"))
        self.label_3.setText(_translate("main_window", "u-boot"))
        self.uboot_label.setText(_translate("main_window", "None Selected"))
        self.label_4.setText(_translate("main_window", "device tree"))
        self.fdt_label.setText(_translate("main_window", "None Selected"))
        self.label_5.setText(_translate("main_window", "kernel"))
        self.kernel_label.setText(_translate("main_window", "None Selected"))
        self.label_6.setText(_translate("main_window", "rootfs"))
        self.rootfs_label.setText(_translate("main_window", "None Selected"))
        self.flash_button.setText(_translate("main_window", "Flash"))
        self.menu_file.setTitle(_translate("main_window", "Fi&le"))
        self.action_open.setText(_translate("main_window", "&Open Package"))
        self.action_open.setShortcut(_translate("main_window", "Ctrl+O"))
        self.action_exit.setText(_translate("main_window", "E&xit"))
        self.action_exit.setShortcut(_translate("main_window", "Ctrl+X"))
        self.action_save.setText(_translate("main_window", "&Save Config"))
        self.action_save.setShortcut(_translate("main_window", "Ctrl+S"))
        self.action_save_as.setText(_translate("main_window", "Save &As"))
        self.action_save_as.setShortcut(_translate("main_window", "Ctrl+A"))

