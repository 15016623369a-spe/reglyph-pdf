"""Platform-neutral edit contracts. No GUI, network, OCR or model side effects."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Mapping, Sequence
import hashlib,json,math,re

class ContractError(ValueError):pass

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()

def rect(value):
    if not isinstance(value,(list,tuple)) or len(value)!=4:raise ContractError('区域必须包含四个坐标')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in value):raise ContractError('区域坐标无效')
    x,y,w,h=map(float,value)
    if x<0 or y<0 or w<=0 or h<=0:raise ContractError('区域宽高或位置无效')
    return (x,y,w,h)

def contained(inner,outer):
    x,y,w,h=inner;a,b,c,d=outer
    return x>=a and y>=b and x+w<=a+c and y+h<=b+d

@dataclass(frozen=True)
class Edit:
    page:int
    box_id:str
    before:str
    after:str
    region:tuple[float,float,float,float]
    box_digest:str
    # Character offsets allow precise substring updates, while preserving other text.
    start:int
    end:int

@dataclass(frozen=True)
class ReviewItem:
    page:int
    box_id:str
    reason:str

@dataclass(frozen=True)
class Plan:
    version:int
    document_digest:str
    request:dict
    edits:tuple[Edit,...]
    review:tuple[ReviewItem,...]

    def to_dict(self):return asdict(self)
    @property
    def id(self):return digest(self.to_dict())

def validate_document(doc):
    if not isinstance(doc,Mapping) or not isinstance(doc.get('pages'),list):raise ContractError('文档结构无效')
    for p,page in enumerate(doc['pages']):
        if not isinstance(page.get('pixel_digest'),str) or not re.fullmatch('[a-f0-9]{64}',page['pixel_digest']):raise ContractError('缺少原图指纹')
        width,height=page.get('size',(0,0))
        page_rect=rect((0,0,width,height));seen=set()
        for box in page.get('boxes',[]):
            key=box.get('id')
            if not isinstance(key,str) or not key or key in seen:raise ContractError('文字框编号缺失或重复')
            seen.add(key)
            if not isinstance(box.get('text'),str):raise ContractError('文字内容无效')
            if not contained(rect(box.get('rect')),page_rect):raise ContractError('文字框超出页面')

def plan_replace(doc,old,new,*,pages=None,case_sensitive=False,match='whole',confidence=.95):
    """Only whole-box matches are automatic by default. Substrings require OCR spans.

    OCR text and embedded document instructions are data. This API never interprets
    them as user commands and never calls tools named in document content.
    """
    validate_document(doc)
    if not isinstance(old,str) or not old or not isinstance(new,str):raise ContractError('替换内容无效')
    if match not in ('whole','substring'):raise ContractError('不支持的匹配方式')
    if not 0<=confidence<=1:raise ContractError('置信度门槛无效')
    scope=list(range(len(doc['pages']))) if pages is None else list(pages)
    if len(scope)!=len(set(scope)) or any(isinstance(p,bool) or not isinstance(p,int) or not 0<=p<len(doc['pages']) for p in scope):raise ContractError('页码范围无效')
    edits=[];review=[]
    pattern=re.compile(re.escape(old),0 if case_sensitive else re.I)
    for p in scope:
        for box in doc['pages'][p].get('boxes',[]):
            text=box['text'];hits=list(pattern.finditer(text))
            if not hits:continue
            if match=='whole' and not (len(hits)==1 and hits[0].span()==(0,len(text))):
                review.append(ReviewItem(p,box['id'],'品牌与其他文字在同一框中，需要单独定位，未自动修改整行'))
                continue
            checked=bool(box.get('human_verified',False))
            score=box.get('confidence')
            if not checked and (not isinstance(score,(int,float)) or isinstance(score,bool) or not math.isfinite(score) or not confidence<=score<=1):
                review.append(ReviewItem(p,box['id'],'识别置信度不足或缺失，需要核对'))
                continue
            pending=[];reason=None
            for hit in hits:
                start,end=hit.span()
                if start==0 and end==len(text):region=rect(box['rect'])
                else:
                    spans=[s for s in box.get('spans',[]) if s.get('start')==start and s.get('end')==end and s.get('text')==text[start:end]]
                    if len(spans)!=1:
                        reason='缺少精确单词坐标，未按字符数量猜测擦除位置';break
                    region=rect(spans[0]['rect'])
                    if not contained(region,rect(box['rect'])):raise ContractError('单词坐标超出所属文字框')
                pending.append(Edit(p,box['id'],text[start:end],new,region,digest(box),start,end))
            if reason:review.append(ReviewItem(p,box['id'],reason))
            else:edits.extend(pending)
    request=dict(operation='replace_text',old=old,new=new,pages=scope,case_sensitive=case_sensitive,match=match,minimum_confidence=confidence)
    return Plan(1,digest(doc),request,tuple(edits),tuple(review))

def validate_plan(doc,plan):
    """Recompute permissions instead of trusting an LLM-generated action list."""
    if not isinstance(plan,Plan) or plan.version!=1:raise ContractError('修改计划版本无效')
    if digest(doc)!=plan.document_digest:raise ContractError('文档已变化，请重新生成修改计划')
    request=plan.request
    if set(request)!={'operation','old','new','pages','case_sensitive','match','minimum_confidence'} or request['operation']!='replace_text':raise ContractError('计划包含未支持的操作或参数')
    expected=plan_replace(doc,request['old'],request['new'],pages=request['pages'],case_sensitive=request['case_sensitive'],match=request['match'],confidence=request['minimum_confidence'])
    # UI may select a subset; no new regions or edited strings can be injected.
    allowed={canonical(asdict(e)) for e in expected.edits}
    actual=[canonical(asdict(e)) for e in plan.edits]
    if len(actual)!=len(set(actual)) or not all(e in allowed for e in actual):raise ContractError('计划超出了允许修改的文字或区域')
    if plan.review!=expected.review:raise ContractError('不能隐藏待核对项目')
    return True

def apply_text_edits(doc,plan,*,approved_plan_id):
    """Pure transaction: validate all operations first, return a copy, never mutate input."""
    validate_plan(doc,plan)
    if approved_plan_id!=plan.id:raise ContractError('修改计划与预览不一致')
    # Pending items do not silently become completed. The caller must explicitly
    # label a partial plan or resolve them before presenting a complete result.
    result=json.loads(canonical(doc));grouped={}
    for e in plan.edits:grouped.setdefault((e.page,e.box_id),[]).append(e)
    for (p,key),changes in grouped.items():
        box=next(b for b in result['pages'][p]['boxes'] if b['id']==key)
        for e in sorted(changes,key=lambda e:e.start,reverse=True):
            if digest(next(b for b in doc['pages'][p]['boxes'] if b['id']==key))!=e.box_digest:raise ContractError('目标文字框已变化')
            if box['text'][e.start:e.end]!=e.before:raise ContractError('原文字已变化')
            box['text']=box['text'][:e.start]+e.after+box['text'][e.end:]
    return result

def composite_patch(original,generated,mask):
    """Ignore model output outside permission masks, even if the server repaints it."""
    import numpy as np
    src=np.asarray(original);candidate=np.asarray(generated);m=np.asarray(mask)
    if src.shape!=candidate.shape or src.dtype!=candidate.dtype:raise ContractError('修复结果尺寸或像素格式改变，已拒绝写入')
    if src.ndim!=3 or src.shape[2]!=3 or src.dtype!=np.uint8 or m.shape!=src.shape[:2]:raise ContractError('图像或遮罩格式无效')
    if m.dtype!=np.bool_ and not (m.dtype==np.uint8 and np.isin(m,[0,255]).all()):raise ContractError('遮罩必须为二值图，不允许模糊扩大编辑范围')
    out=src.copy();allowed=m if m.dtype==np.bool_ else m==255;out[allowed]=candidate[allowed]
    if not np.array_equal(out[~allowed],src[~allowed]):raise ContractError('检测到越界修改')
    return out
