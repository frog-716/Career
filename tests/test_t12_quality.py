"""T12 quality gates; these assertions are deliberately about repository contracts."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_t12_frontend_domain_contracts_are_explicit_and_not_open_any():
    contracts = (FRONTEND / "contracts.ts").read_text(encoding="utf-8")
    assert "export interface Opportunity" in contracts
    assert "export interface ResearchItem" in contracts
    assert "export interface InterviewSession" in contracts
    assert "export interface ResumeDocument" in contracts
    assert "Record<string, any>" not in contracts
    assert ": any" not in contracts

    for name in ("main.ts", "opportunity-ui.ts", "interview-ui.ts", "knowledge-ui.ts"):
        source = (FRONTEND / name).read_text(encoding="utf-8")
        assert "Promise<any>" not in source, name
    assert "<T = Obj>" in (FRONTEND / "main.ts").read_text(encoding="utf-8")
    assert "<T = Row>" in (FRONTEND / "opportunity-ui.ts").read_text(encoding="utf-8")
    assert "<T = Row>" in (FRONTEND / "interview-ui.ts").read_text(encoding="utf-8")


def test_t12_has_local_checks_browser_entry_fixture_and_minimal_ci():
    assert (ROOT / "scripts" / "review_checks.py").exists()
    assert (ROOT / "scripts" / "browser_regression.py").exists()
    assert (ROOT / "tests" / "fixtures" / "t12_browser_fixture.json").exists()
    assert (ROOT / ".github" / "workflows" / "quality.yml").exists()


def test_t12_regression_matrix_points_to_real_tests():
    matrix = (ROOT / "docs" / "execution" / "REGRESSION-MATRIX.md").read_text(encoding="utf-8")
    for requirement in ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09", "R10", "R11", "R12", "R13", "R14", "R15", "R16", "R17", "R18"):
        assert f"| {requirement} |" in matrix
    assert "unit" in matrix
    assert "API integration" in matrix
    assert "browser" in matrix
    assert "platform" in matrix
    assert "real-provider" in matrix


def test_t12_touched_domains_use_public_cross_module_helpers():
    resume = (ROOT / "src" / "workbench" / "resume_documents.py").read_text(encoding="utf-8")
    pdf = (ROOT / "src" / "workbench" / "resume_pdf.py").read_text(encoding="utf-8")
    profile = (ROOT / "src" / "workbench" / "profile.py").read_text(encoding="utf-8")
    interview = (ROOT / "src" / "workbench" / "interview.py").read_text(encoding="utf-8")
    assert "from .editor import _" not in resume
    assert "from .editor import _" not in pdf
    assert "from .knowledge import _" not in profile
    assert "communication import _owned" not in interview


def test_t12_status_has_current_summary_before_historical_batches():
    status = (ROOT / "docs" / "execution" / "STATUS.md").read_text(encoding="utf-8")
    assert status.index("## 当前源码/运行身份") < status.index("## Career Review 稳定化：T00")
    assert "T12" in status[:2000]
