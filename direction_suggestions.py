"""Conservative, local-first job-direction hints from resume text.

These hints are not an eligibility decision or a semantic skills assessment.
Every displayed evidence line is copied from the supplied resume.
"""

from __future__ import annotations

import hashlib
import re

from job_agent import CandidateProfile


# Exploration presets, never evidence of education, skills, or eligibility.
ROLE_FAMILIES = (
    {"id": "computing", "label": "计算机与软件", "roles": ["Software Developer Co-op", "QA Analyst Co-op", "IT Support Co-op"]},
    {"id": "data", "label": "数据、数学与统计", "roles": ["Data Analyst Co-op", "Business Intelligence Co-op", "Data Engineering Co-op"]},
    {"id": "finance", "label": "金融", "roles": ["Financial Analyst Co-op", "Risk Analyst Co-op", "Investment Analyst Co-op"]},
    {"id": "engineering", "label": "工程与技术", "roles": ["Engineering Co-op", "Quality Engineering Co-op", "Technical Support Co-op"]},
    {"id": "design", "label": "设计与产品", "roles": ["UX Design Co-op", "Product Design Co-op", "Product Management Co-op"]},
    {"id": "science", "label": "自然科学与生命科学", "roles": ["Research Assistant Co-op", "Laboratory Assistant Co-op", "Environmental Science Co-op"]},
    {"id": "humanities", "label": "人文、社会科学与传播", "roles": ["Communications Co-op", "Policy Research Co-op", "Community Programs Co-op"]},
)


def get_role_family(family_id: object) -> dict | None:
    """Resolve an explicit exploration choice without inferring qualifications."""
    if family_id == "":
        return None
    if isinstance(family_id, str):
        for family in ROLE_FAMILIES:
            if family["id"] == family_id:
                return {**family, "roles": list(family["roles"])}
    raise ValueError("Unknown exploration category. Choose a listed category or leave it undecided.")


ROLE_SIGNALS = (
    ("Data Analyst Co-op", (
        r"\bsql\b", r"\bpython\b", r"\bexcel\b", r"data analy[sz]",
        r"data clean", r"\bstatistics?\b", r"\bpandas\b",
    )),
    ("Business Intelligence Co-op", (
        r"power\s*bi", r"\btableau\b", r"\bdashboards?\b",
        r"\breport(?:s|ing)?\b", r"data visuali[sz]",
    )),
    ("Data Operations Co-op", (
        r"data clean", r"data validat", r"data quality", r"quality checks?",
        r"\bspreadsheets?\b", r"\bexcel\b", r"documented validation",
    )),
    ("Data Engineering Co-op", (
        r"\betl\b", r"data pipelines?", r"data warehouses?",
        r"\bdbt\b", r"\bairflow\b", r"\bspark\b",
    )),
    ("Software Developer Co-op", (
        r"\bjavascript\b", r"\btypescript\b", r"\breact\b",
        r"\bapi\b", r"\bunit tests?\b", r"software develop",
    )),
)


def resume_fingerprint(resume: str) -> str:
    return hashlib.sha256(resume.encode("utf-8")).hexdigest()


def suggest_directions(resume: str) -> list[dict[str, object]]:
    """Return at most three role families with two distinct resume signals each."""
    lines = [line.strip() for line in resume.splitlines() if line.strip()]
    candidates: list[tuple[int, int, dict[str, object]]] = []
    for order, (role, signals) in enumerate(ROLE_SIGNALS):
        evidence: list[str] = []
        matched = 0
        for signal in signals:
            source_line = next((line for line in lines if re.search(signal, line, re.IGNORECASE)), None)
            if source_line is None:
                continue
            matched += 1
            if source_line not in evidence and len(evidence) < 3:
                evidence.append(source_line[:240])
        if matched >= 2:
            candidates.append((-matched, order, {"role": role, "evidence": evidence}))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in candidates[:3]]


def apply_confirmed_directions(profile: CandidateProfile, data: dict, resume: str) -> CandidateProfile:
    """Use explicitly confirmed target roles only for the matching resume."""
    if "confirmed_roles" not in data:
        return profile
    roles = data["confirmed_roles"]
    if not isinstance(roles, list) or len(roles) > 5 or any(
        not isinstance(role, str) or not role.strip() or len(role.strip()) > 100 or "\n" in role
        for role in roles
    ):
        raise ValueError("Choose at most five non-empty job directions (100 characters each).")
    cleaned = [role.strip() for role in roles]
    if len({role.casefold() for role in cleaned}) != len(cleaned):
        raise ValueError("Job directions must not repeat.")
    if data.get("direction_fingerprint") != resume_fingerprint(resume):
        raise ValueError("Resume changed after direction confirmation. Review directions again.")
    updated = profile.model_copy(deep=True)
    updated.preferences.target_roles = cleaned
    return updated
