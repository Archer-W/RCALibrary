def test_problems_group_templates_with_approach(client):
    problems = client.get("/api/problems").json()
    assert isinstance(problems, list) and problems

    demo = next(p for p in problems if p["id"] == "demo.generic")
    assert demo["name"] == "Generic Demo Problem"
    assert demo["domain"] == "Demo"

    tmpl = next(t for t in demo["templates"] if t["id"] == "ana.rca.generic-demo")
    assert tmpl["level"] == 1
    assert tmpl["approach_key"] == "fixed_workflow"
    assert tmpl["approach_name"] == "Fixed Workflow"
    assert tmpl["status"] == "available"


def test_template_detail_includes_problem(client):
    detail = client.get("/api/templates/ana.rca.generic-demo").json()
    assert detail["meta"]["problem"]["id"] == "demo.generic"
