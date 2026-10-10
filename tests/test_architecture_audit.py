import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import architecture_audit as audit

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tests" / "fixtures" / "architecture_duplicates.json"

SOURCE = '''
def differently_named(value):
    """A docstring must not hide a copy."""
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned.casefold()
'''


def _source(tmp_path, name, source=SOURCE):
    (tmp_path / name).write_text(source, encoding="utf-8")


def test_detects_same_nontrivial_body_across_networks(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(
        tmp_path, "threads_scan.py",
        SOURCE.replace("differently_named", "other_name")
              .replace("A docstring must not hide a copy.", "Other docs"),
    )
    report = audit.collect(tmp_path)
    assert len(report) == 1
    assert report[0]["networks"] == ["threads", "x"]
    assert report[0]["occurrences"][0]["function"] == "other_name"


def test_new_cross_network_group_breaks_budget(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    assert len(audit.regressions(audit.collect(tmp_path), [])) == 1


def test_deleting_a_copy_is_always_allowed(tmp_path):
    for name in ("x_scan.py", "threads_scan.py", "reddit_scan.py"):
        _source(tmp_path, name)
    baseline = audit.collect(tmp_path)
    (tmp_path / "reddit_scan.py").unlink()
    assert not audit.regressions(audit.collect(tmp_path), baseline)
    (tmp_path / "threads_scan.py").unlink()
    assert audit.collect(tmp_path) == []
    assert not audit.regressions(audit.collect(tmp_path), baseline)


def test_replacing_deleted_copy_does_not_recycle_budget(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    baseline = audit.collect(tmp_path)
    (tmp_path / "threads_scan.py").unlink()
    _source(tmp_path, "reddit_scan.py")
    current = audit.collect(tmp_path)
    assert len(current[0]["occurrences"]) == len(baseline[0]["occurrences"])
    failures = audit.regressions(current, baseline)
    assert len(failures) == 1
    assert [x["network"] for x in failures[0]["unbudgeted_occurrences"]] == ["reddit"]


def test_copy_growth_cannot_reuse_budget(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    baseline = audit.collect(tmp_path)
    _source(tmp_path, "reddit_scan.py")
    failures = audit.regressions(audit.collect(tmp_path), baseline)
    assert failures[0]["unbudgeted_occurrences"][0]["file"] == "reddit_scan.py"


def test_line_shifts_comments_and_docstrings_are_not_new_copies(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    baseline = audit.collect(tmp_path)
    _source(tmp_path, "threads_scan.py", "\n\n# only a comment\n" +
            SOURCE.replace("A docstring must not hide a copy.", "Fresh docstring"))
    assert not audit.regressions(audit.collect(tmp_path), baseline)


def test_trivial_function_and_same_network_only_are_ignored(tmp_path):
    _source(tmp_path, "x_scan.py", '''
def trivial():
    """docs"""
    return 1

def complex_a(value):
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned.casefold()

def complex_b(value):
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned.casefold()
''')
    _source(tmp_path, "threads_scan.py", "def trivial():\n    return 1\n")
    assert audit.collect(tmp_path) == []


def test_report_is_deterministic_and_contains_no_source_text(tmp_path):
    marker = "SYNTHETIC_PRIVATE_PAYLOAD_123"
    source = SOURCE.replace("str(value)", f"str('{marker}')")
    _source(tmp_path, "x_scan.py", source)
    _source(tmp_path, "threads_scan.py", source)
    first = audit.collect(tmp_path)
    assert first == audit.collect(tmp_path)
    encoded = json.dumps(first, sort_keys=True)
    assert marker not in encoded
    assert len(first) == 1
    assert all(len(item["fingerprint"]) == 16 for item in first)


def test_parse_errors_do_not_expose_source_text(tmp_path):
    marker = "SYNTHETIC_PRIVATE_PAYLOAD_123"
    _source(tmp_path, "x_scan.py", f"def invalid(: # {marker}\n  pass\n")
    with pytest.raises(ValueError) as err:
        audit.collect(tmp_path)
    assert marker not in str(err.value)
    assert "x_scan.py" in str(err.value)


def test_empty_or_missing_input_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="No network source"):
        audit.collect(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        audit.collect(tmp_path / "not-there")


def test_duplicate_fingerprints_cannot_inflate_baseline(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    report = audit.collect(tmp_path)
    with pytest.raises(ValueError, match="Duplicate fingerprint"):
        audit.regressions(report, report + report)


def test_additional_copy_inside_already_present_network_exceeds_budget(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    baseline = audit.collect(tmp_path)
    _source(tmp_path, "x_scan.py",
            SOURCE + "\n" + SOURCE.replace("differently_named", "fresh_copy"))
    failures = audit.regressions(audit.collect(tmp_path), baseline)
    assert len(failures) == 1
    assert failures[0]["unbudgeted_occurrences"][0]["function"] == "fresh_copy"


def test_async_function_bodies_are_detected(tmp_path):
    source = SOURCE.replace("def differently_named", "async def differently_named")
    _source(tmp_path, "x_interact.py", source)
    _source(tmp_path, "facebook_interact.py", source.replace("differently_named", "handle"))
    current = audit.collect(tmp_path)
    assert len(current) == 1
    assert current[0]["networks"] == ["facebook", "x"]


def test_cli_returns_nonzero_on_copy_and_only_prints_metadata(tmp_path, capsys):
    marker = "SYNTHETIC_PRIVATE_PAYLOAD_123"
    source = SOURCE.replace("str(value)", f"str('{marker}')")
    _source(tmp_path, "x_scan.py", source)
    _source(tmp_path, "threads_scan.py", source)
    budget = tmp_path / "baseline.json"
    budget.write_text(json.dumps(audit.collect(tmp_path)), encoding="utf-8")
    _source(tmp_path, "reddit_scan.py", source)
    assert audit.main(["--tools", str(tmp_path), "--baseline", str(budget)]) == 1
    captured = capsys.readouterr()
    assert "budget exceeded" in captured.err
    assert marker not in captured.out + captured.err
    (tmp_path / "reddit_scan.py").unlink()
    assert audit.main(["--tools", str(tmp_path), "--baseline", str(budget)]) == 0


def test_repository_does_not_add_unreviewed_cross_network_copies():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures = audit.regressions(audit.collect(ROOT / "tools"), baseline)
    assert not failures, json.dumps(failures, indent=2, sort_keys=True)


def test_repository_has_all_nine_networks_in_scope():
    paths = audit._eligible_paths(ROOT / "tools")
    assert {network for _path, network in paths} == set(audit.NETWORKS)


def _class_source(class_name):
    from textwrap import indent
    return "class " + class_name + ":\n" + indent(
        SOURCE.lstrip("\n").replace("differently_named", "check"),
        "    ",
    )


def test_class_replacement_cannot_reuse_another_class_method_budget(tmp_path):
    _source(tmp_path, "x_scan.py", _class_source("First"))
    _source(tmp_path, "threads_scan.py", _class_source("First"))
    baseline = audit.collect(tmp_path)
    assert {o["function"] for o in baseline[0]["occurrences"]} == {"First.check"}

    # Old detector treated First.check and Second.check as the same identity.
    _source(tmp_path, "x_scan.py", _class_source("Second"))
    failures = audit.regressions(audit.collect(tmp_path), baseline)
    assert len(failures) == 1
    assert failures[0]["unbudgeted_occurrences"][0]["function"] == "Second.check"


def test_nested_functions_use_lexical_identity(tmp_path):
    from textwrap import indent
    inner = SOURCE.lstrip("\n").replace("differently_named", "helper")
    first = "def outer_one():\n" + indent(inner, "    ")
    second = "def outer_two():\n" + indent(inner, "    ")
    _source(tmp_path, "x_scan.py", first)
    _source(tmp_path, "threads_scan.py", first)
    baseline = audit.collect(tmp_path)
    assert "outer_one.helper" in {o["function"] for o in baseline[0]["occurrences"]}
    _source(tmp_path, "x_scan.py", second)
    failures = audit.regressions(audit.collect(tmp_path), baseline)
    assert failures and failures[0]["unbudgeted_occurrences"][0]["function"] == "outer_two.helper"


@pytest.mark.parametrize("damage", (
    "non_list", "bad_fingerprint", "bad_occurrences", "foreign_filename",
    "unknown_network", "wrong_network_summary", "nonpositive_line",
))
def test_invalid_baseline_never_grants_allowances(tmp_path, damage):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    report = audit.collect(tmp_path)
    baseline = json.loads(json.dumps(report))
    if damage == "non_list":
        baseline = {}
    elif damage == "bad_fingerprint":
        baseline[0]["fingerprint"] = "not-a-fingerprint"
    elif damage == "bad_occurrences":
        baseline[0]["occurrences"] = []
    elif damage == "foreign_filename":
        baseline[0]["occurrences"][0]["file"] = "other_scan.py"
    elif damage == "unknown_network":
        baseline[0]["occurrences"][0]["network"] = "unknown"
    elif damage == "wrong_network_summary":
        baseline[0]["networks"] = ["x"]
    elif damage == "nonpositive_line":
        baseline[0]["occurrences"][0]["line"] = 0
    with pytest.raises(ValueError, match="Malformed architecture baseline"):
        audit.regressions(report, baseline)


def test_repeated_exact_baseline_location_cannot_inflate_allowance(tmp_path):
    _source(tmp_path, "x_scan.py")
    _source(tmp_path, "threads_scan.py")
    report = audit.collect(tmp_path)
    poisoned = json.loads(json.dumps(report))
    poisoned[0]["occurrences"].append(dict(poisoned[0]["occurrences"][0]))
    with pytest.raises(ValueError, match="Duplicate occurrence"):
        audit.regressions(report, poisoned)


def test_same_lexical_name_at_distinct_lines_remains_budgetable(tmp_path):
    # Two distinct definitions can have the same qualified name. They must
    # count twice, unlike an exact repeated baseline location.
    _source(tmp_path, "x_scan.py", SOURCE + "\n" + SOURCE)
    _source(tmp_path, "threads_scan.py")
    report = audit.collect(tmp_path)
    assert len(report) == 1
    x_copies = [o for o in report[0]["occurrences"] if o["network"] == "x"]
    assert len(x_copies) == 2
    assert len({o["line"] for o in x_copies}) == 2
    assert audit.regressions(report, report) == []


def test_module_manifest_fails_on_missing_same_network_module(tmp_path):
    for name in ("x_scan.py", "x_execute.py", "threads_scan.py"):
        _source(tmp_path, name)
    expected = ["threads_scan.py", "x_execute.py", "x_scan.py"]
    assert audit.missing_modules(tmp_path, expected) == []
    # The network set is unchanged, but an important source disappeared.
    (tmp_path / "x_execute.py").unlink()
    assert {network for _, network in audit._eligible_paths(tmp_path)} == {"x", "threads"}
    assert audit.missing_modules(tmp_path, expected) == ["x_execute.py"]


def test_module_manifest_accepts_new_modules_without_budget_inflation(tmp_path):
    _source(tmp_path, "x_scan.py")
    expected = ["x_scan.py"]
    _source(tmp_path, "x_execute.py")
    assert audit.missing_modules(tmp_path, expected) == []


def test_manifest_rejects_windows_subdirectory_and_unhashable_entries(tmp_path):
    _source(tmp_path, "x_scan.py")
    for malformed in (["folder\\x_scan.py"], [{"not": "a filename"}]):
        with pytest.raises(ValueError, match="Malformed architecture module manifest"):
            audit.missing_modules(tmp_path, malformed)


@pytest.mark.parametrize("bad", ([], ["x_scan.py", "x_scan.py"], ["../x_scan.py"],
                                  ["unrelated.py"], "x_scan.py"))
def test_malformed_module_manifest_fails_closed(tmp_path, bad):
    _source(tmp_path, "x_scan.py")
    with pytest.raises(ValueError, match="Malformed architecture module manifest"):
        audit.missing_modules(tmp_path, bad)


def test_repository_keeps_audited_source_inventory():
    expected = json.loads(
        (ROOT / "tests" / "fixtures" / "architecture_scanned_modules.json").read_text(encoding="utf-8")
    )
    assert {audit._network(Path(name)) for name in expected} == set(audit.NETWORKS)
    assert not audit.missing_modules(ROOT / "tools", expected)


def test_cli_rejects_missing_module_from_manifest(tmp_path):
    _source(tmp_path, "x_scan.py")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(["x_scan.py", "x_execute.py"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Missing audited network modules: x_execute.py"):
        audit.main(["--tools", str(tmp_path), "--module-manifest", str(manifest)])
