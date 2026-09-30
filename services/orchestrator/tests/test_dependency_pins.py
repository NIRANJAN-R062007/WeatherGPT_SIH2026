"""Guard against regressing security-sensitive dependency pins."""
from importlib.metadata import version


def _t(v: str) -> tuple:
    return tuple(int(p) for p in v.split(".")[:3])


def test_python_multipart_has_security_fixes():
    assert _t(version("python-multipart")) >= (0, 0, 31)


def test_requirements_pin_matches_minimum():
    import pathlib

    text = (pathlib.Path(__file__).parents[1] / "requirements.txt").read_text()
    line = next(x for x in text.splitlines() if x.startswith("python-multipart"))
    assert _t(line.split("==")[1].strip()) >= (0, 0, 31)
