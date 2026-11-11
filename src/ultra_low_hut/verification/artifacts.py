"""Prepare official version artifacts and the in-memory generation query service."""

import argparse, hashlib, json, os, subprocess, sys, urllib.request, zipfile, re, time
from pathlib import Path

from ultra_low_hut import ROOT
from ultra_low_hut.versions import resolve


def fetch_bytes(url):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "FTP_PROXY"):
        os.environ.pop(name, None)
        os.environ.pop(name.lower(), None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(4):
        try:
            with opener.open(url, timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def download(url, path, digest=None):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_bytes(url)
    if digest and hashlib.sha1(data).hexdigest() != digest:
        raise RuntimeError("SHA1 mismatch: " + path.name)
    temp = path.with_suffix(".download")
    temp.write_bytes(data)
    temp.replace(path)


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


def prepare(version, java="java", exact=False, *, artifacts_only=False, agent_only=False):
    """Reuse every existing JAR without downloading or hashing it again."""
    cfg = resolve(version)
    version = cfg["requested_version"] if exact else cfg["representative"]
    w = ROOT / "runs/versions" / version
    w.mkdir(parents=True, exist_ok=True)
    if agent_only:
        from ultra_low_hut.verification.prepare import build
        return build(version, java, exact=True)

    info_path = w / "version.json"
    info = json.loads(info_path.read_text()) if info_path.exists() else None

    def version_info():
        nonlocal info
        if info is None:
            manifest = json.loads(fetch_bytes("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"))
            entry = next(v for v in manifest["versions"] if v["id"] == version)
            info = json.loads(fetch_bytes(entry["url"]))
            info_path.write_text(json.dumps(info, indent=2))
        return info

    server = w / "server.jar"
    if not server.exists():
        d = version_info()["downloads"]["server"]
        download(d["url"], server, d.get("sha1"))
    libs = w / "libraries"
    libs.mkdir(exist_ok=True)
    inner = w / "server-inner.jar"
    classpath_file = w / "classpath.txt"
    cached_dependencies = (classpath_file.read_text().strip().split(os.pathsep)
                           if classpath_file.exists() else [])
    if not inner.exists() or not cached_dependencies or any(
            not Path(entry).exists() for entry in cached_dependencies):
        with zipfile.ZipFile(server) as bundle:
            if not inner.exists():
                name = next(n for n in bundle.namelist()
                            if n.startswith("META-INF/versions/") and n.endswith(".jar"))
                inner.write_bytes(bundle.read(name))
            for name in bundle.namelist():
                if name.startswith("META-INF/libraries/") and name.endswith(".jar"):
                    destination = libs / Path(name).name
                    if not destination.exists():
                        destination.write_bytes(bundle.read(name))
    for name, rel in [
        ("specialsource", "net/md-5/SpecialSource/1.11.4/SpecialSource-1.11.4-shaded.jar"),
        ("ecj", "org/eclipse/jdt/ecj/3.44.0/ecj-3.44.0.jar"),
        ("asm", "org/ow2/asm/asm/9.9/asm-9.9.jar"),
    ]:
        destination = w / (name + ".jar")
        if not destination.exists():
            url = "https://repo.maven.apache.org/maven2/" + rel
            sha = fetch_bytes(url + ".sha1").decode().split()[0]
            download(url, destination, sha)
    mapped = w / "server-mapped.jar"
    if not mapped.exists():
        downloads = version_info()["downloads"]
        if "server_mappings" in downloads:
            d = downloads["server_mappings"]
            download(d["url"], w / "server-mappings.txt", d.get("sha1"))
            mapping(w / "server-mappings.txt", w / "official.srg")
            subprocess.run([java, "-XX:ActiveProcessorCount=2", "-Xmx2G", "-jar",
                            str(w / "specialsource.jar"), "-i", str(inner), "-o", str(mapped),
                            "-m", str(w / "official.srg")], check=True)
        else:
            mapped.write_bytes(inner.read_bytes())
    cp = os.pathsep.join(map(str, [mapped, *sorted(libs.glob("*.jar"))]))
    classpath_file.write_text(cp)
    if not artifacts_only:
        service = ROOT / "runs/query-service-build"
        if (not (service / "query-service.jar").exists()
                or not (service / "adapters" / version / "classes/VanillaQueryMain.class").exists()):
            from ultra_low_hut.verification.prepare import build
            build(version, java, exact=True)
    record_path = w / "artifacts.json"
    if record_path.exists():
        return json.loads(record_path.read_text())
    record = dict(version=version, interval=cfg["id"],
                  java_major=cfg["verifier"]["java_major"])
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", "--versions", nargs="+", action="extend", required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--artifacts-only", action="store_true")
    parser.add_argument("--agent-only", action="store_true")
    args = parser.parse_args()
    for version in dict.fromkeys(args.version):
        print(json.dumps(prepare(version, args.java, args.exact,
                                 artifacts_only=args.artifacts_only, agent_only=args.agent_only)), flush=True)


if __name__ == "__main__":
    main()
