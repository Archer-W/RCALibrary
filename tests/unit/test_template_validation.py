import pytest

from rcalibrary.analyzers import default_registry
from rcalibrary.config import REPO_ROOT
from rcalibrary.errors import TemplateValidationError
from rcalibrary.workflow.loader import TemplateLoader

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "templates"


@pytest.fixture
def loader():
    return TemplateLoader(default_registry)


def test_valid_minimal_loads(loader):
    template = loader.load_file(FIXTURES / "valid_min.yaml")
    assert template.meta.id == "test.valid-min"


@pytest.mark.parametrize(
    "filename",
    ["bad_unknown_analyzer.yaml", "bad_dataset_ref.yaml", "bad_enum_no_options.yaml"],
)
def test_invalid_templates_raise(loader, filename):
    with pytest.raises(TemplateValidationError):
        loader.load_file(FIXTURES / filename)
