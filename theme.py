STYLE='''
QWidget { color:#26323f; font-family:"PingFang SC","Microsoft YaHei UI","Arial"; font-size:13px; }
QMainWindow,QDialog { background:#f5f7fa; }
QFrame#Header,QFrame#Tools,QFrame#Footer { background:white; border-bottom:1px solid #e4e8ee; }
QLabel#Title { font-size:20px; font-weight:650; color:#172330; }
QLabel#Subtle { color:#7b8795; font-size:12px; }
QLabel#Eyebrow { color:#527d9b; font-size:11px; font-weight:600; }
QLabel#EmptyTitle { color:#263747; font-size:25px; font-weight:600; }
QLabel#EmptyIcon { background:#e8f0f6; color:#3f7192; border-radius:20px; font-size:32px; padding:18px; }
QLabel#Hint { color:#607a8c; background:#edf4f9; border-radius:6px; padding:9px; }
QPushButton,QToolButton { color:#3d4b5b; background:white; border:1px solid #dce3ea; border-radius:6px; padding:7px 12px; min-height:18px; }
QPushButton:hover,QToolButton:hover { background:#f0f5f9; border-color:#aabfd0; }
QPushButton:pressed,QToolButton:pressed { background:#e5edf5; }
QPushButton:disabled,QToolButton:disabled { color:#a7b0ba; background:#f8f9fb; border-color:#e9edf2; }
QPushButton#Primary,QToolButton#Primary { color:white; background:#37678c; border-color:#37678c; font-weight:600; }
QPushButton#Primary:hover,QToolButton#Primary:hover { background:#2b5779; }
QPushButton#Danger { color:#a24a46; border-color:#ead6d3; }
QPushButton:checked,QToolButton:checked { background:#e7f0f7; border-color:#7199b7; color:#2c638a; }
QToolButton::menu-indicator { subcontrol-position:right center; right:8px; }
QMenu { background:white; border:1px solid #dce3ea; padding:6px; }
QMenu::item { padding:9px 23px; border-radius:4px; }
QMenu::item:selected { background:#eaf1f7; color:#2b5e83; }
QLineEdit,QTextEdit,QSpinBox,QDoubleSpinBox,QComboBox,QFontComboBox { background:white; border:1px solid #d9e0e8; border-radius:5px; padding:6px; selection-background-color:#d2e4f1; selection-color:#1e3e56; }
QLineEdit:focus,QTextEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus { border-color:#7299b6; }
QTextEdit:disabled { background:#f6f8fa; color:#98a3af; }
QComboBox::drop-down { border:0; width:20px; }
QCheckBox { spacing:7px; }
QCheckBox::indicator { width:14px; height:14px; border:1px solid #bbc8d3; border-radius:3px; background:white; }
QCheckBox::indicator:checked { background:#477d9f; border-color:#477d9f; image:none; }
QSlider::groove:horizontal { height:4px; background:#e1e7ed; border-radius:2px; }
QSlider::sub-page:horizontal { background:#7298b3; border-radius:2px; }
QSlider::handle:horizontal { background:#3d7196; width:12px; margin:-5px 0; border-radius:6px; }
QListWidget { background:#f8fafc; border:0; outline:0; }
QListWidget::item { border:1px solid transparent; margin:6px 10px; padding:5px; border-radius:7px; }
QListWidget::item:selected { background:#e6eff7; border:1px solid #89abc4; }
QListWidget::item:hover { background:#edf3f8; }
QScrollArea,QWidget#RightPanel { background:white; border:0; }
QScrollBar:vertical { background:transparent; width:7px; margin:0; }
QScrollBar::handle:vertical { background:#cad3dc; border-radius:3px; min-height:28px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QSplitter::handle { background:#e2e7ed; }
QGroupBox { background:white; border:1px solid #e2e8ee; border-radius:7px; margin-top:15px; padding:14px 10px 9px; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 4px; color:#5f7182; }
QTableWidget { background:white; border:1px solid #dce4eb; gridline-color:#edf0f4; }
QHeaderView::section { background:#f3f6f9; color:#6a7d8f; border:0; padding:8px; }
QProgressBar { border:1px solid #dfe6ed; border-radius:5px; background:#f7f9fb; text-align:center; }
QProgressBar::chunk { background:#6b94b1; border-radius:4px; }
'''
