# -*- coding: utf-8 -*-
"""공문 폴더 → _작업/docs.json

  python extract.py --root "<공문 폴더>" [--scan-only]

파일명 규칙(K-에듀파인 일괄 저장): (학교명-문서번호 (본문|첨부)) 제목.확장자
본문 PDF에서 수신·근거·본문·붙임·기안자·결재일을 뽑고, 같은 폴더·같은 번호의 첨부를 연결한다.
부서는 최상위 폴더명, 월은 결재일에서 계산한다(폴더에 월 구분이 없어도 된다).
"""
import os, re, sys, json, argparse, collections
sys.stdout.reconfigure(encoding='utf-8')

PAT = re.compile(r'^\((?P<school>.+?)-(?P<num>\d+)\s*\((?P<kind>본문|첨부)\)\)\s*(?P<title>.+)$')
ROLE = re.compile(r'^(★\s*)?[가-힣·\s]{0,10}(교사|교장|교감|원장|원감|전담사|실무사|행정사|실장|강사|주무관|사서|영양사|부장|보건교사|영양교사|지도사)$')
NAME = re.compile(r'^(?!전결$|대결$|출장$|수신$|수신자$|참조$|구분$|성명$|성별$|비고$|협조자$|연번$|소속$|직위$|기간$|내용$)[가-힣]{2,4}$')
DATE_RE = re.compile(r'(전결|대결)?\s*\n?(\d{4})\.\s*\n?(\d{1,2})\.\s*\n?(\d{1,2})\.?')


def read_pdf(path):
    try:
        import fitz
        d = fitz.open(path)
        return "\n".join(p.get_text() for p in d), len(d)
    except ImportError:
        from pypdf import PdfReader
        r = PdfReader(path)
        return "\n".join((p.extract_text() or '') for p in r.pages), len(r.pages)


def parse_sign(text):
    """결재란은 '협조자' 바로 앞에 있다. 첫 (직위→이름) 쌍이 기안자, 마지막 날짜가 결재일.
    본문에도 날짜(관련 공문 일자)가 있으므로 반드시 '마지막' 날짜를 쓴다."""
    j = text.find('협조자')
    seg = text[:j] if j >= 0 else text
    k = seg.rfind('끝.')
    seg = seg[k + 2:] if k >= 0 else seg
    lines = [l.strip() for l in seg.split('\n') if l.strip()][-20:]
    joined = '\n'.join(lines)
    ms = list(DATE_RE.finditer(joined))
    date, kind, approver = '', '', ''
    if ms:
        dm = ms[-1]
        date = f"{dm.group(2)}-{int(dm.group(3)):02d}-{int(dm.group(4)):02d}"
        kind = dm.group(1) or '결재'
        after = [l for l in joined[dm.end():].split('\n') if l.strip()]
        approver = next((l for l in after if NAME.match(l)), '')
    # 기안자: ① ★ 표시가 붙은 직위 다음 이름 ② 없으면 결재일 직전 8줄 안의 첫 (직위→이름) 쌍.
    # 범위를 좁히는 이유: 본문 끝의 표(강사 명단 등)에도 '○○강사 / 이름' 꼴이 나와 기안자로 잘못 잡힌다.
    is_name = lambda x: bool(NAME.match(x)) and not ROLE.match(x)
    drafter = ''
    for i, l in enumerate(lines[:-1]):
        if l.startswith('★') and ROLE.match(l) and is_name(lines[i + 1]):
            drafter = lines[i + 1]; break
    if not drafter:
        di = next((i for i in range(len(lines) - 1, -1, -1) if re.search(r'\d{4}\.', lines[i])), len(lines))
        win = lines[max(0, di - 8):di + 1]
        for i, l in enumerate(win[:-1]):
            if ROLE.match(l) and is_name(win[i + 1]) and win[i + 1] != approver:
                drafter = win[i + 1]; break
    if not drafter and approver: drafter = approver      # 전결·대결 또는 1인 결재
    return drafter, date, kind


def parse_body(text, school):
    lines = [l.strip() for l in text.split('\n')]
    recv = ''
    if '수신' in lines:
        i = lines.index('수신'); recv = lines[i + 1] if i + 1 < len(lines) else ''
    body = ''
    if '제목' in lines:
        i = lines.index('제목')
        start = i + 2
        for k in range(i + 1, min(i + 6, len(lines))):   # 제목이 두 줄로 넘어가는 경우를 건너뛴다
            if re.match(r'^1\s*\.', lines[k]) or '관련' in lines[k][:8]:
                start = k; break
        out = []
        for l in lines[start:]:
            if l.startswith('★') or ROLE.match(l) or l in ('협조자', school + '장') or l.startswith('시행'):
                break
            out.append(l)
        body = re.sub(r'\s+', ' ', ' '.join(out)).strip()
        # 결과 HTML은 교내에서 돌려 보므로 본문의 전화번호·주민번호는 가린다
        body = re.sub(r'01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}', '010-****-****', body)
        body = re.sub(r'\b(\d{6})[-\s]?[1-4]\d{6}\b', r'\1-*******', body)
    rm = re.search(r'관련\s*[:：]?\s*([^\n]+?)\s*[\(（]\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})', text)
    basis, basis_date = '', ''
    if rm:
        basis = re.sub(r'^(가\.|나\.|;|:)\s*', '', rm.group(1).strip())
        try: basis_date = f"{rm.group(2)}-{int(rm.group(3)):02d}-{int(rm.group(4)):02d}"
        except ValueError: pass
    am = re.search(r'붙임\s*(.+?)\s*끝\.', text, flags=re.S)
    attach = re.sub(r'\s+', ' ', am.group(1)) if am else ''
    coop = ('협조자' in text) and ('행정실장' in text.split('협조자')[-1][:60])
    return recv, body, basis, basis_date, attach, coop


def tags_for(title, recv, coop):
    t = []
    if recv and recv != '내부결재': t.append('외부제출')
    if '학교운영위원회 심의' in title or '학운위' in title: t.append('학운위')
    elif re.search(r'위원회|협의회|회의|다모임', title): t.append('위원회')
    if re.search(r'가정통신문|안내장', title): t.append('가정통신문')
    if coop or re.search(r'성립전|예산|운영비|강사비|강사료|인건비|지급|정산|구입|구매|물품|경비|사전결재', title): t.append('예산')
    if re.search(r'신청', title): t.append('신청')
    if re.search(r'국회|도의회|시의회|군의회|의원|감사원|행정사무감사|국정감사', title): t.append('의회·감사')
    return t


def norm_title(t):
    t = re.sub(r'\(.*?\)', '', t)
    t = re.sub(r'20\d\d\s*학?년?도?\.?|\d{1,2}\s*월|\d+\s*차|\d+\s*주|\d+', '', t)
    return re.sub(r'[\s\.\-·,:_「」『』]', '', t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--scan-only', action='store_true', help='PDF를 읽지 않고 폴더 구성만 보고')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    work = os.path.join(root, '_작업')

    mains, atts, nomatch, schools = [], collections.defaultdict(list), [], collections.Counter()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(('_', '.'))]
        for f in fn:
            base, ext = os.path.splitext(f)
            m = PAT.match(base)
            rel = os.path.relpath(os.path.join(dp, f), root)
            if not m:
                if dp != root or ext.lower() in ('.pdf', '.hwp', '.hwpx', '.xlsx'): nomatch.append(rel)
                continue
            schools[m.group('school')] += 1
            num = int(m.group('num'))
            if m.group('kind') == '본문':
                mains.append(dict(num=num, title=m.group('title'), rel=rel, dir=dp, ext=ext.lower()))
            else:
                atts[(dp, num)].append(dict(name=m.group('title') + ext, rel=rel.replace('\\', '/')))
    school = schools.most_common(1)[0][0] if schools else ''
    tops = collections.Counter(r['rel'].split(os.sep)[0] if os.sep in r['rel'] else '(루트)' for r in mains)
    print(f"학교명: {school}  (파일명에서 발견: {dict(schools)})")
    print(f"본문 {len(mains)}건 · 첨부 {sum(len(v) for v in atts.values())}개 · 규칙 밖 파일 {len(nomatch)}개")
    print("최상위 폴더별 본문 수:", dict(tops))
    for p in nomatch[:15]: print("  규칙 밖:", p)
    bunjang = [p for p in nomatch if '업무분장' in p] + [x['rel'] for lst in atts.values() for x in lst if '업무분장' in x['name']]
    print("업무분장표 후보:", bunjang[:8] if bunjang else "없음 — 사용자에게 요청한다")
    nonpdf = [r['rel'] for r in mains if r['ext'] != '.pdf']
    if nonpdf: print(f"※ 본문이 PDF가 아닌 파일 {len(nonpdf)}건 (본문 추출 불가):", nonpdf[:5])
    if a.scan_only or not mains: return
    os.makedirs(work, exist_ok=True)

    docs, notext = [], []
    for r in mains:
        text, pages = ('', 0)
        if r['ext'] == '.pdf':
            try: text, pages = read_pdf(os.path.join(root, r['rel']))
            except Exception as e: print("  PDF 읽기 실패:", r['rel'], e)
        if len(text.strip()) < 50: notext.append(r['rel'])
        drafter, date, kind = parse_sign(text)
        recv, body, basis, basis_date, attach, coop = parse_body(text, school)
        parts = r['rel'].split(os.sep)
        docs.append(dict(num=r['num'], folder=parts[0] if len(parts) > 1 else '', title=r['title'],
                         rel=r['rel'].replace('\\', '/'), date=date, approve=kind, drafter=drafter,
                         recv=recv, basis=basis, basis_date=basis_date, body=body, attach_text=attach,
                         attachments=sorted(atts.get((r['dir'], r['num']), []), key=lambda x: x['name']),
                         coop_admin=bool(coop), tags=tags_for(r['title'], recv, coop), pages=pages))
    # 같은 폴더에서 못 찾은 첨부는 번호가 유일할 때만 번호로 연결
    used = {a_['rel'] for d in docs for a_ in d['attachments']}
    by_num = collections.defaultdict(list)
    for d in docs: by_num[d['num']].append(d)
    for (dp, num), lst in atts.items():
        for a_ in lst:
            if a_['rel'] not in used and len(by_num.get(num, [])) == 1:
                by_num[num][0]['attachments'].append(a_); used.add(a_['rel'])

    # 문서 id = 결재연도-번호 (문서번호는 1월에 1번으로 돌아가므로 연도를 붙여야 유일)
    dated = [d for d in docs if d['date']]
    if dated:
        first = min(d['date'] for d in dated)
        sy = int(first[:4]) if int(first[5:7]) >= 3 else int(first[:4]) - 1
    else:
        sy = 0
    for d in docs:
        y, m = (int(d['date'][:4]), int(d['date'][5:7])) if d['date'] else (0, 0)
        d['id'] = f"{y}-{d['num']}"
        d['ym'] = y * 100 + m
        d['month'] = (f"{m}월" if y == sy else f"{y}년 {m}월") if y else '날짜 미상'
    seen = collections.Counter(d['id'] for d in docs)
    for d in docs:
        if seen[d['id']] > 1: d['id'] += '-' + re.sub(r'\W', '', d['folder'])[:6]
    months_by_norm = collections.defaultdict(set)
    for d in docs: months_by_norm[(d['folder'], norm_title(d['title']))].add(d['month'])
    for d in docs:
        c = len(months_by_norm[(d['folder'], norm_title(d['title']))])
        d['cycle'] = '매월' if c >= 5 else ('반복' if c >= 2 else '연1회')
    docs.sort(key=lambda d: (d['date'], d['num']))
    meta = dict(school=school, school_year=sy, months=[m for _, m in sorted({(d['ym'], d['month']) for d in docs})])
    json.dump(dict(meta=meta, docs=docs), open(os.path.join(work, 'docs.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    # tasks.json 의 pattern 을 쓸 때 볼 제목 목록
    with open(os.path.join(work, 'titles.txt'), 'w', encoding='utf-8') as f:
        for folder in sorted({d['folder'] for d in docs}):
            sel = [d for d in docs if d['folder'] == folder]
            f.write(f"\n##### 폴더: {folder or '(루트)'} ({len(sel)}건)\n")
            for d in sel: f.write(f"{d['id']:>10s} {d['date'][5:]} {d['drafter']:4s} {d['title']}\n")
    print(f"\n추출 완료 → _작업/docs.json, _작업/titles.txt  ({sy}학년도, {len(docs)}건)")
    for k in ('date', 'drafter', 'recv', 'body'):
        print(f"  {k:8s} 누락 {sum(1 for d in docs if not d[k])}")
    print("  기안자:", collections.Counter(d['drafter'] for d in docs).most_common(12))
    print("  폴더×기안자:", collections.Counter((d['folder'], d['drafter']) for d in docs).most_common(15))
    print("  월:", meta['months'])
    linked = sum(len(d['attachments']) for d in docs); total = sum(len(v) for v in atts.values())
    print(f"  첨부 연결 {linked}/{total}")
    if notext: print(f"  ※ 글자가 추출되지 않는 PDF {len(notext)}건(스캔본 가능성):", notext[:5])


if __name__ == '__main__':
    main()
