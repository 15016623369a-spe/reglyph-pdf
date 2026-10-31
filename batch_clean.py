"""Conservative fast paths and bounded mask batching; never enlarge edit masks."""
import hashlib
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

def flat_background(image, mask):
    """Accept near-exact solid surrounds, rejecting gradients, edges and texture.

    Use a narrow outer ring: distant rules and neighbouring paragraphs should
    not make a solid panel require a neural-model request.
    """
    arr=np.asarray(image,dtype=np.uint8)
    base=(np.asarray(mask)>0).astype(np.uint8)
    if not base.any():return None
    outer=cv2.dilate(base,cv2.getStructuringElement(cv2.MORPH_RECT,(17,17)))>0
    inner=cv2.dilate(base,cv2.getStructuringElement(cv2.MORPH_RECT,(5,5)))>0
    ring=outer & ~inner
    pixels=arr[ring]
    if len(pixels)<96:return None
    color=np.median(pixels,axis=0)
    distance=np.max(np.abs(arr.astype(np.int16)-color.astype(np.int16)),axis=2)
    close=distance<=2
    if float(close[ring].mean())<.98:return None
    ys,xs=np.nonzero(base);cx=(xs.min()+xs.max())/2;cy=(ys.min()+ys.max())/2
    yy,xx=np.indices(base.shape)
    for part in (xx<=cx,xx>cx,yy<=cy,yy>cy):
        sample=ring & part
        if sample.sum()<16 or float(close[sample].mean())<.95:return None
    return tuple(int(v) for v in color)

def merge_remote_tasks(tasks, image_size, padding):
    """Merge nearby inference crops, retaining the exact union of edit masks.

    Bounded size and area prevent a long chain of OCR boxes from turning into
    expensive whole-page inference. Explicit modes and blur settings stay apart.
    """
    width,height=image_size
    def bounds(mask):
        x0,y0,x1,y1=mask.getbbox()
        return (max(0,x0-padding),max(0,y0-padding),min(width,x1+padding),min(height,y1+padding))
    def area(r):return (r[2]-r[0])*(r[3]-r[1])
    groups=[]
    for task in tasks:
        task=dict(task);task['members']=[task['index']]
        rect=bounds(task['mask']);best=None
        for i,(other,old) in enumerate(groups):
            if other['analysis'].get('requested_mode')!=task['analysis'].get('requested_mode'):continue
            if other.get('composite_blur')!=task.get('composite_blur'):continue
            union=(min(rect[0],old[0]),min(rect[1],old[1]),max(rect[2],old[2]),max(rect[3],old[3]))
            if union[2]-union[0]>896 or union[3]-union[1]>640:continue
            # Context rectangles must overlap substantially; do not bridge columns.
            overlap=max(0,min(rect[2],old[2])-max(rect[0],old[0]))*max(0,min(rect[3],old[3])-max(rect[1],old[1]))
            if overlap<.15*min(area(rect),area(old)):continue
            if area(union)>1.15*(area(rect)+area(old)):continue
            score=area(union)-area(old)
            if best is None or score<best[0]:best=(score,i,union)
        if best is None:groups.append((task,rect));continue
        _,i,union=best;other,_=groups[i]
        other['mask']=Image.fromarray(np.maximum(np.asarray(other['mask']),np.asarray(task['mask'])))
        other['boxes']=other['boxes']+task['boxes']
        other['members']+=task['members']
        other['remote_required']=other.get('remote_required',False) or task.get('remote_required',False)
        groups[i]=(other,union)
    return [task for task,_ in groups]

def cache_key(url,image,mask):
    digest=hashlib.sha256(b'ipdf-inpaint-v1\0'+str(url).encode())
    digest.update(str(image.size).encode());digest.update(image.tobytes());digest.update(mask.tobytes())
    return digest.hexdigest()

def load_cached(folder,key,size):
    path=Path(folder)/(key+'.png')
    try:
        with Image.open(path) as im:
            if im.size==size:return im.convert('RGB')
    except (OSError,ValueError):pass
    return None

def save_cached(folder,key,image):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    import os,tempfile
    fd,name=tempfile.mkstemp(prefix='.repair-',suffix='.png',dir=folder);os.close(fd)
    try:image.save(name,'PNG');os.replace(name,folder/(key+'.png'))
    finally:Path(name).unlink(missing_ok=True)
    # Bound the persistent cache. Eviction affects speed only, never documents.
    entries=sorted(folder.glob('*.png'),key=lambda p:p.stat().st_mtime,reverse=True)
    total=0
    for i,path in enumerate(entries):
        total+=path.stat().st_size
        if i>=256 or total>256*1024**2:path.unlink(missing_ok=True)
