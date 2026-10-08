"""共享合成素材与假模型输出：不是实际模型分析逻辑。"""

from pathlib import Path
from unittest.mock import Mock

from job_agent import Analysis, BulletEdit, Fact


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def html_response(
    html: str,
    *,
    url: str = "https://employer.example/jobs/123",
    content_type: str = "text/html; charset=utf-8",
    content_length: str | None = None,
) -> Mock:
    response = Mock()
    response.url = url
    response.text = html
    response.content = html.encode("utf-8")
    response.headers = {"Content-Type": content_type}
    if content_length is not None:
        response.headers["Content-Length"] = content_length
    response.raise_for_status.return_value = None
    return response


def build_test_analysis(
    term_quote: str,
    classification: str = "8_month_confirmed",
    *,
    original_bullet: str = "Built Power BI reports for a fictional campus operations dataset.",
    revised_bullet: str = "Built Power BI reports for a fictional campus operations dataset.",
) -> Analysis:
    """Build fake model output; never call job_agent.make_analysis or an API."""
    unknown = Fact(value="Not stated", source_quote="")
    return Analysis(
        employer="Northstar Analytics", title="Data Analyst Co-op", location=unknown.model_copy(),
        term=Fact(value=term_quote, source_quote=term_quote),
        start_date=unknown.model_copy(), deadline=unknown.model_copy(),
        publication_date=unknown.model_copy(), work_mode=unknown.model_copy(),
        term_classification=classification, priority="high",
        matching_points=[], gaps=[], resume_edits=[
            BulletEdit(
                original=original_bullet,
                revised=revised_bullet,
                reason="Reporting fit",
            )
        ],
        application_paragraph="", user_actions=[],
    )
