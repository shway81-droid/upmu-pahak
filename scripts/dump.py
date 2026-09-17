# -*- coding: utf-8 -*-
"""업무별 '읽기용' 덤프를 _작업/dump/<부서>.txt 로 만든다. 1년 흐름(notes.json)을 쓰기 전에 이 파일들을 끝까지 읽는다.

  python dump.py --root "<공문 폴더>"
"""
import os, re, sys, json, argparse
sys.stdout.reconfigure(encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); a = ap.parse_args()
    work = os.path.join(os.path.abspath(a.root), '_작업')
    data = json.load(open(os.path.join(work, 'docs.json'), encoding='utf-8'))
    cfg = json.load(open(os.path.join(work, 'tasks.json'), encoding='utf-8'))
    os.makedirs(os.path.join(work, 'dump'), exist_ok=True)
    for gi, g in enumerate(cfg['groups']):
        path = os.path.join(work, 'dump', re.sub(r'[\\/:*?"<>|]', '_', g['label']) + '.txt')
        with open(path, 'w', encoding='utf-8') as f:
            for t in g['tasks'] + [dict(id=f"g{gi}_etc", name='공통 · 기타')]:
                sel = sorted([d for d in data['docs'] if d.get('task_id') == t['id']], key=lambda x: (x['date'], x['num']))
                f.write(f"\n##### {t['id']} | {t['name']} ({len(sel)})\n")
                for d in sel:
                    recv = '내부' if d['recv'] == '내부결재' else re.sub(r'^.*?(\S{2,8}교육지원청|교육감)', r'\1', d['recv'])[:26]
                    att = ' / '.join(x['name'][:30] for x in d['attachments'][:3])
                    basis = f" ←{d['basis'][:24]}({d['basis_date'][5:]})" if d['basis'] else ''
                    f.write(f"{d['id']} {d['date'][5:]} [{recv}]{basis} | {d['title']}\n    {d['body'][:240]}\n    첨부: {att}\n")
        print(f"{path}  ({os.path.getsize(path)//1024} KB)")


if __name__ == '__main__':
    main()
