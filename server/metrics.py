"""Resource use, read from the kernel rather than estimated.

Per cell: the cgroup v2 counters of its systemd units (the agent with everything it started, its screen,
and any apps you ran on it). Memory is the working set (memory.current minus reclaimable inactive file
cache, the figure `docker stats` and cAdvisor show); CPU is a rate measured between two reads, as a
percent of one core. Host: /proc/stat, /proc/meminfo, /proc/loadavg and statvfs. Disk use per cell is
walked in the background at most once a minute, counting allocated blocks once per inode, like `du`."""
import os
import subprocess
import threading
import time
from pathlib import Path

from . import cells, usage
from .config import HISTORY, HOME, KNOWLEDGE, LOCAL, SCREENS, UNIT, read

CGROUP = Path("/sys/fs/cgroup")
PROC = Path("/proc")
DISK_EVERY = 60


def read_int(path):
    value = read(path)
    return int(value) if value and value.isdigit() else None


def read_kv(path):
    out = {}
    for line in (read(path) or "").splitlines():
        key, _, value = line.partition(" ")
        if value.strip().lstrip("-").isdigit():
            out[key] = int(value)
    return out


class Rate:
    """Per-second rate of an ever-growing counter, measured over at least a second; a read sooner than
    that returns the last rate. None until there are two reads, or after the counter went backwards."""

    def __init__(self):
        self.last = {}

    def __call__(self, key, value, now):
        prev = self.last.get(key)
        if prev and now - prev[0] < 1:
            return prev[2]
        rate = (value - prev[1]) / (now - prev[0]) if prev else None
        if rate is not None and rate < 0:
            rate = None
        self.last[key] = (now, value, rate)
        return rate

    def forget(self, keep):
        for key in list(self.last):
            if key not in keep:
                del self.last[key]


class Units:
    """Where each systemd user unit's cgroup lives. Looked up once per unit, then read directly."""

    def __init__(self):
        self.paths = {}
        self.misses = {}

    def path(self, unit):
        p = self.paths.get(unit)
        if p is not None and p.is_dir():
            return p
        if time.monotonic() - self.misses.get(unit, -60) < 10:
            return None
        try:
            cg = subprocess.run(["systemctl", "--user", "show", "-p", "ControlGroup", "--value", unit],
                                capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            cg = ""
        p = CGROUP / cg.lstrip("/") if cg else None
        if p is None or not p.is_dir():
            self.misses[unit] = time.monotonic()
            self.paths.pop(unit, None)
            return None
        self.paths[unit] = p
        return p

    def of_cell(self, name):
        agent = self.path(f"{UNIT}-agent-{name}.service")
        found = [p for p in (agent, self.path(f"{UNIT}-screen-{name}.service")) if p]
        if agent:
            found += sorted(agent.parent.glob(f"{UNIT}-app-{name}.*"))
        return agent, found


def cgroup(path):
    current = read_int(path / "memory.current")
    stat = read_kv(path / "memory.stat")
    return {
        "mem": None if current is None else max(0, current - stat.get("inactive_file", 0)),
        "cpu_usec": read_kv(path / "cpu.stat").get("usage_usec"),
        "pids": read_int(path / "pids.current"),
    }


def du(path):
    """Bytes allocated under path, each inode once; symlinks are not followed."""
    total, seen, stack = 0, set(), [str(path)]
    while stack:
        try:
            entries = os.scandir(stack.pop())
        except OSError:
            continue
        with entries:
            for e in entries:
                try:
                    st = e.stat(follow_symlinks=False)
                except OSError:
                    continue
                if (st.st_dev, st.st_ino) in seen:
                    continue
                seen.add((st.st_dev, st.st_ino))
                total += st.st_blocks * 512
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
    return total


class Disk:
    """Disk use per folder, refreshed in a background thread so a request never waits on a walk."""

    def __init__(self):
        self.sizes = {}
        self.at = 0.0
        self.busy = False
        self.lock = threading.Lock()

    def get(self, folders):
        with self.lock:
            if not self.busy and time.monotonic() - self.at > DISK_EVERY:
                self.busy = True
                threading.Thread(target=self.walk, args=(dict(folders),), daemon=True).start()
            return dict(self.sizes)

    def walk(self, folders):
        sizes = {key: du(path) for key, path in folders.items()}
        with self.lock:
            self.sizes, self.at, self.busy = sizes, time.monotonic(), False


class Metrics:
    def __init__(self):
        self.units = Units()
        self.rate = Rate()
        self.disk = Disk()
        self.lock = threading.Lock()

    def host(self, now):
        mem = read_kv_kb(PROC / "meminfo")
        cpu = (read(PROC / "stat") or "").splitlines()[:1]
        busy_frac = None
        if cpu and cpu[0].startswith("cpu "):
            v = [int(x) for x in cpu[0].split()[1:]]
            idle, total = v[3] + (v[4] if len(v) > 4 else 0), sum(v[:8])
            busy, all_ = self.rate("host.busy", total - idle, now), self.rate("host.total", total, now)
            busy_frac = busy / all_ if busy is not None and all_ else None
        load = (read(PROC / "loadavg") or "0 0 0").split()[:3]
        disks, seen = [], set()
        for path in (HOME, Path(LOCAL) if LOCAL else None):
            if path is None or not path.exists():
                continue
            st = os.statvfs(path)
            dev = os.stat(path).st_dev
            if dev in seen:
                continue
            seen.add(dev)
            disks.append({"path": str(path), "total": st.f_blocks * st.f_frsize,
                          "used": (st.f_blocks - st.f_bfree) * st.f_frsize, "free": st.f_bavail * st.f_frsize})
        own = read_kv_kb(PROC / "self" / "status")
        return {
            "cores": os.cpu_count(),
            "cpu": None if busy_frac is None else round(busy_frac * 100, 1),
            "load": [float(x) for x in load],
            "mem": {"total": mem.get("MemTotal"), "available": mem.get("MemAvailable"),
                    "used": (mem["MemTotal"] - mem["MemAvailable"]) if "MemTotal" in mem and "MemAvailable" in mem else None},
            "disks": disks,
            "control_plane": {"rss": own.get("VmRSS"), "threads": own.get("Threads")},
        }

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            out_cells, keep, folders = [], set(), {"history": HISTORY, "knowledge": KNOWLEDGE}
            for c in cells.list_cells():
                name = c["name"]
                agent, groups = self.units.of_cell(name)
                samples = [cgroup(p) for p in groups]
                mems = [s["mem"] for s in samples if s["mem"] is not None]
                usecs = [s["cpu_usec"] for s in samples if s["cpu_usec"] is not None]
                pids = [s["pids"] for s in samples if s["pids"] is not None]
                key = f"cell.{name}"
                keep.add(key)
                cpu = self.rate(key, sum(usecs), now) if usecs else None
                home = SCREENS / name / "home"
                folders[f"{name}.home"] = Path(os.path.realpath(home))
                folders[f"{name}.state"] = SCREENS / name / "state"
                out_cells.append({
                    "name": name,
                    "runtime": c["runtime"],
                    "status": c["status"],
                    "started": c["started"],
                    "cpu": None if cpu is None else round(cpu / 1e6 * 100, 1),
                    "mem": sum(mems) if mems else None,
                    "mem_max": read_int(agent / "memory.max") if agent else None,
                    "mem_peak": read_int(agent / "memory.peak") if agent else None,
                    "pids": sum(pids) if pids else None,
                    "tokens": usage.totals(SCREENS / name / "state" / "stream.jsonl"),
                })
            keep |= {"host.busy", "host.total"}
            host = self.host(now)
            self.rate.forget(keep)
            sizes = self.disk.get(folders)
            for c in out_cells:
                home, state = sizes.get(f"{c['name']}.home"), sizes.get(f"{c['name']}.state")
                c["disk"] = None if home is None and state is None else {"home": home, "state": state}
            host["cells_mem"] = sum(c["mem"] or 0 for c in out_cells)
            host["storage"] = {"history": sizes.get("history"), "knowledge": sizes.get("knowledge")}
            host["disk_measured"] = bool(sizes)
            return {"host": host, "cells": out_cells}


def read_kv_kb(path):
    """/proc files with `Key:   123 kB` lines, as bytes (counts stay counts)."""
    out = {}
    for line in (read(path) or "").splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            out[key] = int(parts[0]) * (1024 if len(parts) > 1 and parts[1] == "kB" else 1)
    return out


METRICS = Metrics()
