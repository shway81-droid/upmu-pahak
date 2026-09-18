#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공개 저장소에 실제 학교명·사람 이름이 들어가지 않았는지 검사한다.

이 스킬의 예시에는 학교마다 다른 값이 들어가므로 실제 값을 적을 자리가 없다.
그래서 예시는 모두 ○○ 표기로 쓴다 — `○○초등학교`, `김○○`.
한 번 공개된 뒤에는 되돌리기 어려우므로, 커밋 전에 기계가 한 번 더 본다.

이 파일에는 **실제 이름을 적지 않는다.** 이름 목록을 넣으면 그 목록 자체가
노출이 되기 때문이다. 대신 "○ 가 없는 사람 이름 자리"를 패턴으로 잡는다.

사용법:
    python scripts/check_anonymized.py            # 저장소 전체
    python scripts/check_anonymized.py 파일 …      # 특정 파일만

종료 코드: 0 = 통과, 1 = 익명화 안 된 곳 발견
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 검사 대상 확장자. 바이너리·이미지는 보지 않는다.
SUFFIXES = {".md", ".py", ".ps1", ".json", ".yml", ".yaml", ".html", ".txt"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".github"}
# 이 파일 자신은 규칙 설명에 예시가 들어가므로 건너뛴다.
SKIP_FILES = {"check_anonymized.py"}

# ── 규칙 ──────────────────────────────────────────────────────────────────
# 1) 실제 학교명. `○○초등학교`는 ○가 한글이 아니라 애초에 걸리지 않는다.
SCHOOL = re.compile(r"[가-힣]{2,10}(?:초등학교|중학교|고등학교)")

# 2) `이름 (담당 업무) -> 폴더명` 꼴 매핑 줄의 맨 앞 이름
MAPPING = re.compile(r"^\s*([가-힣○]{2,5})\s*\(.*?\)\s*->")

# 3) 폴더 경로에 담당자 이름을 쓰는 자리 (…\업무파악\<이름>\…)
PATH_SEG = re.compile(r"업무파악\\([^\\\s'\"]+)")

# 4) 설정 파일에서 사람·학교 값을 담는 키
JSON_KEYS = re.compile(
    r'"(drafters|school|school_short)"\s*:\s*(\[[^\]]*\]|"[^"]*")'
)
HANGUL = re.compile(r"[가-힣]")


def check_text(text: str):
    """(줄번호, 규칙, 안내) 목록을 돌려준다. 찾은 값 자체는 담지 않는다."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if SCHOOL.search(line):
            out.append((i, "학교명", "실제 학교명으로 보입니다. `○○초등학교` 로 바꿔 주세요."))

        m = MAPPING.match(line)
        if m and "○" not in m.group(1):
            out.append((i, "담당자 이름", "매핑 예시의 이름에 ○ 가 없습니다. `김○○` 꼴로 바꿔 주세요."))

        for seg in PATH_SEG.findall(line):
            if HANGUL.search(seg) and "○" not in seg:
                out.append((i, "경로 속 이름", "폴더 경로에 실제 이름으로 보이는 값이 있습니다. `박○○` 꼴로 바꿔 주세요."))

        for key, value in JSON_KEYS.findall(line):
            if HANGUL.search(value) and "○" not in value:
                out.append((i, f'"{key}" 값', "설정 예시에 실제 값으로 보이는 이름이 있습니다. ○○ 표기로 바꿔 주세요."))
    return out


def targets(argv):
    if argv:
        return [Path(a) for a in argv]
    found = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix not in SUFFIXES:
            continue
        if p.name in SKIP_FILES:
            continue
        if SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        found.append(p)
    return found


def main(argv):
    problems = 0
    for path in targets(argv):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            rel = str(path.resolve().relative_to(ROOT))
        except ValueError:
            rel = str(path)
        for line_no, rule, hint in check_text(text):
            print(f"{rel}:{line_no}  [{rule}] {hint}")
            problems += 1

    if problems:
        print()
        print(f"익명화가 필요한 곳 {problems}군데를 찾았습니다.")
        print("이 저장소는 공개입니다 — 커밋 전에 고쳐 주세요.")
        print("실제 값이 아니라 정상이라면 규칙을 scripts/check_anonymized.py 에서 조정하세요.")
        return 1

    print("익명화 검사 통과 — 실제 학교명·사람 이름으로 보이는 값이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
