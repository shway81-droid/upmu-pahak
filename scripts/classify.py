# -*- coding: utf-8 -*-
"""_작업/tasks.json(+overrides.json) 규칙으로 docs.json 각 문서에 부서(group)·업무(task_id)를 배정한다.

  python classify.py --root "<공문 폴더>" [--list 전체|<부서 표시명>]

부서 결정: ① 최상위 폴더명이 group.folders 에 있으면 그 부서 ② 아니면 기안자가 group.drafters 에 있으면 그 부서.
업무 결정: 부서 안에서 tasks 를 위에서부터 보며 제목이 pattern 에 처음 걸리는 업무. 아무것도 안 걸리면 '기타'.
overrides.json {"문서id": "task_id"} 가 규칙보다 우선한다.
"""
import os, re, sys, json, argparse, collections
sys.stdout.reconfigure(encoding='utf-8')
ETC_DEFAULT = r'국회|도의회|시의회|군의회|의원|감사원|행정사무감사|국정감사'
ETC_NAME = '공통 · 기타 (의회·감사 요구자료 등)'


def load(root):
    work = os.path.join(root, '_작업')
    data = json.load(open(os.path.join(work, 'docs.json'), encoding='utf-8'))
    cfg = json.load(open(os.path.join(work, 'tasks.json'), encoding='utf-8'))
    ovp = os.path.join(work, 'overrides.json')
    ov = json.load(open(ovp, encoding='utf-8')) if os.path.exists(ovp) else {}
    return work, data, cfg, ov


def etc_id(gi): return f"g{gi}_etc"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--list')
    a = ap.parse_args()
    work, data, cfg, ov = load(os.path.abspath(a.root))
    groups = cfg['groups']
    ids = [t['id'] for g in groups for t in g['tasks']]
    assert len(ids) == len(set(ids)), "tasks.json: 업무 id가 중복됩니다"
    for g in groups:
        for t in g['tasks']: re.compile(t['pattern'])          # 잘못된 정규식은 여기서 바로 드러난다
    valid = set(ids) | {etc_id(i) for i in range(len(groups))}
    bad = {k: v for k, v in ov.items() if v not in valid}
    assert not bad, f"overrides.json 에 없는 task_id: {bad}"
    unknown = set(ov) - {d['id'] for d in data['docs']}
    if unknown: print("※ overrides.json 에 있지만 문서에 없는 id:", sorted(unknown)[:10])
    ex = cfg.get('exclude', {})
    ex_f, ex_d = set(ex.get('folders', [])), set(ex.get('drafters', []))
    etc_pat = re.compile(cfg.get('etc_pattern', ETC_DEFAULT))
    owner = {t['id']: gi for gi, g in enumerate(groups) for t in g['tasks']}
    owner.update({etc_id(gi): gi for gi in range(len(groups))})
    body_hint = []

    def group_of(d):
        for gi, g in enumerate(groups):
            if d['folder'] and d['folder'] in g.get('folders', []): return gi
        for gi, g in enumerate(groups):
            if d['drafter'] and d['drafter'] in g.get('drafters', []): return gi
        return None

    for d in data['docs']:
        d['excluded'] = bool((d['folder'] in ex_f) or (d['drafter'] in ex_d and group_of(d) is None))
        gi = None if d['excluded'] else group_of(d)
        d['group'] = gi
        if gi is None: d['task_id'], d['task_src'] = None, 'none'; continue
        if d['id'] in ov:     # override 는 다른 부서의 업무로도 옮길 수 있다(같은 사업 문서를 한곳에 모으기 위해)
            d['group'], d['task_id'], d['task_src'] = owner[ov[d['id']]], ov[d['id']], 'override'; continue
        gpat = groups[gi].get('etc_pattern')      # 부서별 기타 규칙(예: 담임으로서 한 일, 본인 수업공개)
        if etc_pat.search(d['title']) or (gpat and re.search(gpat, d['title'])):
            d['task_id'], d['task_src'] = etc_id(gi), 'etc-rule'; continue
        if etc_pat.search(d['body'][:160]): body_hint.append(d)
        for t in groups[gi]['tasks']:
            if re.search(t['pattern'], d['title']): d['task_id'], d['task_src'] = t['id'], 'rule'; break
        else:
            d['task_id'], d['task_src'] = etc_id(gi), 'unmatched'
    json.dump(data, open(os.path.join(work, 'docs.json'), 'w', encoding='utf-8'), ensure_ascii=False)

    docs = data['docs']
    cnt = collections.Counter(d['task_id'] for d in docs)
    print(f"제외(행정실 등) {sum(d['excluded'] for d in docs)}건 · 부서 미배정 {sum(1 for d in docs if d['group'] is None and not d['excluded'])}건 · 규칙 미매칭(기타로 감) {sum(1 for d in docs if d['task_src']=='unmatched')}건")
    for gi, g in enumerate(groups):
        print(f"[{g['label']}] {sum(1 for d in docs if d['group']==gi)}건")
        for t in g['tasks']: print(f"   {cnt[t['id']]:4d}  {t['id']:14s} {t['name']}")
        print(f"   {cnt[etc_id(gi)]:4d}  {etc_id(gi):14s} {ETC_NAME}")
    if body_hint:
        print("\n제목에는 없지만 본문 첫머리에 의회·감사 표현이 있는 문서 — 요구자료가 맞으면 overrides 로 기타에 보낸다:")
        for d in body_hint[:15]: print(f"   {d['id']:>10s} {d['title']}")
    big = [(t['name'], cnt[t['id']]) for g in groups for t in g['tasks'] if cnt[t['id']] > 45]
    if big: print("\n문서가 많이 몰린 업무(45건 초과) — '업무명 + 하위 주제'로 나누는 것을 검토:", big)
    empty = [t['name'] for g in groups for t in g['tasks'] if cnt[t['id']] == 0]
    if empty: print("문서가 0건인 업무(칩에 나오지 않는다):", empty)
    orphan = [d for d in docs if d['group'] is None and not d['excluded']]
    if orphan:
        print("\n부서 미배정 문서(폴더·기안자가 어느 부서에도 없음) — tasks.json 의 folders/drafters 를 보완하거나 exclude 에 넣는다:")
        for k, v in collections.Counter((d['folder'], d['drafter']) for d in orphan).most_common(10): print("   ", k, v)
    if a.list:
        for gi, g in enumerate(groups):
            if a.list not in ('전체', 'all', g['label']): continue
            for t in g['tasks'] + [dict(id=etc_id(gi), name=ETC_NAME)]:
                sel = sorted([d for d in docs if d['task_id'] == t['id']], key=lambda x: (x['date'], x['num']))
                print(f"\n### [{g['label']}] {t['name']} ({len(sel)})")
                for d in sel: print(f"  {d['id']:>10s} {d['date'][5:]} {'*' if d['task_src']=='unmatched' else ' '} {d['title']}")


if __name__ == '__main__':
    main()
