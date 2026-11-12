"""접수함 폴더의 원문을 모두 읽어 하자대장.csv로 저장한다. 사용: python run.py"""
import csv
import sys
from collections import Counter
from pathlib import Path

import ai
import rules

BASE = Path(__file__).parent
접수함 = BASE / "data" / "접수함"
대장경로 = BASE / "data" / "하자대장.csv"

항목 = ["접수번호", "접수일", "원문파일", "위치", "공종", "하자내용", "긴급도", "조치기한",
        "공사번호", "시공업체", "준공일", "보증만료일", "보증판정", "책임구분", "상태", "비고"]


def 행만들기(파일, 결과, 순번, 공사목록):
    """AI가 정리한 결과 + 코드 규칙 → 대장 1행(dict)."""
    접수일, 위치, 공종, 긴급도 = 결과["접수일"], 결과["위치"], 결과["공종"], 결과["긴급도"]
    행 = {k: "" for k in 항목}
    행.update({
        "접수번호": rules.접수번호(접수일, 순번), "접수일": 접수일, "원문파일": 파일.name,
        "위치": 위치, "공종": 공종, "하자내용": 결과["하자내용"], "긴급도": 긴급도,
        "조치기한": rules.조치기한(접수일, 긴급도),
    })
    판정 = rules.판정(접수일, 위치, 공종, 공사목록)
    비고 = [판정.pop("비고")]
    행.update(판정)
    if len(결과["하자내용"]) > 40:
        비고.append("하자내용 40자 초과")
    행["비고"] = "; ".join(b for b in 비고 if b)
    행["상태"] = "확인필요" if 행["보증판정"] == rules.확인필요 else "판정완료"
    return 행


def main():
    공사목록 = rules.공사목록읽기()
    위치목록 = sorted({k["위치"] for k in 공사목록})
    순번 = Counter()  # 접수일별 순번. 같은 날은 파일명 순서대로 01, 02, ...
    행들 = []

    for 파일 in sorted(접수함.glob("*.txt")):
        근거 = ""
        try:
            결과 = ai.접수정리(파일.read_text(encoding="utf-8"), 파일.name, 위치목록)
            순번[결과["접수일"]] += 1
            행 = 행만들기(파일, 결과, 순번[결과["접수일"]], 공사목록)
            근거 = 결과.get("근거", "")
        except Exception as e:
            print(f"[오류] {파일.name}: {e}", file=sys.stderr)
            행 = {k: "" for k in 항목}
            행.update({"원문파일": 파일.name, "상태": "확인필요", "비고": f"처리 오류: {e}"})
        행들.append(행)
        print(f"{파일.name} → {행['접수번호']} {행['공종']} {행['긴급도']} {행['보증판정']} | {근거}")

    with open(대장경로, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀에서 한글 깨짐 방지
        w = csv.DictWriter(f, fieldnames=항목)
        w.writeheader()
        w.writerows(행들)
    print(f"\n{len(행들)}건 저장: {대장경로}")


if __name__ == "__main__":
    main()
