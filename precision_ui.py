"""Strict matching, immutable previews and atomic background/text transactions."""
from pathlib import Path
from dataclasses import replace
import copy,hashlib,math,json
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QFormLayout,QLineEdit,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox
from platform_config import data_dir
from exact_edit import plan_replace,validate_plan,digest,ContractError,apply_text_edits

class PrecisionMixin:
    def _write_exact_audit(self,plan,count,erased):
        import datetime,os,tempfile
        now=datetime.datetime.now().astimezone()
        folder=data_dir()/'操作记录';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(now.strftime('%Y%m%d-%H%M%S-%f')+'.json')
        record=dict(time=now.isoformat(),status='committed',plan_id=plan.id,replacements=count,
                    pending_review=len(plan.review),background_checked=bool(erased),
                    outside_region_changed_pixels=0 if erased else None,text_and_layout_check='passed',plan=plan.to_dict())
        fd,name=tempfile.mkstemp(prefix='.audit-',suffix='.json',dir=folder)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
            os.replace(name,path)
        finally:Path(name).unlink(missing_ok=True)
        return path

    def _show_exact_success(self,plan,count,path):
        self._last_exact_audit=str(path)
        QMessageBox.information(self,'严格替换完成',f'已替换 {count} 处；待核对 {len(plan.review)} 处保持原样。\n本次修改通过范围校验，操作记录已保存。\n{path}')

    def _notify_replace_complete(self,count):
        if getattr(self,'_hold_completion_notice',False):self._pending_replace_count=count
        else:super()._notify_replace_complete(count)

    def replace_matches(self,matches,erase=True,preserve_original=True):
        contract=getattr(self,'_active_exact_contract',None)
        if erase or not contract:return super().replace_matches(matches,erase,preserve_original)
        plan,paths=contract;doc=self._contract_document(paths)
        expected=apply_text_edits(doc,plan,approved_plan_id=plan.id)
        snapshot=(copy.deepcopy(self.box_data),list(self.undo_stack),list(self.redo_stack))
        self._hold_completion_notice=True;self._pending_replace_count=None
        try:
            super().replace_matches(matches,erase,preserve_original)
            if self._contract_document(paths)!=expected:raise ContractError('文字或排版变化超出预览计划')
            audit_path=self._write_exact_audit(plan,self._pending_replace_count,False)
        except Exception as e:
            self.box_data,self.undo_stack,self.redo_stack=snapshot
            if self.current_img:self.switch_slide(self.images.index(self.current_img))
            QMessageBox.warning(self,'本次修改未提交',str(e));self._pending_replace_count=None
        finally:self._hold_completion_notice=False
        if self._pending_replace_count is not None:self._show_exact_success(plan,self._pending_replace_count,audit_path)

    def _contract_document(self,paths=None):
        pages=[]
        for source in self.images:
            path=(paths or {}).get(source) or self._get_export_image_path(source)
            with Image.open(path) as im:size=list(im.size)
            boxes=[]
            for i,b in enumerate(self.box_data.get(source,[])):
                region=b.get('clean_rect',b['rect']) if b.get('clean_tight') else b['rect']
                region=[float(v) for v in region]
                poly=b.get('clean_polygon')
                if poly:
                    xs=[float(pt[0]) for pt in poly];ys=[float(pt[1]) for pt in poly]
                    left=min(region[0],min(xs));top=min(region[1],min(ys));right=max(region[0]+region[2],max(xs)+1);bottom=max(region[1]+region[3],max(ys)+1)
                    region=[left,top,right-left,bottom-top]
                x,y,w,h=region;left,top=math.floor(x),math.floor(y)
                region=[left,top,math.ceil(x+w)-left,math.ceil(y+h)-top]
                # Whitelist layout fields so derived UI bookkeeping cannot invalidate a plan.
                layout={k:b.get(k) for k in ['rect','font_family','font_size','bold','rotation','text_scale_x','text_shear_y','text_offset_x','text_offset_y','clean_rect','clean_polygon','clean_mode','text_color','use_custom_bg','bg_color','bg_alpha','align','word_wrap','line_spacing','fixed_font','text_color_manual','text_color_auto']}
                boxes.append(dict(id=str(i),text=str(b.get('text','')),rect=region,layout=layout,
                    confidence=float(b['confidence']) if b.get('confidence') is not None else None,
                    human_verified=bool(b.get('human_verified') or ('audit_index' in b and 'audit_kind' in b))))
            pages.append(dict(size=size,pixel_digest=hashlib.sha256(Path(path).read_bytes()).hexdigest(),boxes=boxes))
        return dict(pages=pages)

    def replace_dialog(self):
        if not self.images or not self.can_operate():return
        d=QDialog(self);d.setWindowTitle('精确查找替换');d.resize(900,640);l=QVBoxLayout(d);l.setContentsMargins(22,20,22,20);l.setSpacing(12)
        tip=QLabel('严格模式只自动替换独立、清晰的文字框。品牌混在整行正文中，或识别不确定时，列为待核对，避免多擦其他文字。');tip.setWordWrap(True);l.addWidget(tip)
        form=QFormLayout();find=QLineEdit();find.setPlaceholderText('例如 ACME');new=QLineEdit();new.setPlaceholderText('例如 NOVA（留空可删除文字）');scope=QComboBox();scope.addItems(['全部页面','当前页']);form.addRow('查找文字',find);form.addRow('替换为',new);form.addRow('处理范围',scope);l.addLayout(form)
        strict=QCheckBox('严格定位：不猜测单词位置，不自动重绘混合正文');strict.setChecked(True);l.addWidget(strict)
        sensitive=QCheckBox('区分大小写');l.addWidget(sensitive)
        erase=QCheckBox('同时清除底图中的旧文字');erase.setChecked(True);l.addWidget(erase)
        preserve=QCheckBox('保留其他原版内容，不重新排版');preserve.setChecked(True);l.addWidget(preserve)
        table=QTableWidget(0,4);table.setHorizontalHeaderLabels(['页码','原文字','替换后','处理说明']);table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch);table.setEditTriggers(QAbstractItemView.NoEditTriggers);l.addWidget(table)
        state={};summary=QLabel('输入内容后预览修改计划。');summary.setWordWrap(True);l.addWidget(summary)
        def query():return find.text(),new.text(),scope.currentText(),sensitive.isChecked(),strict.isChecked()
        def preview():
            try:
                if not find.text():raise ValueError('请先输入要查找的文字')
                paths={p:self._get_export_image_path(p) for p in self.images}
                doc=self._contract_document(paths)
                pages=[self.images.index(p) for p in self.pages_for_scope(scope.currentText())]
                if strict.isChecked():
                    plan=plan_replace(doc,find.text(),new.text(),pages=pages,case_sensitive=sensitive.isChecked())
                    matches=[dict(page=self.images[e.page],index=int(e.box_id),before=e.before,after=e.after,count=1,edit=e) for e in plan.edits]
                    blocked=[(v.page,v.box_id,v.reason) for v in plan.review]
                else:
                    from workflow import matching_boxes
                    plan=None;matches=matching_boxes(self,find.text(),new.text(),self.pages_for_scope(scope.currentText()),sensitive.isChecked());blocked=[]
                table.setRowCount(len(matches)+len(blocked))
                for i,m in enumerate(matches):
                    values=[str(self.images.index(m['page'])+1),m['before'],m['after'],'精确匹配' if strict.isChecked() else '普通模式：可能重绘整行']
                    for j,text in enumerate(values):
                        item=QTableWidgetItem(text)
                        if j==0:item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked)
                        table.setItem(i,j,item)
                for i,(p,key,reason) in enumerate(blocked,len(matches)):
                    text=doc['pages'][p]['boxes'][int(key)]['text']
                    for j,value in enumerate([str(p+1),text,'不自动修改',reason]):table.setItem(i,j,QTableWidgetItem(value))
                state.update(query=query(),doc=doc,paths=paths,plan=plan,matches=matches)
                summary.setText(f'可执行 {len(matches)} 项；待核对 {len(blocked)} 项。只执行勾选项；待核对项保持原样。')
            except (ValueError,TypeError,KeyError) as e:state.clear();table.setRowCount(0);summary.setText(str(e))
        self.button('预览匹配结果',preview,l)
        def apply():
            if query()!=state.get('query'):preview()
            if not state:return
            selected=[m for i,m in enumerate(state['matches']) if table.item(i,0).checkState()==Qt.Checked]
            if not selected:return
            plan=state['plan']
            if plan is not None:
                try:
                    plan=replace(plan,edits=tuple(m['edit'] for m in selected));validate_plan(self._contract_document(state['paths']),plan)
                except (ContractError,ValueError) as e:summary.setText(str(e));return
                self._active_exact_contract=(plan,state['paths'])
            d.accept()
            try:self.replace_matches(selected,erase.isChecked(),preserve.isChecked())
            finally:
                # The asynchronous transaction captures its contract before returning.
                self._active_exact_contract=None
        self.dialog_footer(d,l,'替换匹配项',apply);d.exec()

    def _clean_then(self,pages,boxes,callback,rois=None):
        # All-or-nothing: failed/cancelled pages must not leave a half-applied document.
        snapshot=(copy.deepcopy(self.box_data),dict(self.inpaint_variants),self.show_inpaint_preview,list(self.undo_stack),list(self.redo_stack))
        contract=getattr(self,'_active_exact_contract',None)
        failures=[]
        if contract:
            plan,paths=contract;validate_plan(self._contract_document(paths),plan)
            original_doc=self._contract_document(paths)
            expected_doc=apply_text_edits(original_doc,plan,approved_plan_id=plan.id)
            # Match snapshots retain the original indexes via the selected operation order.
            for p in pages:
                edits=[e for e in plan.edits if self.images[e.page]==p]
                for box,e in zip(boxes[p],edits):box.update(clean_tight=True,clean_rect=list(e.region))
        self._hold_completion_notice=True;self._pending_replace_count=None
        before=getattr(self,'inpaint_thread',None)
        def rollback(reason):
            self.box_data,self.inpaint_variants,self.show_inpaint_preview,self.undo_stack,self.redo_stack=snapshot
            self._hold_completion_notice=False;self._pending_replace_count=None
            self._inpaint_replacements=[];self._refresh_thumb_images();self._sync_inpaint_preview_toggle()
            if self.current_img:self.switch_slide(self.images.index(self.current_img))
            QMessageBox.warning(self,'本次修改未提交',reason+'\n已恢复到操作前的文字和底图。')
        def finish(completed):
            thread=self.inpaint_thread
            if failures or thread.isInterruptionRequested() or set(completed)!=set(pages):
                rollback('任务失败或被取消，不会保留部分替换结果。');return
            try:
                if contract:
                    validate_plan(self._contract_document(contract[1]),contract[0])
                    # Independently check the complete output, including local repair paths.
                    for p in pages:
                        original=np.array(Image.open(paths[p]).convert('RGB'))
                        result=np.array(Image.open(self.inpaint_variants[p]).convert('RGB'))
                        if original.shape!=result.shape:raise ContractError('输出尺寸改变，已拒绝提交')
                        mask=np.zeros(original.shape[:2],dtype=bool)
                        for e in plan.edits:
                            if self.images[e.page]!=p:continue
                            x,y,w,h=map(int,e.region);mask[y:y+h,x:x+w]=True
                        if not np.array_equal(original[~mask],result[~mask]):raise ContractError('检测到指定区域之外的像素变化，已拒绝提交')
                callback(completed)
                if contract:
                    actual=self._contract_document(paths)
                    if actual!=expected_doc:raise ContractError('文字或排版变化超出预览计划，已拒绝提交')
                audit_path=self._write_exact_audit(plan,self._pending_replace_count,True) if contract else None
                self._hold_completion_notice=False
                if self._pending_replace_count is not None:
                    if contract:self._show_exact_success(plan,self._pending_replace_count,audit_path)
                    else:super(PrecisionMixin,self)._notify_replace_complete(self._pending_replace_count)
            except Exception as e:rollback(str(e))
        result=super()._clean_then(pages,boxes,finish,rois)
        thread=getattr(self,'inpaint_thread',None)
        if thread is not None and thread is not before:thread.error.connect(failures.append,Qt.QueuedConnection)
        else:self._hold_completion_notice=False
        return result
