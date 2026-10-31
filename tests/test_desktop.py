"""Actual Qt dialog + transaction integration, offline repair fixtures."""
import os,sys,time,copy,json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'app' if (ROOT/'app').exists() else ROOT.parent))
TMP=Path(tempfile.mkdtemp(prefix='precision-desktop-'))
os.environ.update(QT_QPA_PLATFORM='offscreen',IPDF_DATA_DIR=str(TMP/'data'),PYTHONDONTWRITEBYTECODE='1')
from editor import *
import numpy as np
TEST_ROOT=Path(__file__).resolve().parent
from PySide6.QtTest import QTest
from PIL import ImageDraw
from exact_edit import plan_replace
app=QApplication([]);app.setStyle('Fusion');app.setFont(QFont(ui_font(),12))
messages=[]
for name in ['information','warning','critical']:setattr(QMessageBox,name,lambda *args,**kw:messages.append(str(args[1:3])))

def settle(win):
 start=time.monotonic()
 while win.busy():
  app.processEvents();time.sleep(.01)
  if time.monotonic()-start>40:raise TimeoutError('test timed out')
 for _ in range(8):app.processEvents();time.sleep(.01)

def window(count=1):
 win=Editor();win._ensure_inpaint_ready=lambda:True;win.show()
 for i in range(count):
  path=TMP/f'page-{len(list(TMP.glob("page-*")))}.png';im=Image.new('RGB',(600,320),'white');draw=ImageDraw.Draw(im)
  draw.text((50,50),'ACME',fill='black');draw.text((300,50),'ACME',fill='black');draw.text((50,200),'OTHER',fill='black');im.save(path)
  win._add_image_item(str(path));p=win.images[-1]
  win.box_data[p]=[dict(text='ACME',rect=[45,45,75,30],confidence=.99,clean_mode='fill',font_size=14,font_family='Arial'),dict(text='ACME',rect=[295,45,75,30],confidence=.99,clean_mode='fill',font_size=14,font_family='Arial'),dict(text='OTHER',rect=[45,195,75,30],confidence=.99,font_size=14,font_family='Arial')]
 win.switch_slide(0);app.processEvents();return win

def close(win):win._allow_close=True;win.close();app.processEvents()

def dialog(win,expected,select=None,scope=None):
 errors=[]
 def drive():
  d=app.activeModalWidget()
  try:
   assert isinstance(d,QDialog)
   next(e for e in d.findChildren(QLineEdit) if e.placeholderText()=='例如 ACME').setText('ACME')
   next(e for e in d.findChildren(QLineEdit) if '例如 NOVA' in e.placeholderText()).setText('NOVA')
   if scope:d.findChild(QComboBox).setCurrentText(scope)
   next(b for b in d.findChildren(QPushButton) if b.text()=='预览匹配结果').click()
   table=d.findChild(QTableWidget);assert table.rowCount()==expected,(table.rowCount(),[l.text() for l in d.findChildren(QLabel)])
   if select is False:d.reject();return
   if select is not None:
    for i in range(table.rowCount()):
     if table.item(i,0).flags()&Qt.ItemIsUserCheckable:table.item(i,0).setCheckState(Qt.Checked if i in select else Qt.Unchecked)
   next(b for b in d.findChildren(QPushButton) if b.text()=='替换匹配项').click()
  except BaseException as e:errors.append(e);d.reject()
 QTimer.singleShot(50,drive);win.replace_dialog()
 if errors:raise errors[0]
 settle(win)

# Preview: partial OCR line and low confidence stay unchanged.
win=window();p=win.images[0]
win.box_data[p].extend([dict(text='ACME factory',rect=[45,100,200,24],confidence=.99),dict(text='ACME',rect=[300,100,75,24],confidence=.5)])
before=copy.deepcopy(win.box_data);dialog(win,4,select=[0])
assert [b['text'] for b in win.box_data[p]]==['NOVA','ACME','OTHER','ACME factory','ACME'],messages
assert win.box_data[p][0]['font_size']==before[p][0]['font_size']
report=json.loads(Path(win._last_exact_audit).read_text());assert report['pending_review']==2 and report['outside_region_changed_pixels']==0 and report['replacements']==1
a=np.array(Image.open(p));b=np.array(Image.open(win.inpaint_variants[p]));mask=np.zeros(a.shape[:2],bool);mask[45:75,45:120]=True;assert np.array_equal(a[~mask],b[~mask])
win.undo();assert win.box_data[p]==before[p] and not win.inpaint_variants
win.redo();assert win.box_data[p][0]['text']=='NOVA';close(win)
print('PASS real dialog: strict defaults, partial/uncertain review, selected subset, exact outside pixels, font preservation, undo/redo',flush=True)
# Mid-batch failure must roll back page one, text, undo/redo.
original_save=core.InpaintThread._save_result_image
for cancel in [False,True]:
 win=window(2);before=copy.deepcopy(win.box_data)
 for _ in range(50):win.push_undo()
 original_history=list(win.undo_stack);history=(len(win.undo_stack),len(win.redo_stack));calls=[]
 def controlled(self,source,image):
  calls.append(source)
  if len(calls)==2:
   if cancel:raise InterruptedError('cancel test')
   raise RuntimeError('injected page two failure')
  return original_save(self,source,image)
 core.InpaintThread._save_result_image=controlled
 try:dialog(win,4)
 finally:core.InpaintThread._save_result_image=original_save
 assert len(calls)==2
 assert win.box_data==before and not win.inpaint_variants,(win.box_data,messages)
 assert (len(win.undo_stack),len(win.redo_stack))==history
 assert all(a is b for a,b in zip(win.undo_stack,original_history))
 close(win)
 print('PASS whole-batch rollback after '+('cancellation' if cancel else 'page-two failure'),flush=True)
# Independent output audit must catch even a buggy local writer.
win=window();before=copy.deepcopy(win.box_data)
def corrupt(self,source,image):image.putpixel((590,310),(0,0,0));return original_save(self,source,image)
core.InpaintThread._save_result_image=corrupt
try:dialog(win,2)
finally:core.InpaintThread._save_result_image=original_save
assert win.box_data==before and not win.inpaint_variants,messages;close(win)
print('PASS output pixel audit rejects unexpected edits and restores original',flush=True)
# Scope must remain on the current page.
win=window(2);dialog(win,2,scope='当前页');assert all(b['text']!='ACME' for b in win.box_data[win.images[0]][:2]);assert win.box_data[win.images[1]][0]['text']=='ACME';close(win)
print('PASS current-page scope',flush=True)
(TMP/'desktop-test-result.json').write_text(json.dumps(dict(strict_dialog=True,review_ambiguous=True,subset=True,preserve_style=True,outside_pixels_unchanged=True,undo_redo=True,failure_atomic=True,cancel_atomic=True,detect_buggy_writer=True,current_page_scope=True),indent=2))
print('ALL DESKTOP INTEGRATION TESTS PASS',flush=True)
