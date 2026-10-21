"""Recheck a hit in a fresh unmodified official-server world."""

import argparse, json, hashlib, subprocess, time, threading, queue, struct, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_nbt(data):
    offset = 0

    def take(n):
        nonlocal offset
        v = data[offset : offset + n]
        offset += n
        if len(v) != n:
            raise ValueError("truncated NBT")
        return v

    def num(fmt):
        return struct.unpack(">" + fmt, take(struct.calcsize(">" + fmt)))[0]

    def string():
        return take(num("H")).decode("utf8")

    def payload(tag):
        if tag in range(1, 7):
            return num({1: "b", 2: "h", 3: "i", 4: "q", 5: "f", 6: "d"}[tag])
        if tag == 7:
            return take(num("i"))
        if tag == 8:
            return string()
        if tag == 9:
            child = num("B")
            return [payload(child) for _ in range(num("i"))]
        if tag == 10:
            out = {}
            while True:
                child = num("B")
                if not child:
                    return out
                key = string()
                out[key] = payload(child)
        if tag in (11, 12):
            return [num("i" if tag == 11 else "q") for _ in range(num("i"))]
        raise ValueError("unknown NBT " + str(tag))

    tag = num("B")
    string()
    return payload(tag)


def read_chunk(world, cx, cz):
    raw = (world / "region" / f"r.{cx//32}.{cz//32}.mca").read_bytes()
    i = ((cx % 32) + (cz % 32) * 32) * 4
    sector = int.from_bytes(raw[i : i + 3], "big")
    off = sector * 4096
    if not sector:
        raise ValueError("target chunk absent")
    n = int.from_bytes(raw[off : off + 4], "big")
    compression = raw[off + 4]
    if compression != 2:
        raise ValueError("unsupported region compression " + str(compression))
    return read_nbt(zlib.decompress(raw[off + 5 : off + 4 + n]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--accept-eula", action="store_true")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--x", type=int, required=True)
    p.add_argument("--z", type=int, required=True)
    p.add_argument("--approach", choices=["center", "east", "west"], default="center")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not a.accept_eula:
        p.error("Read the Minecraft EULA and supply --accept-eula")
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    jar = ROOT / "runs/versions" / a.version / "server.jar"
    (out / "eula.txt").write_text("eula=true\n")
    (out / "server.properties").write_text(
        f"level-seed={a.seed}\nlevel-name=world\nserver-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nenable-rcon=false\nenable-query=false\nview-distance=2\nsimulation-distance=2\nmax-tick-time=-1\nspawn-protection=0\n"
    )
    java = str(Path(a.java).resolve()) if "/" in a.java else a.java
    cmd = [java, "-XX:ActiveProcessorCount=1", "-Xmx3G", "-jar", str(jar), "nogui"]
    events = queue.Queue()
    t = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=out,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def reader():
        with (out / "world.log").open("w") as log:
            for line in proc.stdout:
                log.write(line)
                log.flush()
                events.put(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    loaded_at = None
    save_at = None
    stopping = False
    neighbor_at = None
    commands = []

    def send(s):
        proc.stdin.write(s + "\n")
        proc.stdin.flush()
        commands.append(dict(command=s, seconds=time.monotonic() - t))

    try:
        while proc.poll() is None:
            if time.monotonic() - t > 300:
                raise TimeoutError("official verification exceeded 300s")
            try:
                line = events.get(timeout=0.5)
            except queue.Empty:
                line = ""
            if "Done (" in line:
                if a.approach == "center":
                    send(f"forceload add {a.x} {a.z}")
                    loaded_at = time.monotonic()
                else:
                    dx = 32 if a.approach == "east" else -32
                    send(f"forceload add {a.x+dx} {a.z}")
                    neighbor_at = time.monotonic()
            if (
                neighbor_at
                and loaded_at is None
                and time.monotonic() - neighbor_at > 15
            ):
                send(f"forceload add {a.x} {a.z}")
                loaded_at = time.monotonic()
            if loaded_at and time.monotonic() - loaded_at > 12 and save_at is None:
                send("save-all flush")
                save_at = time.monotonic()
            if save_at and time.monotonic() - save_at > 3 and not stopping:
                send("stop")
                stopping = True
        if proc.returncode:
            raise RuntimeError("server exited " + str(proc.returncode))
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=30)
        thread.join(timeout=5)
    chunk = read_chunk(out / "world", a.x // 16, a.z // 16)
    structures = chunk.get("structures", chunk.get("Level", {}).get("Structures", {}))
    starts = structures.get("starts", structures.get("Starts", {}))
    hut = next((v for k, v in starts.items() if "hut" in k.lower()), {})
    report = dict(
        version=a.version,
        seed=str(a.seed),
        x=a.x,
        z=a.z,
        approach=a.approach,
        commands=commands,
        jar_sha256=hashlib.sha256(jar.read_bytes()).hexdigest(),
        seconds=time.monotonic() - t,
        chunk_status=chunk.get("Status"),
        hut=hut,
        structure_keys=list(starts),
    )
    if chunk.get("Status") not in ["full", "minecraft:full"]:
        raise RuntimeError("Target is not a FULL chunk: " + str(report))
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
