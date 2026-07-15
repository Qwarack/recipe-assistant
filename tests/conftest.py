from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load_fixture(relative_path: str) -> str:
        fixture_path = FIXTURES_PATH / relative_path

        return fixture_path.read_text(encoding="utf-8")

    return _load_fixture
