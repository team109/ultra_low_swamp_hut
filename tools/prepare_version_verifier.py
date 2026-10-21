"""Prepare official version artifacts and the in-memory generation query service."""

import argparse, hashlib, json, os, subprocess, sys, urllib.request, zipfile, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mcsearch.hut_versions import resolve


def fetch_bytes(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def download(url, path, digest=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temp = path.with_suffix(".download")
        temp.write_bytes(fetch_bytes(url))
        temp.replace(path)
    if digest and hashlib.sha1(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("SHA1 mismatch: " + path.name)


def mapping(source, target):
    lines = source.read_text().splitlines()
    classes = {}
    for s in lines:
        if s and not s.startswith((" ", "#")):
            name, obf = s[:-1].split(" -> ")
            classes[name] = obf
    primitive = dict(
        zip(
            [
                "void",
                "boolean",
                "byte",
                "char",
                "short",
                "int",
                "long",
                "float",
                "double",
            ],
            "VZBCSIJFD",
        )
    )

    def desc(t, obf=False):
        n = 0
        while t.endswith("[]"):
            n += 1
            t = t[:-2]
        return "[" * n + (
            primitive[t]
            if t in primitive
            else "L" + (classes.get(t, t) if obf else t).replace(".", "/") + ";"
        )

    out = []
    for s in lines:
        if not s or s.startswith("#"):
            continue
        if not s.startswith(" "):
            name, obf = s[:-1].split(" -> ")
            name = name.replace(".", "/")
            obf = obf.replace(".", "/")
            out.append(f"CL: {obf} {name}")
            continue
        a, b = s.strip().split(" -> ")
        a = re.sub(r"^\d+:\d+:", "", a)
        a = re.sub(r":\d+(?::\d+)?$", "", a)
        typ, member = a.split(" ", 1)
        if "(" in member:
            method, args = member[:-1].split("(")
            if "." in method:
                continue
            args = args.split(",") if args else []
            d = "(" + "".join(desc(v) for v in args) + ")" + desc(typ)
            o = "(" + "".join(desc(v, True) for v in args) + ")" + desc(typ, True)
            out.append(f"MD: {obf}/{b} {o} {name}/{method} {d}")
        else:
            out.append(f"FD: {obf}/{b} {name}/{member}")
    target.write_text("\n".join(out) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--exact", action="store_true")
    p.add_argument("--artifacts-only", action="store_true")
    p.add_argument("--agent-only", action="store_true")
    a = p.parse_args()
    cfg = resolve(a.version)
    version = cfg["requested_version"] if a.exact else cfg["representative"]
    w = ROOT / "runs/versions" / version
    w.mkdir(parents=True, exist_ok=True)
    if a.agent_only:
        from tools.prepare_terrain_service import build

        print(json.dumps(build(a.version, a.java, a.exact)))
        return
    m = json.loads(
        fetch_bytes("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json")
    )
    entry = next(v for v in m["versions"] if v["id"] == version)
    info = json.loads(fetch_bytes(entry["url"]))
    (w / "version.json").write_text(json.dumps(info, indent=2))
    d = info["downloads"]["server"]
    download(d["url"], w / "server.jar", d["sha1"])
    with zipfile.ZipFile(w / "server.jar") as z:
        n = next(
            n
            for n in z.namelist()
            if n.startswith("META-INF/versions/") and n.endswith(".jar")
        )
        (w / "server-inner.jar").write_bytes(z.read(n))
        libs = w / "libraries"
        libs.mkdir(exist_ok=True)
        for n in z.namelist():
            if n.startswith("META-INF/libraries/") and n.endswith(".jar"):
                (libs / Path(n).name).write_bytes(z.read(n))
    for name, rel in [
        (
            "specialsource",
            "net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4-shaded.jar",
        ),
        ("ecj", "org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.jar"),
        ("asm", "org/ow2/asm/asm/9.9/asm-9.9.jar"),
    ]:
        url = "https://repo.maven.apache.org/maven2/" + rel
        # Each process uses a version-local tools directory, avoiding concurrent downloads.
        sha = fetch_bytes(url + ".sha1").decode().split()[0]
        download(url, w / (name + ".jar"), sha)
    mapped = w / "server-mapped.jar"
    if "server_mappings" in info["downloads"]:
        d = info["downloads"]["server_mappings"]
        download(d["url"], w / "server-mappings.txt", d["sha1"])
        if not mapped.exists():
            mapping(w / "server-mappings.txt", w / "official.srg")
            subprocess.run(
                [
                    a.java,
                    "-XX:ActiveProcessorCount=2",
                    "-Xmx2G",
                    "-jar",
                    str(w / "specialsource.jar"),
                    "-i",
                    str(w / "server-inner.jar"),
                    "-o",
                    str(mapped),
                    "-m",
                    str(w / "official.srg"),
                ],
                check=True,
            )
    else:
        if not mapped.exists():
            mapped.write_bytes((w / "server-inner.jar").read_bytes())
    cp = os.pathsep.join(map(str, [mapped, *sorted(libs.glob("*.jar"))]))
    (w / "classpath.txt").write_text(cp)
    if not a.artifacts_only:
        from tools.prepare_terrain_service import build

        build(a.version, a.java, a.exact)
    record = dict(
        version=version,
        interval=cfg["id"],
        official_sha1=info["downloads"]["server"]["sha1"],
        java_major=info["javaVersion"]["majorVersion"],
        sha256={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [w / "server.jar", mapped]
        },
    )
    (w / "artifacts.json").write_text(json.dumps(record, indent=2))
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
