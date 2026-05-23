"""
Tale Evaluator — автоматическая проверка качества терапевтических сказок.

Анализирует сказку по ~15 параметрам: структура, содержание,
терапевтическое качество, форматирование.
"""

import hashlib
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger("tales.evaluator")

DB_PATH = Path(__file__).parent / "evaluations.db"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            total_score REAL NOT NULL,
            passed INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            warnings INTEGER NOT NULL DEFAULT 0,
            critical_count INTEGER NOT NULL DEFAULT 0,
            checks_json TEXT NOT NULL,
            notified INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT,
            eval_id INTEGER,
            category TEXT NOT NULL,
            check_name TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            fixed_at TEXT,
            pattern_hash TEXT,
            FOREIGN KEY (eval_id) REFERENCES evaluations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status);
        CREATE INDEX IF NOT EXISTS idx_rec_pattern ON recommendations(pattern_hash);
        CREATE INDEX IF NOT EXISTS idx_eval_content ON evaluations(content_id);
        CREATE INDEX IF NOT EXISTS idx_eval_created ON evaluations(created_at);
    """)
    conn.close()


class CheckResult:
    def __init__(self, name, category, passed, severity="warning", detail="", display_name=""):
        self.name = name
        self.category = category
        self.passed = passed
        self.severity = severity
        self.detail = detail
        self.display_name = display_name or name

    def to_dict(self):
        return {
            "name": self.name, "display_name": self.display_name,
            "category": self.category, "passed": self.passed,
            "severity": self.severity, "detail": self.detail,
        }


CHECK_DISPLAY_NAMES = {
    "title_exists": "Заголовок сказки",
    "story_not_empty": "Текст сказки не пустой",
    "story_length": "Длина сказки (мин. 1500 зн.)",
    "recommendations_exist": "Рекомендации для родителей",
    "questions_exist": "Вопросы для обсуждения",
    "recommendations_length": "Содержательность рекомендаций",
    "questions_length": "Содержательность вопросов",
    "no_asterisks": "Нет звёздочек (**) в тексте",
    "no_markdown": "Нет Markdown-разметки",
    "dialogue_formatting": "Диалоги с тире (—)",
    "paragraph_count": "Разбивка на абзацы (мин. 5)",
    "sensory_details": "Сенсорные детали (запахи, звуки, текстуры)",
    "emotions_present": "Эмоции героя (чувства, ощущения)",
    "no_forbidden_content": "Нет запрещённого контента",
    "no_direct_moralizing": "Нет прямого морализаторства",
    "has_dialogue": "Наличие диалогов",
}

# Sensory words to look for
SENSORY_WORDS = [
    "запах", "аромат", "пахл", "пахн", "благоуха",
    "звук", "шорох", "шёпот", "шепот", "тишин", "скрип", "журчан", "шелест", "звон", "гул", "стук",
    "тёпл", "тепл", "холод", "мягк", "шерст", "пушист", "гладк", "шершав", "бархат",
    "ярк", "сия", "блест", "свет", "тускл", "мерца", "золотист", "серебрист",
    "сладк", "горьк", "вкус",
]

EMOTION_WORDS = [
    "страх", "боял", "испуг", "тревог", "волнен", "волнова",
    "радост", "счастлив", "весел", "улыбну", "улыбка", "засмея", "смеял",
    "грусть", "грустн", "печаль", "слёз", "слез", "плака", "заплак",
    "злост", "злил", "серди", "гнев", "обид",
    "гордост", "гордил", "удивл", "удивлен",
    "стыд", "стесня", "смущ",
    "сжал", "замер", "задрож", "вздохну", "ком в горле", "сердце застучал", "сердце забил",
    "животик", "щеки", "ладошк", "кулачк",
]

FORBIDDEN_PATTERNS = [
    r"\bубил[аио]?\b", r"\bубить\b", r"\bтруп\b", r"\bгроб\b",
    r"\bпистолет", r"\bружь[её]",
    r"\bпорно", r"\bнаркотик",
]

MORALIZING_PHRASES = [
    "ты должен понять",
    "мораль этой сказки",
    "запомни, что нужно",
    "урок в том, что",
    "вот видишь, надо было",
    "нельзя так делать",
    "вот что бывает, когда",
]


def evaluate_tale(tale_data: dict) -> list[CheckResult]:
    """Run all checks on a tale JSON."""
    results = []
    title = tale_data.get("title", "")
    story = tale_data.get("story", "")
    recommendations = tale_data.get("recommendations", "")
    questions = tale_data.get("questions", "")
    story_lower = story.lower()

    # ══ STRUCTURE ══

    results.append(CheckResult(
        "title_exists", "structure",
        bool(title and len(title.strip()) > 3),
        "critical",
        f"«{title[:60]}»" if title else "Заголовок отсутствует",
        CHECK_DISPLAY_NAMES["title_exists"],
    ))

    results.append(CheckResult(
        "story_not_empty", "structure",
        len(story.strip()) > 100,
        "critical",
        f"{len(story)} символов" if story else "Текст пустой",
        CHECK_DISPLAY_NAMES["story_not_empty"],
    ))

    results.append(CheckResult(
        "story_length", "structure",
        len(story.strip()) >= 1500,
        "warning",
        f"{len(story.strip())} символов (мин. 1500)",
        CHECK_DISPLAY_NAMES["story_length"],
    ))

    results.append(CheckResult(
        "recommendations_exist", "structure",
        bool(recommendations and len(recommendations.strip()) > 10),
        "warning",
        f"{len(recommendations.strip())} символов" if recommendations else "Отсутствуют",
        CHECK_DISPLAY_NAMES["recommendations_exist"],
    ))

    results.append(CheckResult(
        "questions_exist", "structure",
        bool(questions and len(questions.strip()) > 10),
        "warning",
        f"{len(questions.strip())} символов" if questions else "Отсутствуют",
        CHECK_DISPLAY_NAMES["questions_exist"],
    ))

    if recommendations:
        results.append(CheckResult(
            "recommendations_length", "structure",
            len(recommendations.strip()) >= 50,
            "info",
            f"{len(recommendations.strip())} символов (мин. 50)",
            CHECK_DISPLAY_NAMES["recommendations_length"],
        ))

    if questions:
        results.append(CheckResult(
            "questions_length", "structure",
            len(questions.strip()) >= 30,
            "info",
            f"{len(questions.strip())} символов (мин. 30)",
            CHECK_DISPLAY_NAMES["questions_length"],
        ))

    # ══ FORMATTING ══

    results.append(CheckResult(
        "no_asterisks", "formatting",
        "**" not in story,
        "warning",
        "Найдены ** в тексте" if "**" in story else "Чисто",
        CHECK_DISPLAY_NAMES["no_asterisks"],
    ))

    has_markdown = bool(re.search(r'[_*]{1,2}\w+[_*]{1,2}|^#{1,3}\s', story, re.MULTILINE))
    results.append(CheckResult(
        "no_markdown", "formatting",
        not has_markdown,
        "warning",
        "Найдена Markdown-разметка" if has_markdown else "Чисто",
        CHECK_DISPLAY_NAMES["no_markdown"],
    ))

    has_em_dash_dialogues = "— " in story or "—\u00a0" in story
    results.append(CheckResult(
        "dialogue_formatting", "formatting",
        has_em_dash_dialogues,
        "info",
        "Диалоги с тире (—)" if has_em_dash_dialogues else "Тире (—) не найдено в диалогах",
        CHECK_DISPLAY_NAMES["dialogue_formatting"],
    ))

    paragraphs = [p.strip() for p in story.split("\n") if p.strip()]
    results.append(CheckResult(
        "paragraph_count", "formatting",
        len(paragraphs) >= 5,
        "warning",
        f"{len(paragraphs)} абзацев",
        CHECK_DISPLAY_NAMES["paragraph_count"],
    ))

    has_dialogue = bool(re.search(r'—\s', story))
    results.append(CheckResult(
        "has_dialogue", "formatting",
        has_dialogue,
        "info",
        "Есть диалоги" if has_dialogue else "Диалогов нет",
        CHECK_DISPLAY_NAMES["has_dialogue"],
    ))

    # ══ THERAPEUTIC QUALITY ══

    sensory_found = [w for w in SENSORY_WORDS if w in story_lower]
    results.append(CheckResult(
        "sensory_details", "therapeutic",
        len(sensory_found) >= 3,
        "info",
        f"Найдено {len(sensory_found)} сенсорных слов: {', '.join(sensory_found[:5])}",
        CHECK_DISPLAY_NAMES["sensory_details"],
    ))

    emotions_found = [w for w in EMOTION_WORDS if w in story_lower]
    results.append(CheckResult(
        "emotions_present", "therapeutic",
        len(emotions_found) >= 3,
        "warning",
        f"Найдено {len(emotions_found)} эмоц. слов: {', '.join(emotions_found[:5])}",
        CHECK_DISPLAY_NAMES["emotions_present"],
    ))

    forbidden_found = [p for p in FORBIDDEN_PATTERNS if re.search(p, story_lower)]
    results.append(CheckResult(
        "no_forbidden_content", "therapeutic",
        len(forbidden_found) == 0,
        "critical",
        f"Найдены запрещённые паттерны: {', '.join(forbidden_found)}" if forbidden_found else "Чисто",
        CHECK_DISPLAY_NAMES["no_forbidden_content"],
    ))

    moralizing_found = [p for p in MORALIZING_PHRASES if p in story_lower]
    results.append(CheckResult(
        "no_direct_moralizing", "therapeutic",
        len(moralizing_found) == 0,
        "warning",
        f"Найдено морализаторство: {', '.join(moralizing_found)}" if moralizing_found else "Чисто",
        CHECK_DISPLAY_NAMES["no_direct_moralizing"],
    ))

    return results


# ── Scoring ──

def score_results(results):
    if not results:
        return 0.0, 0, 0, 0
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    critical = sum(1 for r in results if not r.passed and r.severity == "critical")
    score = (passed / len(results)) * 100
    score = max(0, score - critical * 5)
    return round(score, 1), passed, failed, critical


# ── Persistence ──

def save_evaluation(content_id, results):
    score, passed, failed, critical = score_results(results)
    warnings = sum(1 for r in results if not r.passed and r.severity == "warning")
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO evaluations
           (content_id, total_score, passed, failed, warnings, critical_count, checks_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (content_id, score, passed, failed, warnings, critical,
         json.dumps([r.to_dict() for r in results], ensure_ascii=False))
    )
    eval_id = cur.lastrowid

    for r in results:
        if r.passed:
            continue
        pattern_hash = hashlib.md5(f"{r.name}:{r.detail}".encode()).hexdigest()[:12]
        existing = conn.execute(
            "SELECT id, status FROM recommendations WHERE pattern_hash = ? AND status IN ('fixed','archived') ORDER BY id DESC LIMIT 1",
            (pattern_hash,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE recommendations SET status='reopened', content_id=?, eval_id=?, created_at=datetime('now') WHERE id=?",
                (content_id, eval_id, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO recommendations (content_id, eval_id, category, check_name, description, severity, pattern_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (content_id, eval_id, r.category, r.name, r.detail, r.severity, pattern_hash)
            )
    conn.commit()
    conn.close()
    return eval_id


def notify_telegram(content_id, results, bot_token, chat_id, server_url):
    critical = [r for r in results if not r.passed and r.severity == "critical"]
    if not critical or not bot_token or not chat_id:
        return
    score, passed, failed, _ = score_results(results)
    lines = [
        f"⚠️ <b>Сказка {content_id}</b> — оценка <b>{score}/100</b> ({passed}/{passed+failed})",
        f"🔗 {server_url}/tale/{content_id}",
        "",
    ]
    for r in critical:
        lines.append(f"❌ <b>{r.display_name}</b>")
        lines.append(f"    {r.detail}")
    warns = [r for r in results if not r.passed and r.severity == "warning"]
    if warns:
        lines.append(f"\n⚠️ + {len(warns)} предупреждений")
    try:
        httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        logger.exception("Failed to send eval notification")


def run_evaluation(content_id, tale_data, bot_token="", chat_id="", server_url=""):
    results = evaluate_tale(tale_data)
    score, passed, failed, critical = score_results(results)
    eval_id = save_evaluation(content_id, results)
    if critical > 0:
        notify_telegram(content_id, results, bot_token, chat_id, server_url)
    return {"eval_id": eval_id, "score": score, "passed": passed, "failed": failed, "critical": critical}


# ── Query helpers ──

def get_recent_evaluations(limit=50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, content_id, created_at, total_score, passed, failed, warnings, critical_count FROM evaluations ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_evaluation_by_content(content_id):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM evaluations WHERE content_id = ? ORDER BY id DESC LIMIT 1", (content_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_recommendations(status_filter="open"):
    conn = _get_conn()
    if status_filter == "all":
        rows = conn.execute("SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 200").fetchall()
    else:
        rows = conn.execute("SELECT * FROM recommendations WHERE status = ? ORDER BY created_at DESC LIMIT 200", (status_filter,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_recommendation_status(rec_id, new_status):
    conn = _get_conn()
    fixed_at = datetime.now().isoformat() if new_status in ("fixed", "archived") else None
    conn.execute("UPDATE recommendations SET status = ?, fixed_at = ? WHERE id = ?", (new_status, fixed_at, rec_id))
    conn.commit()
    conn.close()
    return True

def get_stats_summary():
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
    avg_score = conn.execute("SELECT COALESCE(AVG(total_score), 0) FROM evaluations").fetchone()[0]
    total_critical = conn.execute("SELECT COALESCE(SUM(critical_count), 0) FROM evaluations").fetchone()[0]
    perfect = conn.execute("SELECT COUNT(*) FROM evaluations WHERE critical_count = 0 AND failed = 0").fetchone()[0]
    open_recs = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status IN ('open','reopened')").fetchone()[0]

    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for r in conn.execute("SELECT total_score FROM evaluations").fetchall():
        s = r[0]
        if s <= 20: buckets["0-20"] += 1
        elif s <= 40: buckets["21-40"] += 1
        elif s <= 60: buckets["41-60"] += 1
        elif s <= 80: buckets["61-80"] += 1
        else: buckets["81-100"] += 1

    daily = conn.execute(
        "SELECT DATE(created_at) as day, AVG(total_score) as avg_score, COUNT(*) as cnt FROM evaluations WHERE created_at >= datetime('now', '-30 days') GROUP BY DATE(created_at) ORDER BY day"
    ).fetchall()

    common_fails = conn.execute(
        "SELECT check_name, COUNT(*) as cnt FROM recommendations WHERE status IN ('open','reopened') GROUP BY check_name ORDER BY cnt DESC LIMIT 10"
    ).fetchall()

    conn.close()
    return {
        "total_lessons": total,
        "avg_score": round(avg_score, 1),
        "total_critical": total_critical,
        "perfect_lessons": perfect,
        "open_recommendations": open_recs,
        "score_distribution": buckets,
        "daily_scores": [{"day": d[0], "avg": round(d[1], 1), "count": d[2]} for d in daily],
        "common_failures": [{"check": f[0], "count": f[1]} for f in common_fails],
    }
