"""Create a fictitious brochure and annotations; no external media are used."""
from pathlib import Path
import argparse,json
from PIL import Image,ImageDraw,ImageFont

def font(size,bold=False):
 candidates=(['/System/Library/Fonts/Supplemental/Arial Bold.ttf','C:/Windows/Fonts/arialbd.ttf','DejaVuSans-Bold.ttf'] if bold else ['/System/Library/Fonts/Supplemental/Arial.ttf','C:/Windows/Fonts/arial.ttf','DejaVuSans.ttf'])
 for name in candidates:
  try:return ImageFont.truetype(name,size)
  except OSError:continue
 return ImageFont.load_default(size=size)

def create_demo(output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 im=Image.new('RGB',(1600,900),'#f8fafc');d=ImageDraw.Draw(im)
 d.rectangle((800,0,1600,900),fill='#e4edf3')
 # Entirely procedural architectural forms.
 d.polygon([(880,250),(1210,145),(1515,315),(1190,430)],fill='#cad9e3')
 d.polygon([(880,250),(1190,430),(1190,755),(880,575)],fill='#b3c9d7')
 d.polygon([(1190,430),(1515,315),(1515,635),(1190,755)],fill='#8aaabd')
 d.polygon([(961,354),(1105,435),(1105,657),(961,575)],fill='#f0f5f8')
 d.polygon([(1280,447),(1434,392),(1434,557),(1280,613)],fill='#52798f')
 d.line([(870,760),(1190,840),(1535,710)],fill='#c2d2dd',width=3)
 annotations=[]
 def text(x,y,value,size,color='#263e50',bold=False,target=False):
  f=font(size,bold);d.text((x,y),value,font=f,fill=color)
  if target:
   box=d.textbbox((x,y),value,font=f);left,top,right,bottom=box
   annotations.append(dict(text=value,rect=[left-3,top-3,right-left+6,bottom-top+6],confidence=1.,font_family='Arial',font_size=size*.75,bold=bold,text_color=[38,62,80],clean_mode='fill',clean_enabled=True,render_enabled=False))
 text(85,62,'ACME',48,bold=True,target=True)
 text(85,217,'Spaces,',82,bold=True);text(85,310,'reconsidered.',82,bold=True)
 text(90,455,'A fictitious design collection.',28,'#668091')
 text(90,510,'Made for a precise editing workflow.',25,'#668091')
 d.line((90,615,665,615),fill='#cedbe4',width=2)
 text(90,650,'PRODUCT GUIDE',19,'#668091');text(90,695,'SYNTHETIC DEMONSTRATION',18,'#668091')
 text(88,806,'ACME',24,bold=True,target=True)
 text(520,810,'2026  /  EDITION 01',18,'#668091')
 image=output/'synthetic-brochure.png';im.save(image)
 (output/'annotations.json').write_text(json.dumps(annotations,indent=2),encoding='utf-8')
 return image,annotations

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='examples/generated');args=parser.parse_args()
 path,_=create_demo(args.output);print(f'Synthetic demo created: {path}')
