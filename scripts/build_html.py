# -*- coding: utf-8 -*-
"""docs.json + tasks.json + notes.json + assets/template.html → <공문 폴더>/<학교약칭>_업무파악.html

  python build_html.py --root "<공문 폴더>"

화면 구성은 template.html 에 있다. 이 스크립트는 데이터만 채운다(템플릿을 정규식으로 고치지 말 것 —
JS 안의 'D.groups' 같은 줄이 CSS 선택자 패턴에 걸려 지워진 적이 있다. 고칠 땐 정확한 문자열 치환으로).
"""
import os, re, sys, json, argparse
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
PALETTE = ['#2f6fed', '#0f9d58', '#e8710a', '#a142f4', '#d93025', '#00838f', '#6d4c41', '#c2185b', '#558b2f', '#455a64']
ETC_NAME = '공통 · 기타 (의회·감사 요구자료 등)'


def short_recv(r):
    if r == '내부결재': return r
    r = re.sub(r'^(?:\S*?(?:특별자치도|특별자치시|특별시|광역시|도))?(\S+?교육지원청)교육장\((.+?)\)$', r'\1 \2', r)
    r = re.sub(r'^\S*?교육감\((.+?)\)$', r'도교육청 \1', r)
    r = r.replace('(', ' ').replace(')', '').strip()
    return r[:28]


def short_basis(b, d, school):
    if not b: return ''
    short = school.replace('등학교', '').replace('학교', '')
    if b.startswith(school) or (short and b.startswith(short)):
        b = '본교 ' + re.sub(r'^[^-\d]*-?', '', b)
    b = re.sub(r'호$', '', b)
    return f"{b} ({int(d[5:7])}.{int(d[8:10])}.)" if d else b


def flow_steps(flow):
    """'3월 계획 → 4월 조사(안내 → 결과) → …' 를 괄호 밖의 '→' 에서만 끊는다."""
    steps, depth, cur = [], 0, ''
    for ch in flow:
        if ch in '(（': depth += 1
        elif ch in ')）': depth = max(0, depth - 1)
        if ch == '→' and depth == 0: steps.append(cur.strip()); cur = ''
        else: cur += ch
    if cur.strip(): steps.append(cur.strip())
    out = []
    for s in steps:
        m = re.match(r'^((?:\d{1,2}(?:[~·,]\s*\d{1,2})*월(?:\s*[말초])?(?:\s*~\s*\d{1,2}월)?|매월(?:\s*말)?|수시|연중|[12]학기(?:\s*[말초])?|(?:여름|겨울)?방학\s*중|학년\s*[말초]))\s*(.*)$', s)
        out.append(dict(when=m.group(1), what=m.group(2)) if m else dict(when='', what=s))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); a = ap.parse_args()
    root = os.path.abspath(a.root); work = os.path.join(root, '_작업')
    data = json.load(open(os.path.join(work, 'docs.json'), encoding='utf-8'))
    cfg = json.load(open(os.path.join(work, 'tasks.json'), encoding='utf-8'))
    np_ = os.path.join(work, 'notes.json')
    notes = json.load(open(np_, encoding='utf-8')) if os.path.exists(np_) else {}
    meta = data['meta']; school = cfg.get('school') or meta['school']
    short = cfg.get('school_short') or school.replace('등학교', '')
    docs = [d for d in data['docs'] if d.get('group') is not None and not d.get('excluded')]

    groups, cards = [], []
    for gi, g in enumerate(cfg['groups']):
        key = f"g{gi}"
        groups.append(dict(key=key, dept=key, label=g['label'], color=g.get('color') or PALETTE[gi % len(PALETTE)]))
        for ti, t in enumerate(g['tasks'] + [dict(id=f"g{gi}_etc", name=ETC_NAME, desc='업무분장 항목에 속하지 않는 건')]):
            n = notes.get(t['id'], {})
            cards.append(dict(id=t['id'], dept=key, name=t['name'], desc=t.get('desc', ''),
                              order=(999 if t['id'].endswith('_etc') else t.get('order', ti)),  # order: 칩 표시 순서(분류 우선순위와 별개)
                              count=sum(1 for d in docs if d['task_id'] == t['id']),
                              steps=flow_steps(n.get('flow', '')), key=n.get('key', [])))
    out = [dict(id=d['id'], num=d['num'], task=d['task_id'], dept=f"g{d['group']}", month=d['month'], date=d['date'],
                title=d['title'], recv=short_recv(d['recv']), external=d['recv'] != '내부결재',
                basis=short_basis(d['basis'], d['basis_date'], school), body=re.sub(r'\s*끝\.\s*$', '', d['body'])[:700],
                pdf=d['rel'], att=d['attachments'], tags=d['tags'], cycle=d['cycle']) for d in docs]
    months = [m for m in meta['months'] if any(d['month'] == m for d in docs)]
    payload = dict(meta=dict(school=school, short=short, year_label=f"{meta['school_year']}학년도"),
                   groups=groups, cards=cards, docs=out, months=months)
    tpl = open(os.path.join(HERE, '..', 'assets', 'template.html'), encoding='utf-8').read()
    assert tpl.count('__DATA__') == 1
    html = tpl.replace('__DATA__', json.dumps(payload, ensure_ascii=False).replace('</', '<\\/'))
    outp = os.path.join(root, f"{short}_업무파악.html")
    open(outp, 'w', encoding='utf-8').write(html)
    print(f"생성: {outp}  {os.path.getsize(outp)//1024} KB · 문서 {len(out)} · 업무 {sum(1 for c in cards if c['count'])}")
    nowhen = [(c['id'], s['what'][:24]) for c in cards for s in c['steps'] if not s['when']]
    if nowhen: print(f"시기 없이 시작하는 단계 {len(nowhen)}곳 — 앞 단계의 괄호 안으로 옮기거나 시기를 붙인다:", nowhen[:10])
    print("1년 흐름이 없는 업무:", [c['id'] for c in cards if c['count'] and not c['steps'] and not c['id'].endswith('_etc')])


if __name__ == '__main__':
    main()
