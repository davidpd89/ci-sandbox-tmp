#!/usr/bin/env python3
from __future__ import annotations
import json, py_compile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'tools'/'manecillas_launch'
def fail(m): raise SystemExit('ERROR IG-06: '+m)
def main():
    req=[BASE/'README.md',BASE/'ig06_manifest.json',BASE/'fetch_assets.py',BASE/'render_launch.py']
    miss=[str(p.relative_to(ROOT)) for p in req if not p.exists()]
    if miss: fail('faltan archivos: '+', '.join(miss))
    for p in req[2:]:
        try: py_compile.compile(str(p),doraise=True)
        except py_compile.PyCompileError as e: fail(f'{p.name} no compila: {e.msg}')
    d=json.loads((BASE/'ig06_manifest.json').read_text(encoding='utf-8'))
    if d.get('id')!='IG-06_MANECILLAS_LAUNCH_v1' or d.get('canvas')!=[1080,1350]: fail('id/canvas alterados')
    c=d['cover']
    if c.get('drive_id')!='1SClEck69kTqbqorViNxks1t1Axwu-Vy1' or c.get('sha256')!='1361ed45dad7cfea9f9e07de08369ef4e656867f9ecc370c429571cfba0b1e8b' or [c.get('width'),c.get('height')]!=[1024,1536]: fail('portada canónica alterada')
    if d.get('canonical_excerpt_drive_id')!='1CtjHvvy7BxBm-H7I5CXh5p7wK3QcykCt': fail('fuente canónica de fragmentos alterada')
    eps=d.get('episodes') or []
    if [e.get('id') for e in eps]!=['ig06_01','ig06_02','ig06_03'] or any(len(e.get('slides') or [])!=7 for e in eps): fail('deben existir 3 episodios × 7 slides')
    expected=[('Para nosotros, las horas son silenciosas. Digitales.','Fragmento de Las manecillas del recuerdo · pág. 239'),('En la calle todo tiene dos precios: lo que cuesta y lo que te cuesta desprenderte de ello.','Fragmento de Las manecillas del recuerdo · pág. 229'),('Los objetos importantes tienen apellido, Ana. Y no siempre el de quienes los poseen.','Fragmento de Las manecillas del recuerdo · pág. 229')]
    for ep,(quote,footer) in zip(eps,expected):
        if ep['slides'][5].get('quote')!=quote or ep['slides'][5].get('footer')!=footer: fail(ep['id']+' fragmento alterado')
        if ep['slides'][0].get('kind')!='archive' or ep['slides'][4].get('kind')!='bridge' or ep['slides'][5].get('kind')!='excerpt' or ep['slides'][6].get('kind')!='book': fail(ep['id']+' estructura 4+1+1+1 alterada')
        if len(ep.get('hashtags') or [])!=4: fail(ep['id']+' debe mantener 4 hashtags')
    if eps[0]['slides'][6].get('support')!='Publicado hoy · Monza Ediciones': fail('Publicado hoy solo en IG-06-01')
    if any('Publicado hoy' in json.dumps(e,ensure_ascii=False) for e in eps[1:]): fail('Publicado hoy no puede aparecer en 02/03')
    subs=d.get('metricool_substitutions') or []
    if [(x['date'],x['existing_post_id']) for x in subs]!=[('2026-09-03',348656152),('2026-09-05',348656248),('2026-09-07',348657759)]: fail('sustituciones Metricool alteradas')
    fetch=(BASE/'fetch_assets.py').read_text(encoding='utf-8'); render=(BASE/'render_launch.py').read_text(encoding='utf-8')
    for marker in ('isPublicDomain','LicenseShortName','SOURCE_OK','IG06_ASSET_BLOCKED'):
        if marker not in fetch: fail('downloader perdió guardia '+marker)
    for marker in ('IG06_RENDER_BLOCKED','RENDERED_NOT_SCHEDULED','document.fonts.load','Playfair Display','cover_sha256','object-fit:contain'):
        if marker not in render: fail('renderer perdió guardia '+marker)
    print('OK: IG-06 conserva 21 slides, fuentes, fragmentos, portada y sustituciones sin programar.')
if __name__=='__main__': main()
