import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SAMPLE_WIKI = Path(__file__).resolve().parents[1] / "wiki"


@pytest.fixture
def sample_wiki():
    return SAMPLE_WIKI


@pytest.fixture
def tmp_wiki(tmp_path):
    """A minimal wiki with two linked pages and one deliberate error page."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (tmp_path / "wiki.yaml").write_text("name: t\npages_dir: pages\n", encoding="utf-8")
    (pages / "alpha.md").write_text(
        "---\n"
        "id: entity:alpha\ntitle: Alpha\ntype: entity\nslug: alpha\n"
        "status: reviewed\ntags: [x]\n"
        "sources:\n  - id: source:s1\n    uri: http://example.com\n"
        "claims:\n  - id: claim:a1\n    text: Alpha relates to beta.\n"
        "    status: reviewed\n    evidence:\n      - source_id: source:s1\n"
        "---\n\n# Alpha\n\nLinks to [[Beta]].\n",
        encoding="utf-8",
    )
    (pages / "beta.md").write_text(
        "---\n"
        "id: entity:beta\ntitle: Beta\ntype: entity\nslug: beta\nstatus: candidate\n"
        "---\n\n# Beta\n\nSee [[Alpha]].\n",
        encoding="utf-8",
    )
    return tmp_path
