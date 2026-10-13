from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 7680, 4320
OUT = Path(__file__).with_name('outputs') / 'umgc_portal_mockup_unofficial.png'

def font(size, bold=False):
    for p in ['C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf']:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

img = Image.new('RGB', (W, H), '#f5f6f8'); d = ImageDraw.Draw(img)
d.rectangle((0,0,W,330), fill='#e7e9ed'); d.rectangle((0,280,W,330), fill='#d9dce1')
d.text((70,65), '<   >   Refresh', fill='#5c626b', font=font(58, True))
d.rounded_rectangle((560,55,7250,240), 22, fill='white', outline='#b8bdc5', width=4)
d.text((635,95), 'https://my.umgc.edu/StudentCenter', fill='#3f4650', font=font(58))
d.rectangle((0,330,W,760), fill='#073b70'); d.rectangle((0,760,W,850), fill='#f1b434')
d.ellipse((120,420,330,630), outline='#f1b434', width=28); d.arc((120,420,330,630), 200,335, fill='#d44a37', width=28)
d.text((390,410), 'UMGC', fill='white', font=font(165, True)); d.text((410,600), 'Student Portal', fill='#dce9f7', font=font(66))
d.rectangle((0,850,W,1100), fill='white')
d.text((190,925), 'Student Center', fill='#1c4f83', font=font(66, True)); d.text((760,925), '>', fill='#7b838d', font=font(66)); d.text((880,925), 'My Class Schedule', fill='#333b45', font=font(66, True)); d.line((150,1080,W-150,1080), fill='#c9cdd3', width=4)
d.text((210,1215), 'My Class Schedule', fill='#27313a', font=font(115, True))
d.text((210,1380), 'Term:', fill='#59636d', font=font(62, True)); d.text((430,1380), 'Fall 2026', fill='#222a31', font=font(62)); d.text((1120,1380), 'Session:', fill='#59636d', font=font(62, True)); d.text((1430,1380), 'Undergraduate 8-Week Session 3', fill='#222a31', font=font(62))
d.text((210,1535), 'Student:', fill='#59636d', font=font(62, True)); d.text((510,1535), 'Sullivan, Jordan R.', fill='#222a31', font=font(62)); d.text((1530,1535), 'Demo ID:', fill='#59636d', font=font(62, True)); d.text((1870,1535), 'DEMO-0987654', fill='#222a31', font=font(62))
x0,y0,rowh=210,1775,240; widths=[760,1510,420,330,420,720,560,760]; headers=['Course','Description','Section','Credits','Days','Time','Location','Instructor']; rows=[['CMSC 105','Intro to Programming in Python','6380','3.00','Tu/Th','1:00 PM - 2:15 PM','Online','Dr. J. Smith'],['STAT 200','Introduction to Statistics','9040','3.00','Mo','6:00 PM - 8:30 PM','Online','Prof. A. Davis']]
x=x0
for w,h in zip(widths,headers):
    d.rectangle((x,y0,x+w,y0+rowh), fill='#d9e2ee', outline='#9ca8b5', width=4); d.text((x+25,y0+72),h,fill='#163b63',font=font(48,True)); x+=w
for i,row in enumerate(rows):
    x=x0; yy=y0+rowh*(i+1)
    for w,v in zip(widths,row): d.rectangle((x,yy,x+w,yy+rowh),fill='white',outline='#b8c0c9',width=3); d.text((x+25,yy+78),v,fill='#26313b',font=font(46)); x+=w
sy=y0+rowh*3+115; d.rounded_rectangle((210,sy,2600,sy+230),12,fill='#edf3f8',outline='#bdc8d3',width=3); d.text((260,sy+62),'Status: Enrolled',fill='#1d5b38',font=font(60,True)); d.text((3120,sy+62),'Total Tuition: $1,800.00',fill='#27313a',font=font(60,True))
d.text((210,H-250),'Student Portal • Academic Records • Demo interface',fill='#7d858d',font=font(38)); d.text((W-2800,H-360),'UNOFFICIAL MOCKUP',fill='#a4aab1',font=font(120,True))
overlay=Image.new('RGBA',(W,H),(255,255,255,8)); od=ImageDraw.Draw(overlay)
for y in range(0,H,8): od.line((0,y,W,y),fill=(0,0,0,7),width=1)
img=Image.alpha_composite(img.convert('RGBA'),overlay).convert('RGB'); OUT.parent.mkdir(exist_ok=True); img.save(OUT,quality=96); print(OUT)
