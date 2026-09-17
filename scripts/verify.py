# -*- coding: utf-8 -*-
"""결과 HTML 검증. 하나라도 FAIL 이면 종료코드 1.

  python verify.py --root "<공문 폴더>"
"""
import os, re, sys, json, glob, argparse, subprocess, tempfile
sys.stdout.reconfigure(encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); a = ap.parse_args()
    root = os.path.abspath(a.root); work = os.path.join(root, '_작업')
    htmls = glob.glob(os.path.join(root, '*_업무파악.html'))
    assert htmls, "결과 HTML이 없습니다. build_html.py 를 먼저 실행하세요."
    html = open(max(htmls, key=os.path.getmtime), encoding='utf-8').read()
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    P = json.loads(m.group(1).replace('<\\/', '</'))
    data = json.load(open(os.path.join(work, 'docs.json'), encoding='utf-8'))
    docs, cards = P['docs'], P['cards']
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(('OK  ' if cond else 'FAIL'), msg); ok = ok and cond

    src = data['docs']; excluded = sum(1 for d in src if d.get('excluded')); orphan = [d for d in src if d.get('group') is None and not d.get('excluded')]
    check(len(docs) + excluded + len(orphan) == len(src), f"문서 수: 화면 {len(docs)} + 제외 {excluded} + 미배정 {len(orphan)} = 원본 {len(src)}")
    check(not orphan, f"부서 미배정 문서 0건 (현재 {len(orphan)})")
    ids = {c['id'] for c in cards}
    check(all(d['task'] in ids for d in docs), "모든 문서가 업무에 배정됨")
    etc = sum(1 for d in docs if d['task'].endswith('_etc'))
    print(f"     기타로 간 문서 {etc}건 ({etc*100//max(1,len(docs))}%) — 10%를 넘으면 규칙을 더 다듬는다")
    check(all(re.match(r'^\d{4}-\d{2}-\d{2}$', d['date']) for d in docs), "결재일 형식")
    links = [d['pdf'] for d in docs] + [x['rel'] for d in docs for x in d['att']]
    missing = [p for p in links if not os.path.exists(os.path.join(root, p))]
    check(not missing, f"링크 대상 파일 존재 {len(links)-len(missing)}/{len(links)}")
    for p in missing[:5]: print("     없음:", p)
    all_att = {x['rel'] for d in src for x in d['attachments']}
    disk_att = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(('_', '.'))]
        for f in fn:
            if re.match(r'^\(.+?-\d+\s*\(첨부\)\)', f): disk_att.add(os.path.relpath(os.path.join(dp, f), root).replace('\\', '/'))
    check(disk_att == all_att, f"첨부 파일 전수 연결 {len(all_att & disk_att)}/{len(disk_att)}")
    for p in sorted(disk_att - all_att)[:5]: print("     미연결:", p)
    noflow = [c['name'] for c in cards if c['count'] and not c['steps'] and not c['id'].endswith('_etc')]
    check(not noflow, f"문서가 있는 모든 업무에 1년 흐름이 있음 {noflow[:5] if noflow else ''}")
    docids = {}
    for d in docs: docids.setdefault(d['task'], set()).add(d['id'])
    badkey = [(c['id'], k) for c in cards for k in c['key'] if k not in docids.get(c['id'], set())]
    check(not badkey, f"핵심 문서 id가 해당 업무에 존재 {badkey[:5] if badkey else ''}")
    js = re.findall(r'<script>(.*?)</script>', html, re.S)[-1]
    try:
        p = os.path.join(tempfile.gettempdir(), 'upmu_check.js'); open(p, 'w', encoding='utf-8').write(js)
        r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
        check(r.returncode == 0, "화면 스크립트 문법 검사(node)" + ('' if r.returncode == 0 else ' ' + r.stderr[:200]))
    except FileNotFoundError:
        print("     (node 없음 — 문법 검사는 브라우저에서 직접 확인)")
    print("\n결과:", "모두 통과" if ok else "실패 항목 있음")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
