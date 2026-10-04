"""Conservative, local-first job-direction hints from resume text.

These hints are not an eligibility decision or a semantic skills assessment.
Every displayed evidence line is copied from the supplied resume.
"""

from __future__ import annotations

import hashlib
import re

from job_agent import CandidateProfile


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
