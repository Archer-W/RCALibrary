from rcalibrary.deps import get_solution_registry
from rcalibrary.solutions.base import RunRequest


def test_three_levels_with_availability():
    infos = [s.info() for s in get_solution_registry().all()]
    assert [i.level for i in infos] == [1, 2, 3]
    assert infos[0].status == "available"
    assert infos[1].status == "coming_soon"
    assert infos[2].status == "coming_soon"


def test_placeholders_return_not_implemented_without_raising():
    registry = get_solution_registry()
    for level in (2, 3):
        result = registry.get(level).run(RunRequest(problem="x"))
        assert result.status == "not_implemented"
        assert result.report is None
