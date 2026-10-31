"""Portable project storage and document operations for the desktop editor."""
from pathlib import Path
import copy,hashlib,json,math,os,re,shutil,tempfile,zipfile
from PIL import Image

APP_NAME='ReGlyph PDF'
FORMAT_VERSION=1

def json_value(value):
    if hasattr(value,'tolist'):return value.tolist()
    if isinstance(value,Path):return str(value)
    raise TypeError(f'无法保存此数据类型：{type(value).__name__}')

def serialise(value):
    return json.dumps(value,ensure_ascii=False,default=json_value,allow_nan=False)

def fingerprint(win):
    data=[(p,win.box_data.get(p,[]),win.inpaint_variants.get(p),win.roi_by_image.get(p)) for p in win.images]
    return hashlib.sha256(serialise(data).encode()).hexdigest()

def save_project(win,path):
    """Archive originals, cleaned versions and editable fields with atomic replacement."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    pages=[]
    fd,tmp=tempfile.mkstemp(prefix='.saving-',suffix='.ipdfedit',dir=path.parent);os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED) as z:
            for i,source in enumerate(win.images):
                suffix=Path(source).suffix.lower() or '.png';orig=f'pages/{i:04d}/original{suffix}'
                z.write(source,orig)
                item=dict(original=orig,boxes=copy.deepcopy(win.box_data.get(source,[])),roi=win.roi_by_image.get(source),name=Path(source).name)
                clean=win.inpaint_variants.get(source)
                if clean and Path(clean).is_file():
                    item['clean']=f'pages/{i:04d}/clean{Path(clean).suffix.lower()}';z.write(clean,item['clean'])
                pages.append(item)
            manifest=dict(format='image-pdf-editor',version=FORMAT_VERSION,pages=pages,current=max(0,win.list_thumb.currentRow()),show_clean=win.show_inpaint_preview)
            z.writestr('project.json',serialise(manifest))
        os.replace(tmp,path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True);raise
    return path

def read_project(path,destination):
    """Validate before replacing the active document; never extract arbitrary archive paths."""
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='opened-',dir=dest))
    try:
        with zipfile.ZipFile(path) as z:
            m=json.loads(z.read('project.json'))
            if m.get('format')!='image-pdf-editor' or m.get('version')!=FORMAT_VERSION:raise ValueError('不支持的工程文件格式')
            pages=m.get('pages',[])
            if not isinstance(pages,list) or len(pages)>2000:raise ValueError('工程页数无效')
            total=0
            for i,p in enumerate(pages):
                if not isinstance(p.get('boxes',[]),list):raise ValueError('文字数据损坏')
                for b in p.get('boxes',[]):
                    if not isinstance(b,dict) or not isinstance(b.get('rect'),(tuple,list)) or len(b['rect'])!=4:raise ValueError('文字位置数据损坏')
                    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in b['rect']):raise ValueError('文字位置无效')
                    if b['rect'][2]<=0 or b['rect'][3]<=0:raise ValueError('文字框宽高无效')
                for key in ('original','clean'):
                    if key not in p:continue
                    member=p[key]
                    if not isinstance(member,str) or not member.startswith(f'pages/{i:04d}/') or '..' in Path(member).parts:raise ValueError('工程中的图片路径无效')
                    info=z.getinfo(member);total+=info.file_size
                    if info.file_size>500*1024**2 or total>8*1024**3:raise ValueError('工程图片超过可处理的大小')
                    target=folder/f'{i:04d}-{key}{Path(member).suffix}'
                    with z.open(member) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
                    with Image.open(target) as im:im.verify()
                    p[key]=str(target)
        return m
    except BaseException:
        shutil.rmtree(folder,ignore_errors=True);raise

def in_roi(box,roi):
    if not roi:return True
    x,y,w,h=box['rect'];rx,ry,rw,rh=roi
    return rx<=x+w/2<=rx+rw and ry<=y+h/2<=ry+rh

def language(text):return 'zh' if re.search('[\u3400-\u9fff]',str(text)) else 'en'

def classify(box,image_height):
    if box.get('role'):return box['role']
    text=str(box.get('text',''));x,y,w,h=box['rect']
    if y>image_height*.83:
        if re.search(r'EST[.,\s]*19|LUXURY|FULL.PROJECT|CUSTOMIZATION',text,re.I):return 'footer_meta'
        if len(text.strip())<=16 and not re.search(r'[。，；：！？.!?]$',text.strip()):return 'footer'
    if h>image_height*.06 and re.fullmatch(r'[A-Za-z|ⅠⅡ ]{2,16}',text.strip()):return 'brand'
    if h>=image_height*.035 or (len(text.strip())<45 and h>=image_height*.027):return 'title'
    return language(text)+'_body'

def matching_boxes(win,old,new,pages=None,case_sensitive=False):
    if not old:raise ValueError('请先输入要查找的文字')
    pattern=re.compile(re.escape(old),0 if case_sensitive else re.I);matches=[]
    for p in (win.images if pages is None else pages):
        for i,b in enumerate(win.box_data.get(p,[])):
            before=str(b.get('text',''));after,n=pattern.subn(lambda _:new,before)
            if n:matches.append(dict(page=p,index=i,before=before,after=after,count=n))
    return matches

def apply_replacements(win,matches):
    applied=0
    for m in matches:
        boxes=win.box_data.get(m['page'],[])
        if m['index']<len(boxes) and str(boxes[m['index']].get('text',''))==m['before']:
            boxes[m['index']]['text']=m['after'];applied+=m['count']
    return applied

def unify_fonts(win,pages,settings,roi_only=False):
    changed=0
    for path in pages:
        with Image.open(path) as im:height=im.height
        for b in win.box_data.get(path,[]):
            if roi_only and not in_roi(b,win.roi_by_image.get(path)):continue
            role=classify(b,height)
            if role not in settings:continue
            size=float(settings[role]);b.update(font_size=size,font_family='Arial Unicode MS' if language(b.get('text',''))=='zh' else 'Arial',role=role,fixed_font=True)
            if b.get('word_wrap'):b['line_spacing']=1.45
            changed+=1
    return changed

def merge_region(win,path,roi):
    boxes=win.box_data.get(path,[]);selected=[b for b in boxes if in_roi(b,roi)]
    if len(selected)<2:raise ValueError('请框选同一段落中的至少两行文字')
    selected.sort(key=lambda b:(b['rect'][1],b['rect'][0]))
    x=min(b['rect'][0] for b in selected);y=min(b['rect'][1] for b in selected)
    right=max(b['rect'][0]+b['rect'][2] for b in selected);bottom=max(b['rect'][1]+b['rect'][3] for b in selected)
    zh=language(''.join(str(b.get('text','')) for b in selected))=='zh';parts=[]
    last=None
    for b in selected:
        if last:
            gap=b['rect'][1]-(last['rect'][1]+last['rect'][3]);parts.append('\n\n' if gap>max(last['rect'][3],b['rect'][3])*.9 else ('' if zh else ' '))
        parts.append(str(b.get('text','')).strip());last=b
    model=copy.deepcopy(selected[0]);model.update(render_enabled=True,text=''.join(parts),rect=[x,y,max(right-x,roi[2]),max(bottom-y,roi[3])],word_wrap=True,line_spacing=1.45,role='zh_body' if zh else 'en_body',font_size=12 if zh else 9,font_family='Arial Unicode MS' if zh else 'Arial',source_rects=[b['rect'] for b in selected])
    for k in ('bbox','polygon'):model.pop(k,None)
    ids={id(b) for b in selected};win.box_data[path]=[b for b in boxes if id(b) not in ids]+[model]
    return model
