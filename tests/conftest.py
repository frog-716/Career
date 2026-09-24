"""Allow unit tests to use TestClient's synthetic host name."""
import os


os.environ.setdefault("CAREER_TEST_MODE", "1")
# Existing unit tests explicitly inject TestProvider or exercise an explicit
# fake provider. Keep that test harness opt-in separate from production, whose
# missing/invalid mode remains fail-closed LOCAL_ONLY.
os.environ.setdefault("CAREER_AI_MODE", "AI_ENABLED")
