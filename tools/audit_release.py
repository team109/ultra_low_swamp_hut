"""Audit the source publication inventory, including compressed text fixtures.

Generated output and dependencies are excluded; HTTP routes, Java resource names
and URLs are not filesystem paths. A report records precisely what was inspected.
"""

import ast, fnmatch, gzip, hashlib, json, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", "external", "runs", "logs", "__pycache__", ".venv", "dist"}
ARTIFACTS = {".so", ".o", ".a", ".class", ".jar", ".pyc", ".pyo"}
ROUTES = {"/health", "/jobs", "/jobs/", "/cancel"}
ROOT_NAMES = "cephfs home root tmp usr opt mnt workspace workspaces Users private volumes scratch data".split()
HOST_PREFIX = "zhang" + "kaidong"
MACHINE = re.compile(
    r"(?<![A-Za-z0-9:}.])/(?:"
    + "|".join(ROOT_NAMES)
    + r')/[^\s"\'<>`]*|(?<![A-Za-z])[A-Za-z]:\\[A-Za-z][^\s"\']+'
)
QUOTED = re.compile(r"""["'`](/[A-Za-z][A-Za-z0-9_.-]*(?:/[^\s"'`<>]*)?)["'`]""")
RESOURCE = chr(47) + "data/minecraft/worldgen/carver/"
LOCAL_NAMES = {"AGENTS.md", ".env"}
RESULT_NAMES = {
    "low-huts.jsonl",
    "first-hits.jsonl",
    "verified-huts.jsonl",
    "TARGET_REACHED.json",
    "packaging-checks.json",
    "positive-hut-candidates.json",
}


def files():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(
            d for d in dirs if d not in EXCLUDED and not d.startswith("build")
        )
        for n in sorted(names):
            if n in LOCAL_NAMES or n.endswith(".log"):
                continue
            yield Path(base) / n


def audit():
    errors = []
    inventory = []
    text_count = gzip_count = 0
    for p in files():
        rel = p.relative_to(ROOT).as_posix()
        public_catalog = rel.startswith(("data/huts/", "data/mineshafts/"))
        if (
            p.name in LOCAL_NAMES
            or ((p.name in RESULT_NAMES or p.suffix == ".jsonl") and not public_catalog)
            or any(
                v in EXCLUDED or v.startswith("build") and i == 0
                for i, v in enumerate(p.relative_to(ROOT).parts[:-1])
            )
        ):
            errors.append((rel, "local artifact or result in publication inventory"))
            continue
        if p.is_symlink():
            errors.append((rel, "symlink in publication inventory"))
            continue
        if p.suffix in ARTIFACTS:
            errors.append((rel, "compiled artifact"))
            continue
        raw = p.read_bytes()
        inventory.append(
            dict(path=rel, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        )
        try:
            decoded = gzip.decompress(raw) if p.suffix == ".gz" else raw
            text = decoded.decode("utf-8")
        except (UnicodeError, OSError):
            continue
        text_count += 1
        gzip_count += p.suffix == ".gz"
        for line_no, line in enumerate(text.splitlines(), 1):
            if HOST_PREFIX in line:
                errors.append((rel, line_no, "private host reference"))
            if ("-----BEGIN " + "OPENSSH PRIVATE KEY-----") in line or (
                "-----BEGIN " + "RSA PRIVATE KEY-----"
            ) in line:
                errors.append((rel, line_no, "private key material"))
            for m in MACHINE.finditer(line):
                if m.group() == RESOURCE:
                    continue
                errors.append(
                    (rel, line_no, "absolute filesystem path", m.group()[:120])
                )
            for m in [] if p.suffix == ".py" else QUOTED.finditer(line):
                value = m.group(1)
                if (
                    value in ROUTES
                    or value == RESOURCE
                    or value == "/forceload"
                    or (p.suffix == ".java" and ".endsWith(" in line)
                ):
                    continue
                errors.append((rel, line_no, "quoted rooted path", value[:120]))
        if p.suffix == ".py":
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    s = node.value
                    if (
                        s.startswith("/")
                        and len(s) > 1
                        and not s.startswith(("//", "/\\"))
                        and s not in ROUTES
                        and rel != "tools/audit_release.py"
                    ):
                        errors.append(
                            (rel, node.lineno, "absolute Python string", s[:100])
                        )
    report = dict(
        files=len(inventory),
        text_files=text_count,
        gzip_text_files=gzip_count,
        errors=errors,
        inventory=inventory,
    )
    out = ROOT / "runs/release-audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "inventory"},
            ensure_ascii=False,
            indent=2,
        )
    )
    if errors:
        raise SystemExit(1)
    return report


def main():
    audit()


if __name__ == "__main__":
    main()
