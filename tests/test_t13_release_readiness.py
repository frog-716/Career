"""T13 isolated release-readiness invariants over synthetic/local artifacts."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from workbench.app import create_app
from workbench.core import APP_VERSION
from workbench.core import Store
from workbench.local_runtime import DEFAULT_BUILD_ID
from workbench.providers import TestProvider


ROOT = Path(__file__).parents[1]


def test_final_runtime_identity_is_consistent_across_backend_and_frontend():
    frontend_request = (ROOT / "frontend" / "src" / "local-request.ts").read_text(encoding="utf-8")

    assert DEFAULT_BUILD_ID == f"career-{APP_VERSION}"
    assert f'CLIENT_BUILD_ID = "{DEFAULT_BUILD_ID}"' in frontend_request
    assert "schema_version=6" in (ROOT / "src" / "workbench" / "app.py").read_text(encoding="utf-8")


def test_isolated_health_reports_the_same_build_identity(tmp_path):
    app = create_app(Store(tmp_path / "data", TestProvider()))
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "build_id": DEFAULT_BUILD_ID}
    assert response.headers["x-career-build-id"] == DEFAULT_BUILD_ID


def test_isolated_browser_and_quality_entries_cannot_default_to_production():
    browser = (ROOT / "scripts" / "browser_regression.py").read_text(encoding="utf-8")
    checks = (ROOT / "scripts" / "review_checks.py").read_text(encoding="utf-8")

    assert "TestProvider()" in browser
    assert "tempfile.mkdtemp" in browser
    assert 'os.environ["CAREER_TEST_MODE"] = "1"' in browser
    assert "if not loopback(base_url)" in browser
    assert "/Users/frog/Library/Application Support/Career Data" not in browser
    assert "cwd=ROOT" in checks
    assert "python scripts/review_checks.py" not in checks


def test_t12_security_gate_and_pdf_docs_match_current_implementation():
    security_tests = (ROOT / "tests" / "test_t12_1_dependency_security.py").read_text(encoding="utf-8")
    frontend_readme = (ROOT / "frontend" / "README.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs" / "03-architecture.md").read_text(encoding="utf-8")
    status = (ROOT / "docs" / "execution" / "STATUS.md").read_text(encoding="utf-8")

    assert "malformed_host" in security_tests
    assert "range_requests" in security_tests
    assert "html2canvas/jsPDF 图片式渲染" not in frontend_readme
    assert "html2canvas/jsPDF单页图片式PDF" not in architecture
    for advisory in (
        "PYSEC-2026-1941",
        "PYSEC-2026-1942",
        "PYSEC-2026-161",
        "PYSEC-2026-2281",
        "PYSEC-2026-2280",
        "PYSEC-2026-249",
        "PYSEC-2026-248",
    ):
        assert advisory in status


def test_release_readiness_does_not_claim_acceptance_or_production_cutover():
    status = (ROOT / "docs" / "execution" / "STATUS.md").read_text(encoding="utf-8")

    assert "PRODUCTION_AUTHORIZATION_REQUIRED" in status
    assert "T13：`DEPLOYED_VERIFIED`" not in status[:2500]
    assert re.search(r"真实 Provider.*未", status[:2500])
