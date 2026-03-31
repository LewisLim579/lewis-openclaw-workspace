import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit(f"Missing dependency: {exc}. Install with: pip install requests beautifulsoup4")

ROOT = Path(__file__).resolve().parents[2]
MONITOR_DIR = ROOT / "monitoring"
CONFIG_PATH = MONITOR_DIR / "config.json"
STATE_PATH = MONITOR_DIR / "state.json"
REPORTS_DIR = MONITOR_DIR / "reports"

CATEGORY_RULES = [
    ("법·제도·입법", ["법", "입법", "예고", "고시", "공고", "규칙", "법령", "지침"]),
    ("정부·지자체 발표", ["보도", "브리핑", "발표", "정부", "부", "시"]),
    ("전력/가스 시장제도", ["전력시장", "smp", "lmp", "전기사업법", "직접 ppa", "분산에너지", "도시가스", "천연가스"]),
    ("LNG/LPG/수소/암모니아", ["lng", "lpg", "수소", "암모니아", "에탄", "프로판", "부탄", "벙커링", "냉열"]),
    ("데이터센터/AI 전력수요", ["ai", "인공지능", "데이터센터", "데이터 센터", "dc", "전력수요"]),
    ("탄소/배출권/RE100", ["탄소", "배출권", "re100", "rec", "rps", "ndc", "탄소중립"]),
    ("기업/산업 동향", ["sk가스", "sk어드밴스드", "석유화학", "투자", "산업", "기업"]),
    ("울산 지역 동향", ["울산"]),
]

HIGH_PRIORITY_HINTS = ["법", "입법", "예고", "고시", "공고", "규칙", "시장운영규칙", "세부운영규정"]
ALLOW_PATTERNS = {
    "assembly-bills": ["/portal/bbs/", "assembly.go.kr"],
    "nars-news": ["/news/", "/report/", "nars.go.kr"],
    "motie-admin-advance": ["/article/", "/contents/"],
    "motie-notice": ["/article/", "/contents/"],
    "motie-announcement": ["/article/", "/contents/"],
    "motie-legislation": ["/article/", "/contents/"],
    "motie-press": ["/article/", "/contents/"],
    "kpx-notice": ["act=view", "list_no="],
    "kpx-market-rules": ["act=view", "list_no="],
    "kpx-detailed-rules": ["act=view", "list_no="],
    "kpx-other-rules": ["act=view", "list_no="],
    "kogas-press": ["goBoard.do", "boardNo=41"],
    "ulsan-press": ["bbs", "ulsan"],
    "ulsan-notice": ["notice", "ulsan"],
    "kotra-news": ["dream.kotra.or.kr", "kotranews", "MENU_ID="],
    "korea-briefing": ["korea.kr", "briefing"],
    "knrec-biz": ["view.do?no="],
}
EXCLUDE_URL_PATTERNS = ["/contents/", "/menu.es", "/index.do?menuId=", "/cms/com/index.do?MENU_ID="]
NOISE_TERMS = [
    "로그인", "회원가입", "전체", "더보기", "이전", "다음", "목록", "안내", "소개", "구독", "개인정보",
    "이용약관", "고객센터", "국가상징", "정보공개제도안내", "상품권 구매현황", "nars info", "home", "사이트맵"
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_title(title: str) -> str:
    text = normalize_text(title).lower()
    return re.sub(r"[^\w\s가-힣]", "", text)


def classify_item(title: str, body: str, source_name: str):
    haystack = f"{title} {body} {source_name}".lower()
    for category, hints in CATEGORY_RULES:
        if any(h.lower() in haystack for h in hints):
            return category
    return "기업/산업 동향"


def find_matches(text: str, keywords):
    haystack = (text or "").lower()
    return sorted({keyword for keyword in keywords if keyword.lower() in haystack})


def fetch_page(url: str):
    resp = requests.get(url, headers=HEADERS, timeout=12)
    resp.raise_for_status()
    return resp.text


def extract_date(text: str):
    text = normalize_text(text)
    patterns = [r"(20\d{2}[.-]\d{1,2}[.-]\d{1,2})", r"(20\d{2}/\d{1,2}/\d{1,2})"]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).replace(".", "-").replace("/", "-")
    return None


def clean_href(base_url: str, href: str):
    href = (href or "").strip()
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return None
    return urljoin(base_url, href)


def valid_title(text: str):
    lowered = text.lower()
    if len(text) < 10:
        return False
    if any(term.lower() in lowered for term in NOISE_TERMS):
        return False
    return True


def generic_extract(base_url: str, soup: BeautifulSoup, limit_per_source: int):
    items = []
    seen = set()
    for a in soup.select("a[href]"):
        text = normalize_text(a.get_text(" ", strip=True))
        if not valid_title(text):
            continue
        href = clean_href(base_url, a.get("href"))
        if not href:
            continue
        if any(bad in href.lower() for bad in ["login", "join", "privacy", "terms"]):
            continue
        if not is_allowed_for_source("", href):
            continue
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        context = normalize_text(a.parent.get_text(" ", strip=True))
        items.append({
            "title": text,
            "url": href,
            "summary": "",
            "publishedAt": extract_date(context),
            "attachments": [],
            "body": ""
        })
        if len(items) >= limit_per_source:
            break
    return items


def table_row_extract(base_url: str, soup: BeautifulSoup, limit_per_source: int, source_id: str):
    items = []
    seen = set()
    for row in soup.select("tr"):
        links = row.select("a[href]")
        if not links:
            continue
        link = max(links, key=lambda a: len(normalize_text(a.get_text(" ", strip=True))))
        title = normalize_text(link.get_text(" ", strip=True))
        if not valid_title(title):
            continue
        href = clean_href(base_url, link.get("href"))
        if not href:
            continue
        if not is_allowed_for_source(source_id, href):
            continue
        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        row_text = normalize_text(row.get_text(" ", strip=True))
        items.append({
            "title": title,
            "url": href,
            "summary": "",
            "publishedAt": extract_date(row_text),
            "attachments": [],
            "body": ""
        })
        if len(items) >= limit_per_source:
            break
    return items


def list_item_extract(base_url: str, soup: BeautifulSoup, limit_per_source: int, source_id: str):
    items = []
    seen = set()
    selectors = ["li", ".list-item", ".board-list li", ".bbs_list li", ".card", ".news_list li"]
    for selector in selectors:
        for node in soup.select(selector):
            links = node.select("a[href]")
            if not links:
                continue
            link = max(links, key=lambda a: len(normalize_text(a.get_text(" ", strip=True))))
            title = normalize_text(link.get_text(" ", strip=True))
            if not valid_title(title):
                continue
            href = clean_href(base_url, link.get("href"))
            if not href:
                continue
            if not is_allowed_for_source(source_id, href):
                continue
            key = (title, href)
            if key in seen:
                continue
            seen.add(key)
            text = normalize_text(node.get_text(" ", strip=True))
            items.append({
                "title": title,
                "url": href,
                "summary": "",
                "publishedAt": extract_date(text),
                "attachments": [],
                "body": ""
            })
            if len(items) >= limit_per_source:
                return items
    return items


def is_allowed_for_source(source_id: str, href: str):
    href_l = href.lower()
    patterns = ALLOW_PATTERNS.get(source_id)
    if patterns:
        if not any(p.lower() in href_l for p in patterns):
            return False
    if any(p.lower() in href_l for p in EXCLUDE_URL_PATTERNS):
        if "act=view" not in href_l and "view.do?no=" not in href_l:
            return False
    return True


def extract_candidate_items(source, html: str, limit_per_source: int):
    base_url = source["url"]
    soup = BeautifulSoup(html, "html.parser")
    source_id = source["id"]

    table_first = {
        "assembly-bills", "nars-news", "moef-guidelines", "moef-notice", "moef-announcement", "moef-legislation",
        "kpx-notice", "kpx-market-rules", "kpx-detailed-rules", "kpx-other-rules", "ulsan-notice", "ulsan-press",
        "kogas-press", "kdi-law", "kdi-domestic", "kcmi-report"
    }
    list_first = {
        "motie-admin-advance", "motie-notice", "motie-announcement", "motie-legislation", "motie-press",
        "gasnews-list", "energy-news-list", "energydaily-list", "e2news-list", "eplatform-list",
        "electimes-list", "todayenergy-list", "keei-news", "korea-briefing", "kotra-news"
    }

    if source_id in table_first:
        items = table_row_extract(base_url, soup, limit_per_source, source_id)
        if items:
            return items
    if source_id in list_first:
        items = list_item_extract(base_url, soup, limit_per_source, source_id)
        if items:
            return items

    items = table_row_extract(base_url, soup, limit_per_source, source_id)
    if items:
        return items
    items = list_item_extract(base_url, soup, limit_per_source, source_id)
    if items:
        return items
    return generic_extract(base_url, soup, limit_per_source)


def fetch_detail(candidate):
    try:
        html = fetch_page(candidate["url"])
        soup = BeautifulSoup(html, "html.parser")
        texts = []
        for selector in ["article", ".view", ".content", ".board-view", ".article-view", "#content"]:
            for node in soup.select(selector):
                text = normalize_text(node.get_text(" ", strip=True))
                if len(text) > 80:
                    texts.append(text)
        if texts:
            candidate["body"] = max(texts, key=len)
        if not candidate.get("publishedAt"):
            candidate["publishedAt"] = extract_date(soup.get_text(" ", strip=True))
        attachments = []
        for a in soup.select("a[href]"):
            label = normalize_text(a.get_text(" ", strip=True))
            href = a.get("href", "")
            if label and ("pdf" in href.lower() or "download" in href.lower() or "첨부" in label):
                attachments.append(label)
        candidate["attachments"] = attachments[:10]
    except Exception:
        pass
    return candidate


def should_include(title: str, body: str, matched_keywords):
    if not matched_keywords:
        return False, "관련성 낮음"
    combined = f"{title} {body}".lower()
    hard_excludes = ["소개", "안내", "로그인", "고객센터", "구독"]
    if any(term in combined for term in hard_excludes):
        return False, "관련성 낮음"
    importance_terms = ["정책", "제도", "사업", "시장", "투자", "규제", "가격", "수급", "법", "고시", "공고", "예고", "계획", "발표", "보고서", "동향"]
    if any(term in combined for term in importance_terms):
        return True, None
    if len(matched_keywords) >= 2:
        return True, None
    return False, "단순 언급"


def make_item_id(item):
    return f"{normalize_title(item['title'])}|{item['url']}|{item.get('publishedAt') or ''}"


def build_report(run_at, included, excluded):
    lines = []
    lines.append("[모니터링 실행시각]")
    lines.append(run_at.strftime("%Y-%m-%d %H:%M"))
    lines.append("")
    lines.append("[한줄 요약]")
    top_items = included[:5]
    if top_items:
        for item in top_items:
            lines.append(f"- {item['title']} ({item['source']})")
    else:
        lines.append("- 신규 또는 중요 변경 자료 없음")
    lines.append("")
    lines.append("[상세 브리핑]")

    grouped = {}
    for item in included:
        grouped.setdefault(item["category"], []).append(item)

    if not grouped:
        lines.append("신규 또는 중요 변경 자료가 없습니다.")
    else:
        for category, items in grouped.items():
            lines.append(category)
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. {item['title']}")
                lines.append(f"- 출처: {item['source']}")
                lines.append(f"- 게시일: {item.get('publishedAt') or '미상'}")
                lines.append(f"- 매칭 키워드: {', '.join(item['matchedKeywords'])}")
                lines.append(f"- 핵심 내용: {item['summary'] or item['body'][:160] or item['title']}")
                lines.append(f"- 시사점: {item['implication']}")
                lines.append(f"- URL: {item['url']}")
                lines.append("")

    lines.append("[중요도 높음]")
    high = [item for item in included if any(h.lower() in f"{item['title']} {item['summary']} {item['body']}".lower() for h in HIGH_PRIORITY_HINTS)]
    if high:
        for item in high:
            lines.append(f"- {item['title']} | {item['source']} | {item['url']}")
    else:
        lines.append("- 해당 없음")
    lines.append("")
    lines.append("[중복/제외]")
    if excluded:
        for item in excluded[:40]:
            lines.append(f"- {item['title']} | {item['source']} | {item['reason']}")
    else:
        lines.append("- 없음")

    return "\n".join(lines).strip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", default="", help="쉼표로 그룹 필터 지정. 예: 일 1회,일 3회")
    parser.add_argument("--limit-per-source", type=int, default=5)
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    config = load_json(CONFIG_PATH)
    state = load_json(STATE_PATH)
    common = config["commonKeywords"]
    group_filter = [g.strip() for g in args.groups.split(",") if g.strip()]

    included = []
    excluded = []
    existing = {item["id"]: item for item in state.get("items", [])}

    for source in config["sources"]:
        if group_filter and source["group"] not in group_filter:
            continue
        keywords = common if source["keywords"] == "COMMON" else source["keywords"]
        try:
            html = fetch_page(source["url"])
            candidates = extract_candidate_items(source, html, args.limit_per_source)
            if not candidates:
                excluded.append({"title": source['name'], "source": source['name'], "reason": "목록 추출 실패 또는 후보 없음"})
                continue
            for candidate in candidates:
                candidate = fetch_detail(candidate)
                text_blob = " ".join([candidate["title"], candidate["summary"], candidate["body"], " ".join(candidate["attachments"])])
                matched = find_matches(text_blob, keywords)
                ok, reason = should_include(candidate["title"], candidate["body"], matched)
                candidate["source"] = source["name"]
                candidate["matchedKeywords"] = matched
                candidate["category"] = classify_item(candidate["title"], candidate["body"], source["name"])
                candidate["implication"] = "정책/시장 영향 여부를 추가 확인할 가치가 있음" if matched else "관련성 낮음"
                candidate["summary"] = candidate["summary"] or candidate["body"][:140]
                candidate["id"] = make_item_id(candidate)
                if candidate["id"] in existing:
                    excluded.append({"title": candidate["title"], "source": source["name"], "reason": "중복 기사"})
                    continue
                if ok:
                    included.append(candidate)
                    existing[candidate["id"]] = candidate
                else:
                    excluded.append({"title": candidate["title"], "source": source["name"], "reason": reason})
        except Exception as exc:
            excluded.append({"title": source['name'], "source": source['name'], "reason": f"접근 불가: {exc}"})

    run_at = datetime.now()
    report = build_report(run_at, included, excluded)
    report_path = REPORTS_DIR / f"briefing-{run_at.strftime('%Y%m%d-%H%M%S')}.md"
    report_path.write_text(report, encoding="utf-8")

    state["lastRunAt"] = run_at.isoformat()
    state["items"] = list(existing.values())[-2000:]
    save_json(STATE_PATH, state)

    safe_report = report.encode("cp949", errors="replace").decode("cp949", errors="replace")
    print(safe_report)
    print(f"\n[report saved] {report_path}")


if __name__ == "__main__":
    main()
