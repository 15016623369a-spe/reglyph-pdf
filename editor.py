"""图片pdf文字编辑器 — a focused desktop workflow built on OCRPDF-TO-PPT."""
import os,sys,copy,json,re,logging,time
from platform_config import configure_environment,data_dir,cache_dir,ui_font,initialize_data
CPU_THREADS=configure_environment()
initialize_data()
from pathlib import Path
os.environ.setdefault('QT_API','pyside6')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK','True')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
ROOT=Path(__file__).resolve().parent
# Load network/image helpers before Qt installs its import feature hook. Loading
# requests for the first time inside a worker can otherwise stall on source inspection.
import requests,urllib3,encodings.idna
import numpy,cv2
import batch_clean
from PIL import Image,ImageFont
cv2.setNumThreads(CPU_THREADS)
from PySide6.QtCore import Qt,QTimer,QSize,QSizeF,QRectF,QPointF,QUrl
from PySide6.QtGui import QFont,QTextDocument,QTextOption,QTextCursor,QTextBlockFormat,QColor,QImage,QPainter,QPdfWriter,QPageSize,QPageLayout,QAction,QKeySequence,QDesktopServices,QIcon,QTransform
from PySide6.QtWidgets import *
import qtawesome as qta
import engine as core
from workflow import *
from theme import STYLE
from precision_ui import PrecisionMixin
core.GLOBAL_STYLE=STYLE
core.RIGHT_PANEL_W=310
core.PPT_THEME_RED='#37678c'

class LegacyEditor(core.PPTCloneApp):
    def __init__(self):
        self.project_path=None;self._saved_fingerprint=None;self._autosaved_fingerprint=None;self._allow_close=False
        super().__init__()
        self.setWindowTitle(APP_NAME);self.resize(1420,900);self.setMinimumSize(1100,720)
        self.setStyleSheet(STYLE)
        self._reset_right_panel_state()
        self._saved_fingerprint=fingerprint(self)
        self.autosave_timer=QTimer(self);self.autosave_timer.timeout.connect(self.autosave);self.autosave_timer.start(120000)
        self._ui_timer=QTimer(self);self._ui_timer.timeout.connect(self.update_workflow_status);self._ui_timer.start(1200)
        self.setAcceptDrops(True);self.update_workflow_status()

    def button(self,text,slot,parent_layout=None,icon=None,primary=False):
        b=QPushButton(text)
        if icon:b.setIcon(qta.icon(icon,color='white' if primary else '#56758d'))
        if primary:b.setObjectName('Primary')
        b.setCursor(Qt.PointingHandCursor);b.clicked.connect(slot)
        if parent_layout is not None:parent_layout.addWidget(b)
        return b

    def menu_button(self,text,items,layout,primary=False):
        b=QToolButton();b.setText(text);b.setPopupMode(QToolButton.InstantPopup)
        b.setMinimumHeight(34);b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        if primary:b.setObjectName('Primary')
        menu=QMenu(b)
        for label,slot in items:
            if label is None:menu.addSeparator()
            else:menu.addAction(label,slot)
        b.setMenu(menu);layout.addWidget(b);return b

    def init_ui(self):
        super().init_ui()
        layout=self.centralWidget().layout();self.tabs.hide()
        old_status=layout.itemAt(layout.count()-1).widget();old_status.hide()
        header=QFrame();header.setObjectName('Header');header.setFixedHeight(88);hl=QHBoxLayout(header);hl.setContentsMargins(24,17,24,16);hl.setSpacing(10)
        name=QVBoxLayout();name.setSpacing(3);title=QLabel(APP_NAME);title.setObjectName('Title');name.addWidget(title)
        self.document_label=QLabel('把图片文字，变成可编辑内容');self.document_label.setObjectName('Subtle');name.addWidget(self.document_label)
        hl.addLayout(name);hl.addStretch()
        self.button('打开工程',self.open_project_dialog,hl,icon='fa5s.folder-open')
        self.button('保存工程',self.save_project_dialog,hl,icon='fa5s.save')
        self.button('使用指南',self.show_guide,hl,icon='fa5s.book-open')
        more=self.menu_button('更多',[('另存工程',lambda:self.save_project_dialog(save_as=True)),('打开自动备份',self.open_recovery),(None,None),('识别设置',self.open_ocr_settings),('擦字设置',self.open_inpaint_settings),('清除修复缓存',self.clear_repair_cache),('查看操作记录',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()/'操作记录')))),('关于与开源说明',self.show_about)],hl);more.setSizePolicy(QSizePolicy.Fixed,QSizePolicy.Fixed)
        layout.insertWidget(0,header)
        steps=QFrame();steps.setObjectName('Tools');steps.setFixedHeight(65);s=QHBoxLayout(steps);s.setContentsMargins(24,12,24,12);s.setSpacing(12)
        self.menu_button('01  导入文件',[('导入 PDF',self.import_pdfs),('导入图片',self.import_images)],s)
        self.menu_button('02  识别文字',[('识别本页',self.run_ocr_current_slide),('识别全部页面',self.run_ocr_all_images)],s,True)
        self.menu_button('03  清除原字',[('智能清除本页原字',self.inpaint_current_slide),('智能清除全部页面原字',self.inpaint_all_slides),(None,None),('擦除选区中的残留 / Logo',self.erase_region_dialog),('批量擦除同一位置',self.batch_region_dialog),('纯色页面快速去字',self.fill_current_slide)],s)
        self.menu_button('04  编辑与排版',[('查找 / 替换品牌',self.replace_dialog),('统一字号',self.fonts_dialog),('合并选区为段落',self.merge_dialog),('新增文字',self.insert_text_box)],s)
        self.menu_button('05  导出成品',[('导出可编辑 PPT',self.export_ppt),('导出 PDF',self.export_pdf)],s,True)
        layout.insertWidget(1,steps)
        tools=QFrame();tools.setObjectName('Tools');tools.setFixedHeight(55);tl=QHBoxLayout(tools);tl.setContentsMargins(24,8,24,8);tl.setSpacing(7)
        self.button('撤销',self.undo,tl,icon='fa5s.undo');self.button('重做',self.redo,tl,icon='fa5s.redo')
        self.roi_button=self.button('框选区域',self.toggle_roi_select_mode,tl,icon='fa5s.vector-square');self.roi_button.setCheckable(True)
        self.button('擦除选区',self.erase_region_dialog,tl,icon='fa5s.eraser')
        self.button('查找替换',self.replace_dialog,tl,icon='fa5s.search')
        self.button('统一字号',self.fonts_dialog,tl,icon='fa5s.text-height')
        self.button('新增文字',self.insert_text_box,tl,icon='fa5s.plus')
        tl.addStretch();self.preview_button=self.button('查看原图',self.toggle_inpaint_preview,tl)
        self.button('适应窗口',self.fit_view_to_window,tl,icon='fa5s.expand')
        layout.insertWidget(2,tools)
        # Thumbnail rail with page management kept separate from editing actions.
        self.list_thumb.setMinimumWidth(195);self.list_thumb.setMaximumWidth(195);self.list_thumb.setStyleSheet('')
        rail=QWidget();rail.setFixedWidth(195);rl=QVBoxLayout(rail);rl.setContentsMargins(0,12,0,10)
        row=QHBoxLayout();row.setContentsMargins(15,0,12,0);lab=QLabel('页面');lab.setObjectName('Eyebrow');row.addWidget(lab);row.addStretch()
        self.page_menu=self.menu_button('管理',[('新建空白页',self.new_blank_slide),('复制当前页',self.duplicate_slide),('上移当前页',self.move_slide_up),('下移当前页',self.move_slide_down),('删除当前页',self.delete_slide)],row)
        rl.addLayout(row);self.list_thumb.setParent(rail);rl.addWidget(self.list_thumb)
        self.splitter.insertWidget(0,rail)
        # Canvas header and a useful, intentionally quiet empty state.
        center=QWidget();cl=QVBoxLayout(center);cl.setContentsMargins(0,0,0,0);cl.setSpacing(0)
        hintrow=QFrame();hintrow.setStyleSheet('background:#f7f9fc;');hr=QHBoxLayout(hintrow);hr.setContentsMargins(18,10,18,10)
        self.hint=QLabel('先导入 PDF 或图片，再识别和清除底图原字。');self.hint.setObjectName('Subtle');hr.addWidget(self.hint);cl.addWidget(hintrow)
        self.canvas_stack=QStackedWidget();empty=QWidget();el=QVBoxLayout(empty);el.setAlignment(Qt.AlignCenter);el.setSpacing(15)
        ic=QLabel('Aa');ic.setObjectName('EmptyIcon');ic.setAlignment(Qt.AlignCenter);ic.setFixedSize(92,92);el.addWidget(ic,0,Qt.AlignHCenter)
        big=QLabel('让图片里的文字，重新可编辑');big.setObjectName('EmptyTitle');big.setAlignment(Qt.AlignCenter);el.addWidget(big)
        sub=QLabel('保留画面 · 修改文案 · 替换品牌\n从宣传册、产品图或扫描 PDF 开始');sub.setAlignment(Qt.AlignCenter);sub.setObjectName('Subtle');el.addWidget(sub)
        er=QHBoxLayout();er.setAlignment(Qt.AlignCenter);self.button('导入 PDF',self.import_pdfs,er,primary=True);self.button('导入图片',self.import_images,er);el.addLayout(er)
        drop=QLabel('也可以把 PDF、图片或工程文件拖到这里');drop.setObjectName('Subtle');drop.setAlignment(Qt.AlignCenter);el.addWidget(drop)
        self.canvas_stack.addWidget(empty);self.view.setParent(self.canvas_stack);self.view.setStyleSheet('background:#e9edf2;border:0;');self.canvas_stack.addWidget(self.view);cl.addWidget(self.canvas_stack)
        self.splitter.insertWidget(1,center)
        self.right_panel_scroll.setFixedWidth(310)
        footer=QFrame();footer.setObjectName('Footer');footer.setFixedHeight(44);fl=QHBoxLayout(footer);fl.setContentsMargins(18,7,18,7)
        self.status_label=QLabel('未导入文件');self.status_label.setObjectName('Subtle');fl.addWidget(self.status_label);fl.addStretch()
        self.save_label=QLabel('工程文件可保存后继续编辑');self.save_label.setObjectName('Subtle');fl.addWidget(self.save_label)
        fl.addWidget(self.zoom_slider);fl.addWidget(self.lbl_zoom_val);self.lbl_zoom_val.setFixedWidth(60);self.lbl_zoom_val.setStyleSheet('border:0;background:transparent;padding:0;')
        layout.addWidget(footer)
        layout.setStretchFactor(self.splitter,1)
        self.act_export_ppt.setShortcut(QKeySequence('Ctrl+Shift+E'))
        self.act_import_images.setShortcut(QKeySequence('Ctrl+Alt+O'))
        self.add_shortcut('保存工程',QKeySequence.Save,self.save_project_dialog)
        self.add_shortcut('打开工程',QKeySequence.Open,self.open_project_dialog)
        self.add_shortcut('查找替换',QKeySequence.Find,self.replace_dialog)
        self.add_shortcut('清除选区',QKeySequence('Escape'),self.clear_roi_current)
        self.act_del_box.setShortcuts([QKeySequence.Delete,QKeySequence('Backspace')])
        self.removeAction(self.act_del_box);self.view.addAction(self.act_del_box);self.act_del_box.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        QTimer.singleShot(0,self._fix_splitter_sizes)

    def add_shortcut(self,name,key,slot):
        a=QAction(name,self);a.setShortcut(key);a.triggered.connect(slot);self.addAction(a)

    def setup_right_panel(self):
        super().setup_right_panel()
        l=self.right_panel.layout()
        for widget in self.right_panel.findChildren(QWidget):
            if widget not in (self.text_color_preview,self.custom_color_preview):widget.setStyleSheet('')
        for lab in self.right_panel.findChildren(QLabel):
            if lab.text()=='设置对象格式':lab.setText('文字与样式');lab.setObjectName('Title');lab.setStyleSheet('font-size:16px;font-weight:600;margin-bottom:6px;')
            if lab.text()=='字体大小:':lab.setText('字号（磅）')
        self.txt_edit.setFixedHeight(145);self.txt_edit.setPlaceholderText('点击画布中的文字框，在这里修改内容。')
        row=QHBoxLayout();self.font_value=QDoubleSpinBox();self.font_value.setRange(6,600);self.font_value.setDecimals(2);self.font_value.setSingleStep(.5);self.font_value.setSuffix(' pt');self.font_value.setValue(12);self.font_value.valueChanged.connect(self.numeric_font_changed)
        row.addWidget(self.font_value);self.font_family=QComboBox();self.font_family.addItems(list(dict.fromkeys([ui_font(),'Arial','Arial Unicode MS','PingFang SC','Microsoft YaHei UI','Helvetica Neue'])));self.font_family.currentTextChanged.connect(self.family_changed);row.addWidget(self.font_family)
        at=l.indexOf(self.slider_font);l.insertLayout(at,row)
        self.wrap_check=QCheckBox('段落自动换行');self.wrap_check.toggled.connect(self.wrap_changed);l.insertWidget(l.indexOf(self.slider_font)+1,self.wrap_check)
        angle_row=QHBoxLayout();angle_row.addWidget(QLabel('文字角度'))
        self.angle_value=QDoubleSpinBox();self.angle_value.setRange(-180,180);self.angle_value.setDecimals(1);self.angle_value.setSuffix('°');self.angle_value.valueChanged.connect(self.angle_changed);angle_row.addWidget(self.angle_value);l.insertLayout(l.indexOf(self.slider_font)+1,angle_row)
        # Detailed masking/background options are available without filling the primary panel.
        self.btn_apply_style_page.hide()
        l.insertWidget(l.count()-2,self.button('合并选区文字为段落',self.merge_dialog))
        l.insertWidget(l.count()-2,self.button('删除文字框并擦除底图',self.delete_and_erase))
        l.insertWidget(l.count()-2,self.button('统一正文 / 标题 / 页脚字号',self.fonts_dialog))
        self.slider_font.setMaximum(200)
        for b in self.right_panel.findChildren(QPushButton):
            if b.text()=='删除选中框':b.setText('仅删除可编辑文字框');b.setObjectName('Danger');b.setToolTip('不会清除底图上的原字；需要同时清除时，使用上方“删除文字框并擦除底图”。')
        # Hide less-used controls as a coherent advanced section.
        start=None;advanced=[]
        for i in range(l.count()):
            widget=l.itemAt(i).widget()
            if isinstance(widget,QLabel) and widget.text()=='文本框背景色:':start=i
            if start is not None and widget is not None and i>=start:
                if isinstance(widget,QLabel) and widget.text()=='去字设置:':break
                advanced.append(widget)
        self.advanced_button=QPushButton('更多：背景覆盖与透明度');self.advanced_button.setCheckable(True)
        self.advanced_button.toggled.connect(lambda checked:[v.setVisible(checked) for v in advanced])
        if start is not None:l.insertWidget(start,self.advanced_button)
        for v in advanced:v.hide()

    def _fix_splitter_sizes(self):
        if not hasattr(self,'splitter') or len(self.splitter.sizes())!=3:return
        total=sum(self.splitter.sizes());left=195 if self._show_left_panel else 0;right=310 if self._show_right_panel else 0
        if total>left+right+200:self.splitter.setSizes([left,total-left-right,right])

    def numeric_font_changed(self,value):
        m=self._get_selected_model()
        if not m or float(m.get('font_size') or 12)==float(value):return
        self.push_undo_current_slide();m['font_size']=float(value);m['fixed_font']=True
        self.slider_font.blockSignals(True);self.slider_font.setValue(round(value));self.slider_font.blockSignals(False);self._apply_selected_style()

    def on_font_size_changed(self,value):
        super().on_font_size_changed(value)
        if hasattr(self,'font_value'):
            self.font_value.blockSignals(True);self.font_value.setValue(value);self.font_value.blockSignals(False)

    def family_changed(self,value):
        m=self._get_selected_model()
        if m and m.get('font_family')!=value:self.push_undo_current_slide();m['font_family']=value;self._apply_selected_style()

    def angle_changed(self,value):
        m=self._get_selected_model()
        if m and float(m.get('rotation',0))!=value:self.push_undo_current_slide();m['rotation']=value;self._apply_selected_style()

    def wrap_changed(self,value):
        m=self._get_selected_model()
        if m and bool(m.get('word_wrap'))!=value:
            self.push_undo_current_slide();m['word_wrap']=value;m['line_spacing']=1.45;self._apply_selected_style()

    def refresh_right_panel_from_selected(self):
        super().refresh_right_panel_from_selected();m=self._get_selected_model()
        if m:
            self.font_value.blockSignals(True);self.font_value.setValue(float(m.get('font_size') or 12));self.font_value.blockSignals(False)
            self.font_family.blockSignals(True);self.font_family.setCurrentText(m.get('font_family') or 'Arial Unicode MS');self.font_family.blockSignals(False)
            self.angle_value.blockSignals(True);self.angle_value.setValue(float(m.get('rotation',0)));self.angle_value.blockSignals(False)
            self.wrap_check.blockSignals(True);self.wrap_check.setChecked(bool(m.get('word_wrap')));self.wrap_check.blockSignals(False)

    def _enable_right_panel_widgets(self,enabled):
        super()._enable_right_panel_widgets(enabled)
        for name in ('font_value','font_family','angle_value','wrap_check'):
            if hasattr(self,name):getattr(self,name).setEnabled(enabled)

    def update_status(self):
        super().update_status()
        if hasattr(self,'canvas_stack'):self.update_workflow_status()

    def update_workflow_status(self):
        if not hasattr(self,'status_label'):return
        self.canvas_stack.setCurrentIndex(1 if self.images else 0)
        idx=self.images.index(self.current_img)+1 if self.current_img in self.images else 0
        count=len(self.box_data.get(self.current_img,[]));clean=self.current_img in self.inpaint_variants
        self.status_label.setText(f'第 {idx} / {len(self.images)} 页  ·  {count} 个文字框  ·  '+('已清除底图原字' if clean else '原始底图') if self.images else '本地处理  ·  支持 PDF / PNG / JPG / 工程文件')
        self.roi_button.setChecked(self.roi_select_mode)
        self.preview_button.setText('查看原图' if self.show_inpaint_preview else '查看去字图')
        if not self.images:message='导入文件 → 识别文字 → 清除原字 → 编辑排版 → 导出成品'
        elif not count:message='第 2 步：识别文字。Logo 漏识别时，可先框选区域再识别。'
        elif not clean:message='第 3 步：清除原字，避免修改后的文字与底图原字重叠。'
        else:message='点击文字框修改内容；框选残留可补擦，完成后保存工程或导出。'
        self.hint.setText(message)
        if self.project_path:self.document_label.setText(Path(self.project_path).name)
        if self.images:
            dirty=fingerprint(self)!=self._saved_fingerprint;self.save_label.setText('有未保存的修改  ·  每 2 分钟自动备份' if dirty else '工程已保存')
            self.setWindowTitle(APP_NAME+(' · '+Path(self.project_path).stem if self.project_path else '')+(' *' if dirty else ''))

    def _add_image_item(self,path):
        super()._add_image_item(path)
        if len(self.images)==1:self.list_thumb.setCurrentRow(0)

    def busy(self):
        return any(getattr(self,n,None) is not None and getattr(self,n).isRunning() for n in ('ocr_thread','inpaint_thread'))

    def can_operate(self):
        if self.busy():QMessageBox.information(self,APP_NAME,'正在识别或擦字，请等待当前任务完成。');return False
        return True

    def import_pdfs(self):
        if self.can_operate():super().import_pdfs();self.update_workflow_status()

    def import_images(self):
        if self.can_operate():super().import_images();self.update_workflow_status()

    def run_ocr_simulation(self,images=None):
        if not self.can_operate():return
        self.push_undo();super().run_ocr_simulation(images)

    def on_ocr_result(self,image_path,results,roi_used=None):
        for b in results:
            b.setdefault('font_family',ui_font() if language(b.get('text',''))=='zh' else 'Arial')
        super().on_ocr_result(image_path,results,roi_used)

    def save_project_dialog(self,*args,save_as=False):
        if not self.images:QMessageBox.information(self,APP_NAME,'请先导入 PDF 或图片。');return False
        if not self.can_operate():return False
        path=self.project_path if not save_as else None
        if not path:path,_=QFileDialog.getSaveFileName(self,'保存可继续编辑的工程',str(Path.home()/'Desktop'/'未命名工程.ipdfedit'),'图片PDF编辑工程 (*.ipdfedit)')
        if not path:return False
        if not path.endswith('.ipdfedit'):path+='.ipdfedit'
        try:
            save_project(self,path);self.project_path=path;self._saved_fingerprint=fingerprint(self);self.update_workflow_status();return True
        except Exception as e:QMessageBox.critical(self,'保存失败',str(e));return False

    def confirm_unsaved(self):
        if not self.images or fingerprint(self)==self._saved_fingerprint:return True
        answer=QMessageBox(self);answer.setWindowTitle('保存当前工程');answer.setText('当前内容有未保存的修改。')
        save=answer.addButton('保存工程',QMessageBox.AcceptRole);discard=answer.addButton('不保存',QMessageBox.DestructiveRole);answer.addButton('取消',QMessageBox.RejectRole);answer.exec()
        return self.save_project_dialog() if answer.clickedButton()==save else answer.clickedButton()==discard

    def open_project_dialog(self):
        if not self.can_operate():return
        path,_=QFileDialog.getOpenFileName(self,'打开工程','','图片PDF编辑工程 (*.ipdfedit)')
        if path:self.load_project_file(path)

    def load_project_file(self,path,confirm=True):
        if not self.can_operate() or (confirm and not self.confirm_unsaved()):return False
        try:m=read_project(path,self.slide_assets_dir)
        except Exception as e:QMessageBox.critical(self,'工程打开失败',str(e));return False
        self.list_thumb.blockSignals(True);self.list_thumb.clear();self.images=[];self.box_data={};self.scaled_images={};self.inpaint_variants={};self.roi_by_image={};self.current_img=None
        for p in m['pages']:
            source=p['original'];super()._add_image_item(source);self.box_data[source]=p.get('boxes',[])
            if p.get('clean'):self.inpaint_variants[source]=p['clean']
            if p.get('roi'):self.roi_by_image[source]=p['roi']
        self.show_inpaint_preview=bool(m.get('show_clean',True));self.list_thumb.blockSignals(False)
        self.undo_stack.clear();self.redo_stack.clear();self._sync_inpaint_preview_toggle()
        if self.images:self.list_thumb.setCurrentRow(min(max(0,m.get('current',0)),len(self.images)-1))
        else:self.scene.clear();self.selected_box=None
        self.project_path=str(path);self._saved_fingerprint=fingerprint(self);self.update_workflow_status();return True

    def autosave(self):
        if not self.images or self.busy():return
        sig=fingerprint(self)
        if sig==self._autosaved_fingerprint:return
        try:
            save_project(self,data_dir()/'自动备份'/'最近工程.ipdfedit');self._autosaved_fingerprint=sig
        except Exception:logging.exception('自动备份失败')

    def open_recovery(self):
        p=data_dir()/'自动备份'/'最近工程.ipdfedit'
        if p.exists():self.load_project_file(p)
        else:QMessageBox.information(self,'自动备份','编辑后每 2 分钟会保存一份备份。当前还没有备份。')

    def pages_for_scope(self,text):
        return list(self.images) if text=='全部页面' else ([self.current_img] if self.current_img else [])

    def dialog_footer(self,dialog,layout,apply_text,slot):
        row=QHBoxLayout();row.addStretch();self.button('取消',dialog.reject,row);self.button(apply_text,slot,row,primary=True);layout.addLayout(row)

    def replace_dialog(self):
        if not self.images or not self.can_operate():return
        d=QDialog(self);d.setWindowTitle('查找替换品牌 / 文案');d.resize(820,590);l=QVBoxLayout(d);l.setContentsMargins(22,20,22,20);l.setSpacing(12)
        tip=QLabel('匹配已识别的文字。照片招牌若漏识别，请框选后识别，或擦除后新增文字。');tip.setWordWrap(True);tip.setObjectName('Hint');l.addWidget(tip)
        form=QFormLayout();find=QLineEdit();find.setPlaceholderText('例如 ACME');new=QLineEdit();new.setPlaceholderText('例如 NOVA（留空可删除文字）');scope=QComboBox();scope.addItems(['全部页面','当前页']);form.addRow('查找文字',find);form.addRow('替换为',new);form.addRow('处理范围',scope);l.addLayout(form)
        sensitive=QCheckBox('区分大小写');l.addWidget(sensitive)
        erase=QCheckBox('同时清除底图中的旧文字（推荐，避免重影）');erase.setChecked(True);l.addWidget(erase)
        preserve=QCheckBox('只修改匹配文字框；其他已识别文字保留原图，不重新排版');preserve.setChecked(True);l.addWidget(preserve)
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['页码','原文字','替换后']);table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);table.setEditTriggers(QAbstractItemView.NoEditTriggers);l.addWidget(table)
        state={'matches':[],'query':None};summary=QLabel('先输入查找文字并预览匹配结果。');l.addWidget(summary)
        def preview():
            try:matches=matching_boxes(self,find.text(),new.text(),self.pages_for_scope(scope.currentText()),sensitive.isChecked())
            except ValueError as e:summary.setText(str(e));return []
            state['matches']=matches;state['query']=(find.text(),new.text(),scope.currentText(),sensitive.isChecked());table.setRowCount(len(matches))
            for i,m in enumerate(matches):
                for j,t in enumerate((str(self.images.index(m['page'])+1),m['before'],m['after'])):
                    item=QTableWidgetItem(t)
                    if j==0:item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked)
                    table.setItem(i,j,item)
            summary.setText(f'匹配 {sum(m["count"] for m in matches)} 处，涉及 {len({m["page"] for m in matches})} 页。');return matches
        self.button('预览匹配结果',preview,l)
        def apply():
            query=(find.text(),new.text(),scope.currentText(),sensitive.isChecked())
            if query!=state['query']:preview()
            matches=[m for i,m in enumerate(state['matches']) if table.item(i,0).checkState()==Qt.Checked]
            if not matches:return
            d.accept();self.replace_matches(matches,erase.isChecked(),preserve.isChecked())
        self.dialog_footer(d,l,'替换匹配项',apply);d.exec()

    def replace_matches(self,matches,erase=True,preserve_original=True):
        if not self.can_operate():return
        pages=list(dict.fromkeys(m['page'] for m in matches))
        # Snapshot fresh-page state before cleaning. Never hide text whose pixels
        # have already been removed by an earlier whole-page clean.
        fresh={p for p in self.images if p not in self.inpaint_variants}
        def commit(allowed):
            selected=[m for m in matches if m['page'] in allowed];count=apply_replacements(self,selected)
            if preserve_original and allowed:
                for p in fresh:
                    for b in self.box_data.get(p,[]):b['render_enabled']=False
                for m in selected:self.box_data[m['page']][m['index']]['render_enabled']=True
            if self.current_img:self.switch_slide(self.images.index(self.current_img))
            self.update_workflow_status();self._notify_replace_complete(count)
        if not erase:self.push_undo();commit(set(pages));return
        boxes={p:[copy.deepcopy(self.box_data[p][m['index']]) for m in matches if m['page']==p] for p in pages}
        self._clean_then(pages,boxes,lambda completed:commit(completed))

    def _notify_replace_complete(self,count):
        QMessageBox.information(self,'替换完成',f'已替换 {count} 处。请逐页检查照片招牌和漏识别文字。')

    def _clean_then(self,pages,boxes,callback,rois=None):
        if not self._ensure_inpaint_ready():return
        before=getattr(self,'inpaint_thread',None)
        original_rois=self.roi_by_image;self.roi_by_image=rois or {}
        try:self._run_inpaint(pages,run_mode=core.InpaintThread.RUN_SMART,box_data_override=boxes,input_image_by_src={p:self._get_export_image_path(p) for p in pages})
        finally:self.roi_by_image=original_rois
        thread=getattr(self,'inpaint_thread',None)
        if thread is not None and thread is not before:
            def done(canceled):
                completed={p for p,dest in getattr(self,'_inpaint_replacements',[]) if Path(dest).exists()}
                callback(completed)
            thread.all_done.connect(done,Qt.QueuedConnection)

    def fonts_dialog(self):
        if not self.images or not self.can_operate():return
        d=QDialog(self);d.setWindowTitle('按文字用途统一字号');l=QVBoxLayout(d);l.setContentsMargins(22,20,22,20);l.setSpacing(12)
        tip=QLabel('同类文字使用固定字号，不再按每行长短缩放。标题、正文和页脚可分别设置。');tip.setWordWrap(True);tip.setObjectName('Hint');l.addWidget(tip)
        form=QFormLayout();scope=QComboBox();scope.addItems(['当前页','全部页面','当前页选区内']);form.addRow('范围',scope);l.addLayout(form)
        controls={}
        for key,title,default,checked in [('zh_body','中文正文',12,True),('en_body','英文正文',9,True),('title','标题',24,False),('footer','页脚品牌',17.25,False)]:
            row=QHBoxLayout();cb=QCheckBox(title);cb.setChecked(checked);sp=QDoubleSpinBox();sp.setRange(6,600);sp.setDecimals(2);sp.setValue(default);sp.setSuffix(' pt');row.addWidget(cb);row.addStretch();row.addWidget(sp);l.addLayout(row);controls[key]=(cb,sp)
        note=QLabel('用途按文字位置和高度估计。精确处理一段正文时，先框选该段，选择“选区内”；多行正文建议先合并为段落。');note.setWordWrap(True);note.setObjectName('Subtle');l.addWidget(note)
        def apply():
            if scope.currentText()=='当前页选区内' and not self._get_current_roi():QMessageBox.information(d,'先框选区域','请先关闭对话框，框选一段正文，再操作。');return
            settings={k:sp.value() for k,(cb,sp) in controls.items() if cb.isChecked()}
            if not settings:return
            self.push_undo();n=unify_fonts(self,self.pages_for_scope(scope.currentText()),settings,scope.currentText()=='当前页选区内');self.switch_slide(self.images.index(self.current_img));d.accept();QMessageBox.information(self,'字号已统一',f'已设置 {n} 个文字框。若长文字超出，请合并为段落或扩大文字框，不会自动缩小字号。')
        self.dialog_footer(d,l,'应用统一字号',apply);d.exec()

    def merge_dialog(self):
        if not self.can_operate():return
        roi=self._get_current_roi()
        if not roi:QMessageBox.information(self,'框选段落','先用“框选区域”围住同一段文字，避免包含左右两栏，再点“合并选区为段落”。');return
        self.push_undo_current_slide()
        try:merge_region(self,self.current_img,roi);self.switch_slide(self.images.index(self.current_img));self.clear_roi_current()
        except ValueError as e:self.undo_stack.pop();QMessageBox.information(self,'合并段落',str(e))

    def erase_region_dialog(self):
        if not self.can_operate():return
        roi=self._get_current_roi()
        if not roi:QMessageBox.information(self,'先框选区域','点击“框选区域”，拖动框住残留字或 Logo，再点击“擦除选区”。');return
        self.region_dialog(False,roi)

    def batch_region_dialog(self):
        if not self.can_operate():return
        roi=self._get_current_roi()
        if not roi:QMessageBox.information(self,'先框选重复位置','先在当前页框住页脚 Logo 等重复区域，再使用批量擦除。');return
        self.region_dialog(True,roi)

    def region_dialog(self,batch,roi):
        d=QDialog(self);d.setWindowTitle('批量处理重复位置' if batch else '擦除选区');l=QVBoxLayout(d);l.setContentsMargins(22,20,22,20);l.setSpacing(12)
        hint=QLabel('使用周围画面修复选区。处理后请检查纹理；可用“撤销”恢复。');hint.setWordWrap(True);hint.setObjectName('Hint');l.addWidget(hint)
        form=QFormLayout();page_range=QLineEdit('1-'+str(len(self.images)) if batch else str(self.images.index(self.current_img)+1))
        if batch:form.addRow('页码范围（如 2-35,36）',page_range)
        new=QLineEdit();new.setPlaceholderText('留空只擦除；填写 NOVA 可添加新品牌文字');form.addRow('擦除后添加文字',new)
        method=QComboBox();method.addItems(['AI 精修（纹理 / 照片）','本地平滑修复（均匀墙面 / 门头）']);form.addRow('修复方式',method);l.addLayout(form)
        remove=QCheckBox('同时删除选区内的可编辑文字框');remove.setChecked(True);l.addWidget(remove)
        def apply():
            try:
                nums=set()
                for term in page_range.text().split(','):
                    pair=term.strip().split('-');a=int(pair[0]);b=int(pair[-1]);nums.update(range(a,b+1))
                if not nums or min(nums)<1 or max(nums)>len(self.images):raise ValueError()
            except ValueError:QMessageBox.information(d,'页码无效','请输入有效范围，例如 2-35，使用英文逗号分隔。');return
            pages=[self.images[n-1] for n in sorted(nums)];base=QImage(self.current_img);regions={}
            for p in pages:
                im=QImage(p);regions[p]=[roi[0]*im.width()/base.width(),roi[1]*im.height()/base.height(),roi[2]*im.width()/base.width(),roi[3]*im.height()/base.height()]
            d.accept();self.erase_regions(pages,regions,remove.isChecked(),new.text(),'smooth' if method.currentIndex()==1 else 'remote')
        self.dialog_footer(d,l,'处理 '+('指定页面' if batch else '当前选区'),apply);d.exec()

    def erase_regions(self,pages,regions,remove=True,new_text='',method='remote'):
        boxes={p:[dict(rect=regions[p],text='',clean_enabled=True,clean_mode=method,clean_tight=True,clean_rect=regions[p])] for p in pages}
        def commit(completed):
            for p in completed:
                roi=regions[p]
                if remove:self.box_data[p]=[b for b in self.box_data.get(p,[]) if not in_roi(b,roi)]
                if new_text:
                    x,y,w,h=roi
                    im=core._imread_any(self._get_export_image_path(p));tc=core.extract_text_color_from_region(core._imread_any(p),roi) if im is not None else [70,70,70]
                    role='footer' if y>QImage(p).height()*.83 else 'brand'
                    self.box_data.setdefault(p,[]).append(dict(rect=[x,y,w,h],text=new_text,font_family='Arial',font_size=self.fit_font_size_pt_like_ppt(new_text,w,h),text_color=tc or [70,70,70],text_color_manual=True,text_color_auto=False,bold=True,align='left',clean_enabled=False,role=role))
            if self.current_img:self.switch_slide(self.images.index(self.current_img))
            self.update_workflow_status()
        self._clean_then(pages,boxes,commit)

    def delete_and_erase(self):
        m=self._get_selected_model()
        if not m or not self.can_operate():return
        roi=list(m['rect']);self.erase_regions([self.current_img],{self.current_img:roi},True,'')

    def _ensure_inpaint_ready(self):
        return super()._ensure_inpaint_ready()

    def _run_inpaint(self,images_to_run,run_mode=core.InpaintThread.RUN_SMART,**kwargs):
        # Every touch-up starts from the latest repaired image, preserving earlier erasures.
        kwargs.setdefault('input_image_by_src',{p:self._get_export_image_path(p) for p in images_to_run})
        result=super()._run_inpaint(images_to_run,run_mode=run_mode,**kwargs)
        if kwargs.get('box_data_override') is None and getattr(self,'inpaint_thread',None):
            def activate_cleaned(path,destination):
                roi=self.inpaint_thread.roi_by_image.get(path)
                for b in self.box_data.get(path,[]):
                    if b.get('clean_enabled',True) and core.InpaintThread._intersects_roi(b.get('rect'),roi):b['render_enabled']=True
                if path==self.current_img:self.switch_slide(self.images.index(path))
            self.inpaint_thread.finished_one.connect(activate_cleaned,Qt.QueuedConnection)
        return result

    def export_preflight(self):
        if not self.images or not self.can_operate():return False
        unclean=[p for p in self.images if any(b.get('render_enabled',True) for b in self.box_data.get(p,[])) and p not in self.inpaint_variants]
        if unclean:
            d=QMessageBox(self);d.setWindowTitle('检查原字重影');d.setText(f'有 {len(unclean)} 页尚未生成去字底图，导出可能保留原字。')
            clean=d.addButton('先清除全部原字',QMessageBox.AcceptRole);export=d.addButton('仍然导出',QMessageBox.ActionRole);d.addButton('取消',QMessageBox.RejectRole);d.exec()
            if d.clickedButton()==clean:self.inpaint_all_slides();return False
            return d.clickedButton()==export
        return True

    def _prepare_boxes_for_ppt_export(self,image_path,boxes):
        return super()._prepare_boxes_for_ppt_export(image_path,[b for b in boxes if b.get('render_enabled',True)])

    def _export_ppt_to_path(self,path):
        from pptx.util import Pt
        from pptx.dml.color import RGBColor
        from pptx.oxml.xmlchemy import OxmlElement
        items=self._collect_ppt_export_items();exporter=self._build_ppt_exporter(items)
        for logical,bg,boxes in items:
            exporter.add_image_with_text_boxes(bg,boxes)
            slide=exporter.prs.slides[-1];image=QImage(bg);placement=exporter._resolve_slide_layout(image.width(),image.height());scale=placement['content_scale']
            for sh,b in zip([s for s in slide.shapes if s.has_text_frame],boxes):
                tf=sh.text_frame;tf.margin_left=tf.margin_right=tf.margin_top=tf.margin_bottom=0;tf.word_wrap=bool(b.get('word_wrap',False))
                size=float(b.get('font_size') or 12)*placement['layout_scale'];family=b.get('font_family') or 'Arial Unicode MS'
                for p in tf.paragraphs:
                    p.space_before=p.space_after=Pt(0);p.line_spacing=Pt(size*float(b.get('line_spacing',1.2)))
                    for f in [p.font]+[r.font for r in p.runs]:
                        f.size=Pt(size);f.name=family;f.bold=bool(b.get('bold'));f.color.rgb=RGBColor(*[int(v) for v in b.get('text_color',[0,0,0])])
                    for r in p.runs:
                        ea=OxmlElement('a:ea');ea.set('typeface',family);r._r.get_or_add_rPr().append(ea)
                sh.rotation=float(b.get('rotation',0))
            slide.notes_slide.notes_text_frame.text='由图片pdf文字编辑器导出。文字可编辑，背景为图片。'
        return exporter.save(path)

    def export_ppt(self):
        if not self.export_preflight():return
        path,_=QFileDialog.getSaveFileName(self,'导出可编辑 PPT','','PowerPoint (*.pptx)')
        if not path:return
        if not path.lower().endswith('.pptx'):path+='.pptx'
        try:
            if self._export_ppt_to_path(path):QMessageBox.information(self,'导出完成',f'可编辑 PPT 已保存：\n{path}')
            else:raise RuntimeError('导出未完成，请查看日志')
        except Exception as e:QMessageBox.critical(self,'导出失败',str(e))

    def export_pdf(self):
        if not self.export_preflight():return
        path,_=QFileDialog.getSaveFileName(self,'导出 PDF','','PDF (*.pdf)')
        if not path:return
        if not path.lower().endswith('.pdf'):path+='.pdf'
        try:self.export_pdf_to_path(path);QMessageBox.information(self,'导出完成',f'PDF 已保存：\n{path}')
        except Exception as e:QMessageBox.critical(self,'导出失败',str(e))

    def export_pdf_to_path(self,path):
        writer=QPdfWriter(str(path));writer.setResolution(72);writer.setTitle('图片pdf文字编辑器导出');painter=QPainter()
        for i,logical in enumerate(self.images):
            image=QImage(self._get_export_image_path(logical))
            if image.isNull():raise ValueError('无法读取页面图片')
            writer.setPageSize(QPageSize(QSizeF(image.width()*.75,image.height()*.75),QPageSize.Point))
            writer.setPageMargins(__import__('PySide6.QtCore',fromlist=['QMarginsF']).QMarginsF(0,0,0,0),QPageLayout.Point)
            if i==0:
                if not painter.begin(writer):raise ValueError('无法写入 PDF')
            else:writer.newPage()
            painter.setRenderHint(QPainter.LosslessImageRendering,True)
            painter.save();painter.scale(.75,.75);painter.drawImage(QPointF(0,0),image)
            for box in self._prepare_boxes_for_ppt_export(logical,self.box_data.get(logical,[])):
                x,y,w,h=box['rect'];painter.save();painter.translate(x,y)
                if box.get('rotation'):painter.translate(w/2,h/2);painter.rotate(float(box['rotation']));painter.translate(-w/2,-h/2)
                if box.get('use_custom_bg') and box.get('bg_color'):
                    color=QColor(*[int(v) for v in box['bg_color']]);color.setAlpha(int(box.get('bg_alpha',255)));painter.fillRect(QRectF(0,0,w,h),color)
                painter.translate(float(box.get('text_offset_x',0)),float(box.get('text_offset_y',0)))
                painter.setTransform(QTransform(float(box.get('text_scale_x',1)),float(box.get('text_shear_y',0))*float(box.get('text_scale_x',1)),0,1,0,0),True)
                doc=make_text_document(box,w/max(.01,float(box.get('text_scale_x',1))));doc.drawContents(painter,QRectF(0,0,doc.textWidth(),max(h,doc.size().height())))
                painter.restore()
            painter.restore()
        if painter.isActive():painter.end()
        return True

    def clear_repair_cache(self):
        if self.busy():return
        import shutil
        shutil.rmtree(cache_dir()/'repair-cache',ignore_errors=True)
        QMessageBox.information(self,'修复缓存','已清除修复缓存。工程和已完成的去字结果不受影响。更换修复模型后请执行一次此操作。')

    def show_guide(self):
        guide=ROOT/'docs/user-guide.zh-CN.html'
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide if guide.exists() else ROOT/'README.md')))

    def show_about(self):
        QMessageBox.information(self,APP_NAME,'ReGlyph PDF 1.2.0\nDesktop OCR · Scoped repair · Editable export\n\nDerived from Tansuo2021/OCRPDF-TO-PPT.\nAttribution: THIRD_PARTY_NOTICES.md')

    def show_shortcuts(self):
        QMessageBox.information(self,'常用快捷键','Mac 使用 ⌘，Windows 使用 Ctrl：\nS 保存工程　O 打开工程　F 查找替换\nZ 撤销　Shift+Z 重做\nDelete 删除可编辑框　Esc 清除选区\n拖动文字框移动，拖动四角调整区域。')

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():event.acceptProposedAction()

    def dropEvent(self,event):
        if not self.can_operate():return
        paths=[u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        projects=[p for p in paths if p.lower().endswith('.ipdfedit')]
        if projects:self.load_project_file(projects[0]);return
        self.import_paths(paths)

    def import_paths(self,paths):
        import fitz
        for path in paths:
            if path.lower().endswith('.pdf'):
                with fitz.open(path) as doc:
                    for i,p in enumerate(doc):
                        target=Path(self.slide_assets_dir)/f'drop-{time.time_ns()}-{i}.png';p.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).save(target);self._add_image_item(str(target))
            elif path.lower().endswith(('.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff')):self._add_image_item(path)
        self.update_workflow_status()

    def closeEvent(self,event):
        if self.busy():QMessageBox.information(self,APP_NAME,'请等待识别或擦字任务完成后退出。');event.ignore();return
        if not self._allow_close and not self.confirm_unsaved():event.ignore();return
        self.autosave_timer.stop();self._ui_timer.stop();super().closeEvent(event)


def make_text_document(box,width):
    doc=QTextDocument();doc.setDocumentMargin(0)
    font=QFont(box.get('font_family') or 'Arial Unicode MS');font.setPixelSize(max(1,round(float(box.get('font_size') or 12)/.75)));font.setBold(bool(box.get('bold')))
    doc.setDefaultFont(font);doc.setPlainText(str(box.get('text','')))
    opt=doc.defaultTextOption();opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere if box.get('word_wrap') else QTextOption.NoWrap)
    opt.setAlignment({'left':Qt.AlignLeft,'center':Qt.AlignHCenter,'right':Qt.AlignRight}.get(box.get('align'),Qt.AlignLeft));doc.setDefaultTextOption(opt);doc.setTextWidth(width)
    cursor=QTextCursor(doc);cursor.select(QTextCursor.Document);fmt=cursor.charFormat();fmt.setForeground(QColor(*[int(v) for v in box.get('text_color',[0,0,0])]));cursor.setCharFormat(fmt)
    if box.get('line_spacing'):
        bf=QTextBlockFormat();bf.setLineHeight(float(box['line_spacing'])*float(box.get('font_size') or 12)/.75,QTextBlockFormat.FixedHeight.value);cursor.mergeBlockFormat(bf)
    return doc

class Editor(PrecisionMixin,LegacyEditor):
    pass

if __name__=='__main__':
    app=QApplication(sys.argv);app.setApplicationName(APP_NAME);app.setApplicationDisplayName(APP_NAME);app.setWindowIcon(QIcon(str(ROOT/'资源/应用图标.png')));app.setStyle('Fusion')
    font=QFont(ui_font(),12);app.setFont(font)
    win=Editor();win.show()
    if len(sys.argv)>1:
        p=sys.argv[1]
        QTimer.singleShot(100,lambda:win.load_project_file(p) if p.endswith('.ipdfedit') else win.import_paths([p]))
    sys.exit(app.exec())
