from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (ROOT / "frontend" / "src" / "workspace.ts").read_text(encoding="utf-8")
MAIN = (ROOT / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")


def test_t15_has_only_the_four_current_first_level_modules():
    assert '"wiki", "职业 Wiki"' in WORKSPACE
    assert '"jobs", "机会"' in WORKSPACE
    assert '"resume", "简历工作台"' in WORKSPACE
    assert '"work", "任职"' in WORKSPACE
    assert '"today"' not in WORKSPACE
    assert '"今天"' not in WORKSPACE


def test_t15_uses_root_home_fallback_without_hijacking_explicit_routes():
    assert 'p === "home" || !p' in MAIN
    assert 'rawRequested === "home" || !rawRequested' in MAIN
    assert 'const requested = rawRequested === "home" || !rawRequested ? sidebarHome() : rawRequested;' in MAIN


def test_t15_navigation_contract_has_keyboard_menu_focus_and_atomic_persistence_hooks():
    assert 'event.key === "ContextMenu"' in WORKSPACE
    assert 'event.key === "F10" && event.shiftKey' in WORKSPACE
    assert 'querySelector<HTMLElement>("[data-sidebar-home]")?.focus()' in WORKSPACE
    assert 'trigger.focus()' in WORKSPACE
    assert "normalizeSidebarOrder" in WORKSPACE
    assert "writeSidebarPreferences" in WORKSPACE
    assert "restoreSidebarOrder" in WORKSPACE
