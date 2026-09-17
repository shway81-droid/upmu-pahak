# -*- coding: utf-8 -*-
"""HWPX(업무분장표 등)의 글과 표를 순서대로 텍스트로 출력한다.

  python read_hwpx.py "<파일.hwpx>"

표는 '셀 | 셀 | 셀' 한 줄씩. 병합 셀 때문에 열이 밀려 보일 수 있으니 부서·담당자·업무 열은 눈으로 맞춰 읽는다.
(.hwp 구형 파일은 이 스크립트로 못 읽는다 — hwp 스킬을 쓰거나, 사용자에게 hwpx/PDF로 다시 저장해 달라고 한다.)
"""
import sys, zipfile
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
NS = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'


def text(el): return ''.join(t.text or '' for t in el.iter(NS + 't'))


def walk(el):
    for ch in el:
        tag = ch.tag.replace(NS, '')
        if tag == 'tbl':
            print(f"\n----- 표 ({ch.get('rowCnt')}행 x {ch.get('colCnt')}열) -----")
            for tr in ch.findall(NS + 'tr'):
                print(' | '.join(' '.join(text(p).strip() for p in tc.iter(NS + 'p') if text(p).strip()) for tc in tr.findall(NS + 'tc')))
        elif tag == 'p':
            if any(True for _ in ch.iter(NS + 'tbl')): walk(ch)
            elif text(ch).strip(): print(text(ch).strip())
        else:
            walk(ch)


z = zipfile.ZipFile(sys.argv[1])
for n in sorted(x for x in z.namelist() if x.startswith('Contents/section')):
    walk(ET.fromstring(z.read(n)))
