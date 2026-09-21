from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_resume_workspace_is_the_only_normal_editor_entry():
    sources = {
        path.relative_to(FRONTEND / "src").as_posix(): path.read_text(encoding="utf-8")
        for path in (FRONTEND / "src").rglob("*")
        if path.suffix in {".ts", ".js"}
    }
    formal_sources = {
        name: content
        for name, content in sources.items()
        if name != "editor/legacy-entry.ts"
    }
    assert all("/editor.html?" not in content for content in formal_sources.values())
    assert "/#resume?document_id=" in sources["opportunity-ui.ts"]
    assert "data-resume-editor-host" in sources["resume-workspace.ts"]
    assert 'id="previewPdf"' in sources["resume-workspace.ts"]
    assert "pdf-preview-dialog" in sources["editor/legacy-app.js"]


def test_legacy_editor_is_mounted_once_and_editor_html_only_redirects():
    legacy_app = (FRONTEND / "src/editor/legacy-app.js").read_text(encoding="utf-8")
    workspace = (FRONTEND / "src/resume-workspace.ts").read_text(encoding="utf-8")
    entry = (FRONTEND / "src/editor/legacy-entry.ts").read_text(encoding="utf-8")
    editor_html = (FRONTEND / "editor.html").read_text(encoding="utf-8")

    assert "export async function mountResumeEditor" in legacy_app
    assert 'import("./editor/legacy-app.js")' in workspace
    assert "legacy-app.js" not in entry
    assert "#resume" in entry and "location.replace" in entry
    assert 'id="paper"' not in editor_html


def test_workspace_navigation_participates_in_editor_dirty_guard():
    main = (FRONTEND / "src/main.ts").read_text(encoding="utf-8")
    editor = (FRONTEND / "src/editor/legacy-app.js").read_text(encoding="utf-8")
    assert "resumeEditorController?.hasUnsavedChanges()" in main
    assert "await resumeEditorController.requestClose()" in main
    assert "resumeTargetChanged" in main
    assert 'page === "resume" && resumeEditorController' in main
    assert "legacyResumePage" not in main
    assert "resumeBuffers" not in main
    assert "当前简历尚未保存" in editor
    assert "放弃未保存内容并离开" in editor
    assert "await fetchPdf(`${editorBase}/pdf`" in editor
    assert "URL.createObjectURL" in editor
