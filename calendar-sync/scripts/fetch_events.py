#!/usr/bin/env python3
from __future__ import annotations
import argparse
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

JST = timezone(timedelta(hours=9))
JP_WEEKDAYS = "月火水木金土日"
ZEN_TO_HALF = str.maketrans("０１２３４５６７８９．／：－", "0123456789./:-")
DATE_PATTERNS = [
    re.compile(r"(?P<year>20\d{2})\s*[年./-]\s*(?P<month>\d{1,2})\s*[月./-]\s*(?P<day>\d{1,2})\s*日?"),
    re.compile(r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"),
    re.compile(r"(?P<month>\d{1,2})/(?P<day>\d{1,2})"),
]
TIME_RANGE_PATTERNS = [
    re.compile(
        r"(?:開催時間|開会時刻|時間|例会)\s*[：:]?\s*"
        r"(?P<sh>\d{1,2})\s*[：:]\s*(?P<sm>\d{2})\s*[〜～~\-]\s*"
        r"(?P<eh>\d{1,2})\s*[：:]\s*(?P<em>\d{2})"
    ),
    re.compile(
        r"(?P<sh>\d{1,2})\s*[：:]\s*(?P<sm>\d{2})\s*[〜～~\-]\s*"
        r"(?P<eh>\d{1,2})\s*[：:]\s*(?P<em>\d{2})"
    ),
    re.compile(r"(?P<sh>\d{1,2})\s*[〜～~\-]\s*(?P<eh>\d{1,2})\s*時"),
]
POSITIVE_WORDS = ("例会", "日程", "開催", "今後", "スケジュール", "案内", "第")
NEGATIVE_WORDS = ("締切", "〆切", "キャンセル", "受付締切", "申込締切", "News", "お知らせ", "投稿日")
LINE_SKIP_WORDS = ("締切", "〆切", "キャンセル", "受付〆切", "受付締切", "申込締切", "期限", "まで", "PR", "ブース")


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.lines: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip:
            return
        text = re.sub(r"\s+", " ", html.unescape(data).translate(ZEN_TO_HALF)).strip()
        if text:
            self.lines.append(text)


@dataclass(frozen=True)
class Candidate:
    event_date: date
    score: int
    context: str
    raw_date: str


def fetch_url(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ShuseiCalendarBot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as res:
        data = res.read()
        encoding = res.headers.get_content_charset() or "utf-8"
    return data.decode(encoding, "ignore")


def html_to_lines(source: str) -> list[str]:
    parser = VisibleTextParser()
    parser.feed(source)
    return parser.lines


def infer_year(month: int, day: int, base: date) -> int:
    guessed = date(base.year, month, day)
    if guessed < base - timedelta(days=45):
        return base.year + 1
    return base.year


def parse_date_match(match: re.Match[str], base: date) -> date | None:
    try:
        year = int(match.groupdict().get("year") or infer_year(int(match.group("month")), int(match.group("day")), base))
        return date(year, int(match.group("month")), int(match.group("day")))
    except ValueError:
        return None


def score_context(context: str, raw_date: str) -> int:
    score = 0
    for word in POSITIVE_WORDS:
        if word in context:
            score += 2
    for word in NEGATIVE_WORDS:
        if word in context:
            score -= 5
    if re.search(r"第\s*\d+\s*回", context):
        score += 4
    if "日程" in context and raw_date in context:
        score += 4
    if "開催" in context and raw_date in context:
        score += 3
    if any(word in raw_date for word in LINE_SKIP_WORDS):
        score -= 10
    return score


def collect_candidates(lines: list[str], base: date) -> list[Candidate]:
    candidates: list[Candidate] = []
    for index, line in enumerate(lines):
        if any(word in line for word in LINE_SKIP_WORDS):
            continue
        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(line):
                label_window = "".join(lines[max(0, index - 2) : index + 1]).replace(" ", "")
                if any(word in label_window for word in ("申込期限", "申込期日", "申込締切", "受付締切", "締切", "〆切", "キャンセル")):
                    continue
                if "year" not in match.groupdict() and match.start() > 0 and line[match.start() - 1] in "年.\/-":
                    continue
                event_date = parse_date_match(match, base)
                if not event_date or event_date < base:
                    continue
                window = lines[max(0, index - 4) : min(len(lines), index + 7)]
                context = "\n".join(window)
                raw_date = match.group(0)
                score = score_context(context, raw_date)
                if score > -4:
                    candidates.append(Candidate(event_date, score, context, raw_date))
    return candidates


def unique_candidates(candidates: Iterable[Candidate]) -> list[Candidate]:
    best: dict[date, Candidate] = {}
    for candidate in candidates:
        current = best.get(candidate.event_date)
        if current is None or candidate.score > current.score or len(candidate.context) > len(current.context):
            best[candidate.event_date] = candidate
    return sorted(best.values(), key=lambda item: (item.event_date, -item.score))


def parse_clock(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def extract_time_range(context: str, default_start: str, default_end: str) -> tuple[time, time]:
    normalized = context.replace("：", ":")
    for pattern in TIME_RANGE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        sh = int(match.group("sh"))
        sm = int(match.groupdict().get("sm") or 0)
        eh = int(match.group("eh"))
        em = int(match.groupdict().get("em") or 0)
        if 0 <= sh < 24 and 0 <= eh < 24:
            return time(sh, sm), time(eh, em)
    return parse_clock(default_start), parse_clock(default_end)


def clean_location(value: str) -> str:
    value = value.replace(" HPは", "").replace(":HPは", "").strip(" ・:")
    if not value or value == "MAP":
        return ""
    if any(word in value for word in ("駐車場", "締切", "キャンセル", "開催です", "お知らせ", "同じ", "階が違います")):
        return ""
    if re.search(r"20\d{2}年|\d{1,2}月\d{1,2}日|第\s*\d+\s*回", value):
        return ""
    if len(value) > 42:
        return ""
    return value


def extract_location(context: str) -> str:
    lines = [line.strip(" ・") for line in context.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line in {"会場", "開催場所", "場所"} and index + 1 < len(lines):
            location = clean_location(lines[index + 1])
            if location:
                return location
        if line.startswith(("会場", "開催場所", "場所")) and len(line) > 3:
            location = clean_location(re.sub(r"^(会場|開催場所|場所)\s*[：:]?", "", line))
            if location:
                return location
    for line in lines:
        if "ホテル" in line or "会館" in line or "レストラン" in line or "モノリス" in line:
            location = clean_location(line)
            if location:
                return location
    return ""


def make_uid(venue_name: str, event_date: date, source_url: str) -> str:
    raw = f"{venue_name}|{event_date.isoformat()}|{source_url}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest() + "@shusei-hyogo-calendar"


def build_event(venue: dict, candidate: Candidate) -> dict:
    start_clock, end_clock = extract_time_range(candidate.context, venue["defaultStart"], venue["defaultEnd"])
    starts_at = datetime.combine(candidate.event_date, start_clock, JST)
    ends_at = datetime.combine(candidate.event_date, end_clock, JST)
    if ends_at <= starts_at:
        ends_at = starts_at + timedelta(hours=3)
    return {
        "id": make_uid(venue["name"], candidate.event_date, venue["url"]),
        "venue": venue["name"],
        "area": venue.get("area", ""),
        "title": f"守成クラブ{venue['name']} 例会",
        "date": candidate.event_date.isoformat(),
        "startsAt": starts_at.isoformat(),
        "endsAt": ends_at.isoformat(),
        "location": extract_location(candidate.context),
        "sourceUrl": venue["url"],
        "confidence": max(0, min(100, 55 + candidate.score * 5)),
        "sourceText": " / ".join(candidate.context.splitlines()[:8]),
    }


def scrape(config: dict, base: date, include_future_count: int) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    errors: list[dict] = []
    for venue in config["venues"]:
        try:
            lines = html_to_lines(fetch_url(venue["url"]))
            candidates = unique_candidates(collect_candidates(lines, base))
            picked = candidates[:include_future_count]
            for candidate in picked:
                events.append(build_event(venue, candidate))
            if not picked:
                errors.append({"venue": venue["name"], "url": venue["url"], "error": "日程候補を抽出できませんでした"})
        except (urllib.error.URLError, TimeoutError, UnicodeError, OSError) as exc:
            errors.append({"venue": venue["name"], "url": venue["url"], "error": str(exc)})
    return sorted(events, key=lambda item: (item["startsAt"], item["venue"])), errors


def escape_ics(value: str) -> str:
    return value.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def fold_ics_line(line: str) -> str:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            parts.append(current)
            current = " " + char
        else:
            current += char
    parts.append(current)
    return "\r\n".join(parts)


def write_ics(events: list[dict], path: Path, calendar_name: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Shusei Hyogo Calendar//JP",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics(calendar_name)}",
        "X-WR-TIMEZONE:Asia/Tokyo",
    ]
    for event in events:
        starts = datetime.fromisoformat(event["startsAt"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ends = datetime.fromisoformat(event["endsAt"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        description = f"出典: {event['sourceUrl']}\\n抽出元: {event.get('sourceText', '')}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['id']}",
                f"DTSTAMP:{now}",
                f"DTSTART:{starts}",
                f"DTEND:{ends}",
                f"SUMMARY:{escape_ics(event['title'])}",
                f"LOCATION:{escape_ics(event.get('location', ''))}",
                f"DESCRIPTION:{escape_ics(description)}",
                f"URL:{event['sourceUrl']}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    path.write_text("\r\n".join(fold_ics_line(line) for line in lines) + "\r\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="守成クラブ兵庫県会場の日程を取得してJSON/ICSを生成します。")
    parser.add_argument("--config", default="config/venues.json")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--future-count", type=int, default=6, help="各会場から拾う未来日程の最大件数")
    parser.add_argument("--today", help="テスト用基準日 YYYY-MM-DD")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    config_path = (root / args.config).resolve()
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = date.fromisoformat(args.today) if args.today else datetime.now(JST).date()
    events, errors = scrape(config, base, args.future_count)
    payload = {
        "calendarName": config["calendarName"],
        "timezone": config.get("timezone", "Asia/Tokyo"),
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "sourceUpdatedAt": email.utils.format_datetime(datetime.now(JST)),
        "events": events,
        "errors": errors,
    }
    (out_dir / "events.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_ics(events, out_dir / "events.ics", config["calendarName"])
    print(f"events: {len(events)}")
    if errors:
        print(f"errors: {len(errors)}", file=sys.stderr)
        for error in errors:
            print(f"- {error['venue']}: {error['error']}", file=sys.stderr)
    return 0 if events else 1


if __name__ == "__main__":
    raise SystemExit(main())
