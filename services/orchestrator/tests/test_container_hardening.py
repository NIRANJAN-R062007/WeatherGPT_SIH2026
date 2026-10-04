"""Static checks that images run non-root and k8s pods are locked down."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SERVICES = ["orchestrator", "gateway"]


@pytest.mark.parametrize("svc", SERVICES)
def test_dockerfile_drops_root(svc):
    text = (ROOT / "services" / svc / "Dockerfile").read_text()
    users = re.findall(r"^USER\s+(\S+)", text, re.M)
    assert users, "no USER instruction"
    uid = users[-1].split(":")[0]
    assert uid.isdigit() and int(uid) != 0
    # USER must precede the CMD so the server itself never runs as root.
    assert text.rindex("USER ") < text.rindex("CMD ")


@pytest.mark.parametrize("svc", SERVICES)
def test_k8s_security_context(svc):
    docs = yaml.safe_load_all((ROOT / "k8s" / "base" / f"{svc}.yaml").read_text())
    dep = next(d for d in docs if d["kind"] == "Deployment")
    spec = dep["spec"]["template"]["spec"]
    pod = spec["securityContext"]
    assert pod["runAsNonRoot"] is True
    assert pod["runAsUser"] == pod["runAsGroup"] == pod["fsGroup"] == 10001
    assert pod["seccompProfile"]["type"] == "RuntimeDefault"
    c = spec["containers"][0]["securityContext"]
    assert c["allowPrivilegeEscalation"] is False
    assert c["readOnlyRootFilesystem"] is True
    assert c["capabilities"]["drop"] == ["ALL"]
    mounts = {m["mountPath"] for m in spec["containers"][0]["volumeMounts"]}
    assert "/tmp" in mounts


# TFA-22: each image's build context, and the .dockerignore at its root. Without
# one, a working-tree build copied services/orchestrator/.venv (~400 MB) into the
# orchestrator image; CI builds from a clean checkout and never showed it.
_CONTEXTS = {"orchestrator": ROOT, "gateway": ROOT / "services" / "gateway"}


def _ignored(context: Path) -> list[str]:
    path = context / ".dockerignore"
    assert path.exists(), f"no .dockerignore in {context}"
    return [ln.strip() for ln in path.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]


@pytest.mark.parametrize("svc", SERVICES)
def test_build_context_leaves_out_local_environments_and_secrets(svc):
    rules = _ignored(_CONTEXTS[svc])
    assert any(r.rstrip("/").endswith(".venv") for r in rules)
    assert any(r.rstrip("/").endswith("__pycache__") for r in rules)
    assert ".env" in rules


def test_the_orchestrator_context_keeps_what_its_dockerfile_copies():
    """An over-eager ignore rule would make COPY fail (or ship an image without
    its data): none of the Dockerfile's COPY sources may be ignored outright."""
    rules = {r.rstrip("/") for r in _ignored(ROOT)}
    text = (ROOT / "services" / "orchestrator" / "Dockerfile").read_text()
    sources = [line.split()[1] for line in text.splitlines() if line.startswith("COPY ")]
    for src in sources:
        top = src.split("/")[0]
        assert top not in rules and src not in rules, f"{src} is ignored"
