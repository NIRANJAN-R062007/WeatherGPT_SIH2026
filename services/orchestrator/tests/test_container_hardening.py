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
