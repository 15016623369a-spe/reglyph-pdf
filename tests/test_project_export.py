"""Portable project and real PDF/PPTX export regression using synthetic assets."""
import copy,json,os,sys,tempfile,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
TMP=Path(tempfile.mkdtemp(prefix='reglyph-export-'))
os.environ.update(QT_QPA_PLATFORM='offscreen',IPDF_DATA_DIR=str(TMP/'data'),PYTHONDONTWRITEBYTECODE='1')
from editor import Editor,QApplication,QFont,QMessageBox,ui_font,save_project
from exact_edit import plan_replace
from PIL import Image,ImageDraw
import numpy as np
import pymupdf
from pptx import Presentation

app=QApplication([]);app.setStyle('Fusion');app.setFont(QFont(ui_font(),12))
messages=[]
for method in ['information','warning','critical']:setattr(QMessageBox,method,lambda *a,**kw:messages.append(str(a[1:3])))
win=Editor();win._ensure_inpaint_ready=lambda:True;win.show()
for index in range(2):
 image=Image.new('RGB',(800,450),'white');draw=ImageDraw.Draw(image)
 draw.text((50,50),'ACME',fill='black');draw.text((50,200),'KEEP ORIGINAL',fill='black')
 source=TMP/f'synthetic-{index}.png';image.save(source);win._add_image_item(str(source))
 win.box_data[str(source)]=[
  dict(text='ACME',rect=[45,45,110,36],confidence=1.,clean_mode='fill',font_family='Arial',font_size=18.,text_color=[25,40,60]),
  dict(text='KEEP ORIGINAL',rect=[45,195,180,36],confidence=1.,font_family='Arial',font_size=16.,render_enabled=False)]
win.switch_slide(0);app.processEvents()
paths={p:win._get_export_image_path(p) for p in win.images};plan=plan_replace(win._contract_document(paths),'ACME','NOVA')
assert len(plan.edits)==2
matches=[dict(page=win.images[e.page],index=int(e.box_id),before=e.before,after=e.after,count=1) for e in plan.edits]
win._active_exact_contract=(plan,paths)
win.replace_matches(matches,erase=True,preserve_original=True);win._active_exact_contract=None
start=time.monotonic()
while win.busy():
 app.processEvents();time.sleep(.01)
 if time.monotonic()-start>30:raise TimeoutError('repair fixture timed out')
for _ in range(10):app.processEvents();time.sleep(.01)
assert len(win.inpaint_variants)==2,messages
assert all(win.box_data[p][0]['text']=='NOVA' for p in win.images),messages
for p in win.images:
 original=np.array(Image.open(p));clean=np.array(Image.open(win.inpaint_variants[p]));assert np.array_equal(original[180:250],clean[180:250])
win.export_pdf_to_path(str(TMP/'synthetic.pdf'))
assert win._export_ppt_to_path(str(TMP/'synthetic.pptx'))
pdf=pymupdf.open(TMP/'synthetic.pdf');presentation=Presentation(TMP/'synthetic.pptx')
assert len(pdf)==len(presentation.slides)==2
assert sum(page.get_text().count('NOVA') for page in pdf)==2
assert 'ACME' not in ''.join(page.get_text() for page in pdf)
assert sum(shape.text.count('NOVA') for slide in presentation.slides for shape in slide.shapes if shape.has_text_frame)==2
expected=copy.deepcopy([win.box_data[p] for p in win.images]);project=TMP/'synthetic.ipdfedit';save_project(win,project)
original_paths=list(win.images);win._allow_close=True;win.close();app.processEvents()
for source in original_paths:Path(source).unlink()
reopened=Editor();reopened.show();app.processEvents();assert reopened.load_project_file(str(project),confirm=False)
assert [reopened.box_data[p] for p in reopened.images]==expected
assert all(Path(reopened.inpaint_variants[p]).is_file() for p in reopened.images)
malformed=TMP/'malformed.ipdfedit'
with zipfile.ZipFile(malformed,'w') as archive:
 archive.writestr('project.json',json.dumps(dict(format='image-pdf-editor',version=1,pages=[dict(original='../escape.png',boxes=[])])))
previous=list(reopened.images);assert not reopened.load_project_file(str(malformed),confirm=False);assert reopened.images==previous
reopened._allow_close=True;reopened.close();app.processEvents()
print('PASS scoped replacement, unrelated content, native PDF/PPTX text, asset-backed project roundtrip, malformed-project recovery')
