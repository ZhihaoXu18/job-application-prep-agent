"""Bounded, bilingual résumé evidence drafts; local heuristics, not verified skills.

Quotes retain exact character offsets. Review edits are session-only annotations;
they are never promoted into the application profile or submitted to a model.
"""

from __future__ import annotations

import hashlib
import re


KINDS = {
    "practice": "实践表述（非熟练度证明）",
    "course": "课程 / 教育表述",
    "learning": "学习中 / 入门表述",
    "negated": "否定 / 缺乏经验表述",
    "mentioned": "仅提到 · 待确认",
}
SKILL_PATTERNS = (
    ("SQL", r"\bsql\b"), ("Python", r"\bpython\b"), ("Excel", r"\bexcel\b"),
    ("Statistics", r"\bstatistics?\b|统计"), ("Pandas", r"\bpandas\b"),
    ("Data analysis", r"data analy[sz]|数据分析"),
    ("Data cleaning", r"data clean|数据清洗"),
    ("Power BI", r"power\s*bi"), ("Tableau", r"\btableau\b"),
    ("Dashboards", r"\bdashboards?\b|仪表盘"),
    ("Reporting", r"\breport(?:s|ing)?\b|报表"),
    ("Data visualization", r"data visuali[sz]|数据可视化"),
    ("Data validation", r"data validat|validation checks?|数据验证"),
    ("Data quality", r"data quality|quality checks?|数据质量"),
    ("Spreadsheets", r"\bspreadsheets?\b|电子表格"),
    ("ETL", r"\betl\b"), ("Data pipelines", r"data pipelines?|数据管道"),
    ("Data warehouses", r"data warehouses?|数据仓库"),
    ("dbt", r"\bdbt\b"), ("Airflow", r"\bairflow\b"), ("Spark", r"\bspark\b"),
    ("JavaScript", r"\bjavascript\b"), ("TypeScript", r"\btypescript\b"),
    ("React", r"\breact\b"), ("API", r"\bapi\b"),
    ("Unit testing", r"\bunit tests?\b|单元测试"),
    ("Software development", r"software develop|软件开发"),
    ("Accounting", r"\baccounting\b|会计"),
    ("Financial statements", r"financial statements?|财务报表"),
    ("Financial modeling", r"financial model(?:l?ing)?|财务建模"),
    ("Valuation", r"\bvaluation\b|估值"),
    ("Budgeting", r"\bbudget(?:s|ing)?\b|预算"),
    ("Forecasting", r"\bforecast(?:s|ing)?\b|预测"),
    ("Risk analysis", r"risk analy[sz]|风险分析"),
)
MAX_ROWS = 40
MAX_QUOTE_CHARS = 2000
# Split contrasting claims before classification; do not split commas in numbers.
CLAUSE_BREAK = re.compile(
    r"(?<!\d),(?!\d)|[，;；。!?！？]|\.(?=\s|$)|\b(?:but|however)\b|但是|但|不过|然而",
    re.IGNORECASE,
)
NEGATIVE = re.compile(
    r"\b(?:no|not|never|without|lack(?:s|ed|ing)?|cannot)\b|"
    r"\b(?:haven|hasn|don|doesn|can|didn)['’]t\b|"
    r"不会|不熟悉|不具备|没有.{0,12}(?:经验|使用|掌握)|没用过|未使用|未掌握|尚未|缺乏",
    re.IGNORECASE,
)
LEARNING = re.compile(
    r"\b(?:learning|studying|beginner|tutorials?)\b|self[ -]study|正在学习|学习中|入门|自学",
    re.IGNORECASE,
)
COURSE = re.compile(r"\b(?:coursework|courses?|academic|curriculum)\b|课程|课堂|学校作业", re.IGNORECASE)
ACTION = re.compile(
    r"\b(?:used|built|wrote|cleaned|created|developed|analy[sz]ed|implemented|deployed|"
    r"assisted|supported|presented|prepared|designed|validated|joined)\b|"
    r"使用|利用|编写|建立|搭建|清洗|分析|开发|实现|协助|完成|制作",
    re.IGNORECASE,
)
SECTION_TYPES = {
    "experience": "experience", "work experience": "experience", "professional experience": "experience",
    "employment": "experience", "工作经历": "experience", "实习经历": "experience",
    "projects": "project", "project experience": "project", "项目": "project", "项目经历": "project",
    "education": "course", "coursework": "course", "relevant coursework": "course",
    "courses": "course", "课程": "course", "教育": "course", "教育经历": "course",
    "skills": "skills", "technical skills": "skills", "tools": "skills", "技能": "skills", "专业技能": "skills",
}


def fingerprint(resume: str) -> str:
    return hashlib.sha256(resume.encode("utf-8")).hexdigest()


def classify_fragment(quote: str, section_type: str = "") -> str:
    # Exempt the additive phrase "not only"; other negation is deliberately cautious.
    checked = re.sub(r"\bnot only\b|不仅", "", quote, flags=re.IGNORECASE)
    if NEGATIVE.search(checked):
        return "negated"
    if LEARNING.search(quote):
        return "learning"
    if COURSE.search(quote) or section_type == "course":
        return "course"
    if ACTION.search(quote):
        return "practice"
    return "mentioned"


def resume_fragments(resume: str):
    """Yield exact clauses with context and offsets, never inferred credentials."""
    offset = 0
    section = ""
    section_type = ""
    for line_number, raw in enumerate(resume.splitlines(keepends=True), 1):
        text = raw.rstrip("\r\n")
        heading = re.sub(r"^\s*#{1,6}\s*", "", text).strip().rstrip(":：").casefold()
        if heading in SECTION_TYPES:
            section, section_type = text.strip(), SECTION_TYPES[heading]
        elif re.match(r"^\s*#{1,6}\s+", text):
            section = text.strip()
        cursor = 0
        inherited_kind = ""
        for delimiter in [*CLAUSE_BREAK.finditer(text), None]:
            end = delimiter.start() if delimiter else len(text)
            fragment = text[cursor:end]
            quote = fragment.strip()
            if quote:
                start = offset + cursor + len(fragment) - len(fragment.lstrip())
                kind = classify_fragment(quote, section_type)
                if inherited_kind == "negated" and kind != "negated" and not ACTION.search(quote):
                    kind = "negated"
                elif kind == "mentioned" and inherited_kind in {"learning", "course"}:
                    kind = inherited_kind
                yield {
                    "quote": quote, "start": start, "end": start + len(quote),
                    "line": line_number, "section": section,
                    "kind": kind,
                }
                inherited_kind = kind
            if delimiter:
                cursor = delimiter.end()
                if delimiter.group().strip().casefold() not in {",", "，"}:
                    inherited_kind = ""
        offset += len(raw)


def labels_in_quote(quote: str) -> list[str]:
    return [label for label, pattern in SKILL_PATTERNS if re.search(pattern, quote, re.IGNORECASE)]


def extract_resume_evidence(resume: str) -> dict:
    rows = []
    omitted = 0
    resume_hash = fingerprint(resume)
    for fragment in resume_fragments(resume):
        labels = labels_in_quote(fragment["quote"])
        if not labels:
            continue
        if len(fragment["quote"]) > MAX_QUOTE_CHARS or len(rows) >= MAX_ROWS:
            omitted += 1
            continue
        row_id = hashlib.sha256(
            f"{resume_hash}:{fragment['start']}:{fragment['end']}".encode()
        ).hexdigest()[:16]
        rows.append({"id": row_id, **fragment, "labels": labels,
                     "included": True, "note": "", "reviewed": False})
    return {"method": "local_rules_v1", "resume_fingerprint": resume_hash,
            "kind_labels": KINDS, "evidence": rows, "omitted_fragments": omitted,
            "reviewed": False}


def review_resume_evidence(resume: str, data: dict) -> dict:
    """Rebuild source quotes, accepting annotations only on this exact draft."""
    draft = extract_resume_evidence(resume)
    if data.get("evidence_fingerprint") != draft["resume_fingerprint"]:
        raise ValueError("简历已更改，请重新整理证据并核对。")
    edits = data.get("evidence_edits")
    if not isinstance(edits, list) or len(edits) != len(draft["evidence"]):
        raise ValueError("请核对当前证据初稿中的全部条目。")
    sources = {row["id"]: row for row in draft["evidence"]}
    reviewed = []
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"id", "kind", "labels", "included", "note"}:
            raise ValueError("证据修改只能包含类型、原文支持的标签、保留状态和个人备注。")
        row_id = edit["id"]
        if not isinstance(row_id, str) or row_id not in sources or row_id in seen:
            raise ValueError("证据条目不存在或重复，请重新整理。")
        seen.add(row_id)
        original = sources[row_id]
        if resume[original["start"]:original["end"]] != original["quote"]:
            raise ValueError("证据原文位置不一致，请重新整理。")
        labels = edit["labels"]
        if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
            raise ValueError("能力标签格式无效。")
        if len(set(labels)) != len(labels) or any(label not in original["labels"] for label in labels):
            raise ValueError("只能保留原文已识别的标签；不能添加没有原文支持的能力。")
        if not isinstance(edit["kind"], str) or edit["kind"] not in KINDS:
            raise ValueError("证据类型无效。")
        if type(edit["included"]) is not bool or not isinstance(edit["note"], str) or len(edit["note"]) > 500:
            raise ValueError("保留状态或备注格式无效；备注最多 500 字符。")
        reviewed.append({**original, **edit, "reviewed": True})
    draft.update(evidence=reviewed, reviewed=True)
    return draft
