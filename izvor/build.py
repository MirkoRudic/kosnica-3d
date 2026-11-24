import re
s=open('src.html').read()
b=open('/home/claude/vajb-osnova/moduli/static/base.css').read()
d=open('/home/claude/vajb-osnova/moduli/static/dialog.js').read()
names=['hexagons','hexagon','christmas-ball','plus','download','player-play','player-pause','settings','x','chevron-down','upload','box','badge','arrow-up','arrow-down','heart-bolt']
syms=[]
for n in names:
    svg=open(f'/home/claude/npmtmp/node_modules/@tabler/icons/icons/outline/{n}.svg').read()
    paths=''.join(p for p in re.findall(r'<path[^>]*/>',svg) if 'stroke="none"' not in p)
    syms.append(f'<symbol id="t-{n}" viewBox="0 0 24 24">{paths}</symbol>')
sprite='<svg width="0" height="0" style="position:absolute">'+''.join(syms)+'</svg>'
open('index.html','w').write(s.replace('/*BASE_CSS*/',b).replace('/*DIALOG_JS*/',d).replace('<!--ICONS-->',sprite))
