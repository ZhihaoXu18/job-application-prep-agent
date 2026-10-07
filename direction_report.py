"""Explainable exploration templates from user-reviewed, source-bound evidence.

These are this project's editorial examples, not employer requirements, skill
assessments, live vacancies, or estimates of hiring success. No network or writes.
"""

from direction_suggestions import get_role_family
from resume_evidence import KINDS, extract_resume_evidence, review_resume_evidence


TEMPLATE_VERSION = "2026-10-06-v1"
# Each group is one exploration topic; labels within it are alternatives, not
# requirements. Repeated labels/quotes never give extra credit within a topic.
ROLE_TEMPLATES = (
    {"id": "data-analyst", "family": "data", "role": "Data Analyst Co-op", "topics": (
        ("查询与整理数据", ("SQL", "Data cleaning", "Data validation")),
        ("分析与统计线索", ("Python", "Pandas", "Statistics", "Data analysis")),
        ("表格与结果表达", ("Excel", "Spreadsheets", "Reporting", "Data visualization")),
    )},
    {"id": "business-intelligence", "family": "data", "role": "Business Intelligence Co-op", "topics": (
        ("报表与可视化", ("Power BI", "Tableau", "Dashboards", "Data visualization")),
        ("数据查询与质量", ("SQL", "Data cleaning", "Data quality")),
        ("表格与报告", ("Excel", "Spreadsheets", "Reporting")),
    )},
    {"id": "data-engineering", "family": "data", "role": "Data Engineering Co-op", "topics": (
        ("数据管道与转换", ("ETL", "Data pipelines", "dbt")),
        ("调度与数据平台", ("Airflow", "Spark", "Data warehouses")),
        ("查询、编程与数据验证", ("SQL", "Python", "Data validation")),
    )},
    {"id": "financial-analyst", "family": "finance", "role": "Financial Analyst Co-op", "topics": (
        ("会计与财务报表", ("Accounting", "Financial statements")),
        ("预算与财务模型", ("Budgeting", "Forecasting", "Financial modeling")),
        ("表格与报告", ("Excel", "Spreadsheets", "Reporting")),
    )},
    {"id": "risk-analyst", "family": "finance", "role": "Risk Analyst Co-op", "topics": (
        ("风险分析线索", ("Risk analysis",)),
        ("统计与数据分析", ("Statistics", "Data analysis", "Python", "SQL")),
        ("数据核对与报告", ("Data validation", "Data quality", "Excel", "Reporting")),
    )},
    {"id": "investment-analyst", "family": "finance", "role": "Investment Analyst Co-op", "topics": (
        ("估值与财务模型", ("Valuation", "Financial modeling")),
        ("财务报表线索", ("Financial statements", "Accounting")),
        ("分析与结果表达", ("Excel", "Data analysis", "Reporting")),
    )},
)
STATUS_LABELS = {
    "practice": "有实践表述 · 非熟练度证明",
    "course": "只有课程 / 教育线索 · 不等于实践",
    "learning": "只有学习中线索 · 不等于实践",
    "mentioned": "仅提到或类型有分歧 · 待核对",
    "negated": "只有否定表述 · 不计为正向线索",
    "unknown": "当前证据未覆盖 · 不代表不会",
}


def effective_kind(original_kind: str, reviewed_kind: str) -> str:
    """Never upgrade recognized negation or an ambiguous type edit to practice."""
    if "negated" in {original_kind, reviewed_kind}:
        return "negated"
    if original_kind == reviewed_kind or original_kind == "practice":
        return reviewed_kind
    # Edits are annotations, not new proof of action. Keep disagreements visible.
    return "mentioned"


def build_direction_report(resume: str, data: dict) -> dict:
    family = get_role_family(data.get("role_family", ""))
    if data.get("evidence_review_confirmed") is not True:
        raise ValueError("请先逐条核对并确认本页简历证据，再生成方向报告。")
    reviewed = review_resume_evidence(resume, data)
    originals = {row["id"]: row for row in extract_resume_evidence(resume)["evidence"]}
    rows = []
    for row in reviewed["evidence"]:
        if not row["included"] or not row["labels"]:
            continue
        original_kind = originals[row["id"]]["kind"]
        kind = effective_kind(original_kind, row["kind"])
        # Private notes intentionally do not enter the report or matching.
        rows.append({key: row[key] for key in ("id", "quote", "start", "end", "line", "section", "labels")} | {
            "kind": kind, "kind_label": KINDS[kind],
            "source_kind": original_kind, "reviewed_kind": row["kind"],
            "type_disagreement": original_kind != row["kind"],
        })
    supported = family is None or family["id"] in {"data", "finance"}
    reports = []
    for template in ROLE_TEMPLATES:
        if family and template["family"] != family["id"]:
            continue
        topics = []
        counts = {key: 0 for key in STATUS_LABELS}
        for label, labels in template["topics"]:
            evidence = []
            for row in rows:
                matched = [item for item in row["labels"] if item in labels]
                if matched:
                    evidence.append({**row, "matched_labels": matched})
            # Type precedence summarizes wording only, never a qualification score.
            status = next((kind for kind in STATUS_LABELS if any(
                row["kind"] == kind for row in evidence
            )), "unknown")
            counts[status] += 1
            topics.append({"label": label, "template_labels": list(labels),
                           "status": status, "status_label": STATUS_LABELS[status],
                           "evidence": evidence})
        positive = sum(counts[kind] for kind in ("practice", "course", "learning"))
        reports.append({"id": template["id"], "family": template["family"], "role": template["role"],
                        "interest_selected": family is not None, "topics": topics, "counts": counts,
                        "summary": f"3 个探索主题中，{positive} 个有非否定且非待确认的表述线索；不是匹配率。"})
    # Stable editorial order: do not turn shared generic keywords into a ranking.
    return {"method": "reviewed_local_templates_v1", "template_version": TEMPLATE_VERSION,
            "resume_fingerprint": reviewed["resume_fingerprint"], "role_family": family,
            "supported_category": supported, "reports": reports,
            "omitted_fragments": reviewed["omitted_fragments"],
            "scope_note": "仅覆盖金融 / 数据的 6 个项目内探索模板；模板标签不是雇主要求。未覆盖不是能力缺失，兴趣不是资格，报告不搜索真实职位。",
            "ordering_note": "固定模板顺序，不计算匹配分数、录用概率或资格结论。",
            "privacy_note": "仅本页使用；下载含简历原文，请私人保管。备注不参与报告，也不发送到模型。"}
