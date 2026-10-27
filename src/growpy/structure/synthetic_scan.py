"""Virtual terrestrial laser scans of generated trees with HELIOS++ (XRFF-344).

A generated tree mesh (Grove OBJ from ``[export] mode = "helios"``) is scanned the way the
real reference was scanned, so real and synthetic clouds pass through the same
segmentation, fitter (XRFF-575) and L2 metrics (``growpy.structure.pointcloud``).

Two modes:

* **alone**: one tree on a ground plane, ``n_positions`` tripod positions on a circle
  of radius ``distance_m`` around the stem;
* **stand**: the same target tree plus neighbour meshes at given offsets; the scan
  positions stay around the target, so neighbours occlude it as in a stand.

HELIOS++ runs as its command-line binary (``helios++``) from the conda env ``helios``
(conda-forge package ``helios``, Python module ``pyhelios``, LGPL-3.0-or-later /
GPL-3.0-or-later). This module needs only numpy and pandas: it writes the scene and
survey XML, calls the binary, and streams the ASCII ``legNNN_points.xyz`` output in
chunks, dropping ground returns while reading (full-resolution 360 degree scans are
mostly ground), so a large scan is never held in memory as a whole.

Frame of the returned points: metres, z up, the target tree's stem base at the origin
(the ground plane is at z = 0). Each point carries the scene part it hit
(``0`` ground, ``1`` target, ``2..`` neighbours, from HELIOS's ``hitObjectId``) and the
scan position (leg) it came from, so a perfect segmentation is available as the upper
bound for the stand mode.

Scanner defaults approximate a RIEGL VZ-series static TLS survey (the Ecosense TLS file
carries RIEGL ``Reflectance``/``Deviation`` fields but no scanner model or scan
positions): HELIOS ``riegl_vz400``, 300 kHz, field of view -40..+60 degrees, 0.04 degree
angular step, optical centre 1.5 m above ground. Nothing here is fitted to the real
scan yet; that is the validation step of XRFF-344.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np

# HELIOS tripod: the platform's scanner mount is 1.5 m, the VZ beam origin 0.2 m above it.
_TRIPOD_MOUNT_M = 1.5
_BEAM_ORIGIN_M = 0.2

DEFAULT_CONDA_HELIOS = Path.home() / "miniconda3" / "envs" / "helios"

# Columns of HELIOS++ ASCII point output (``legNNN_points.xyz``).
_XYZ_COLS = {"x": 0, "y": 1, "z": 2, "hit_object_id": 8}


@dataclass
class ScannerSetup:
    """Static TLS scanner settings (HELIOS ``scannerSettings``).

    HELIOS derives the line rate from pulse rate and step: for ``riegl_vz400`` it is
    ``pulse_freq_hz * resolution_deg / 240``, which must stay within 3-120 Hz (300 kHz at
    0.04 degrees gives 50 Hz; 300 kHz at 0.1 degrees is refused).
    """

    scanner_id: str = "riegl_vz400"
    pulse_freq_hz: int = 300_000
    vertical_min_deg: float = -40.0
    vertical_max_deg: float = 60.0
    resolution_deg: float = 0.04  # vertical and horizontal angular step
    height_m: float = 1.5  # optical centre above ground
    beam_divergence_rad: float | None = None  # None keeps the scanner library value


@dataclass
class ScanPosition:
    x: float
    y: float
    head_start_deg: float = 0.0
    head_stop_deg: float = 360.0


@dataclass
class ScenePart:
    """One OBJ in the scene; ``offset`` is where its local origin (stem base) goes."""

    obj: Path
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    up_axis: str = "z"  # "z" (growpy obj_up_axis = "z") or "y"


@dataclass
class ScanResult:
    xyz: np.ndarray  # (N, 3) metres, z up, target base at origin
    part: np.ndarray  # (N,) 0 ground, 1 target, 2.. neighbours
    position: np.ndarray  # (N,) scan position index
    run_dir: Path
    positions: list[ScanPosition] = field(default_factory=list)

    def tree(self, part: int = 1) -> np.ndarray:
        """Points of one scene part (default: the target tree)."""
        return self.xyz[self.part == part]


# --------------------------------------------------------------------------- geometry


def head_angle_deg(dx: float, dy: float) -> float:
    """HELIOS head rotation that faces direction (dx, dy).

    HELIOS turns the head counter-clockwise about +z starting from +y (read off the
    bundled demo surveys and checked by the cylinder smoke test).
    """
    return math.degrees(math.atan2(-dx, dy)) % 360.0


def ring_positions(
    n: int,
    distance_m: float,
    centre: tuple[float, float] = (0.0, 0.0),
    start_deg: float = 0.0,
    window_half_deg: float | None = None,
) -> list[ScanPosition]:
    """``n`` positions on a circle around ``centre``.

    ``window_half_deg`` limits each position's head rotation to that half-angle around
    the direction of the centre (alone mode: everything else only hits ground); ``None``
    scans the full 360 degrees as in the field.
    """
    out = []
    for i in range(n):
        a = math.radians(start_deg + 360.0 * i / n)
        x = centre[0] + distance_m * math.cos(a)
        y = centre[1] + distance_m * math.sin(a)
        if window_half_deg is None:
            out.append(ScanPosition(x, y))
        else:
            h = head_angle_deg(centre[0] - x, centre[1] - y)
            out.append(ScanPosition(x, y, h - window_half_deg, h + window_half_deg))
    return out


def write_ground_obj(path: Path, half_size_m: float) -> Path:
    """A square ground plane at z = 0 (two triangles, z up)."""
    s = half_size_m
    path.write_text(
        f"v {-s} {-s} 0\nv {s} {-s} 0\nv {s} {s} 0\nv {-s} {s} 0\n"
        "vn 0 0 1\nf 1//1 2//1 3//1\nf 1//1 3//1 4//1\n",
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------- XML


def _part_xml(
    part_id: int, obj: Path, up: str, offset: tuple[float, float, float]
) -> str:
    ox, oy, oz = offset
    return (
        f'        <part id="{part_id}">\n'
        f'            <filter type="objloader">\n'
        f'                <param type="string" key="filepath" value={quoteattr(obj.as_posix())}/>\n'
        f'                <param type="string" key="up" value="{up}"/>\n'
        f"            </filter>\n"
        f'            <filter type="translate">\n'
        f'                <param type="vec3" key="offset" value="{ox};{oy};{oz}"/>\n'
        f"            </filter>\n"
        f"        </part>\n"
    )


def scene_xml(
    parts: list[tuple[Path, str, tuple[float, float, float]]], scene_id: str
) -> str:
    """Scene XML; the list order sets the part ids (0 ground, 1 target, ...)."""
    body = "".join(_part_xml(i, obj, up, off) for i, (obj, up, off) in enumerate(parts))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<document>\n'
        f'    <scene id="{scene_id}" name="{scene_id}">\n{body}    </scene>\n</document>\n'
    )


def survey_xml(
    name: str,
    scene_path: Path,
    scene_id: str,
    positions: list[ScanPosition],
    scanner: ScannerSetup,
) -> str:
    platform_z = scanner.height_m - _TRIPOD_MOUNT_M - _BEAM_ORIGIN_M
    div = (
        f' beamDivergence_rad="{scanner.beam_divergence_rad}"'
        if scanner.beam_divergence_rad is not None
        else ""
    )
    legs = "".join(
        "        <leg>\n"
        f'            <platformSettings x="{p.x:.4f}" y="{p.y:.4f}" z="{platform_z:.4f}"/>\n'
        f'            <scannerSettings template="tls" headRotateStart_deg="{p.head_start_deg:.3f}" '
        f'headRotateStop_deg="{p.head_stop_deg:.3f}"/>\n'
        "        </leg>\n"
        for p in positions
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<document>\n'
        f'    <scannerSettings id="tls" active="true" pulseFreq_hz="{scanner.pulse_freq_hz}" '
        f'verticalAngleMin_deg="{scanner.vertical_min_deg}" '
        f'verticalAngleMax_deg="{scanner.vertical_max_deg}" '
        f'verticalResolution_deg="{scanner.resolution_deg}" '
        f'horizontalResolution_deg="{scanner.resolution_deg}"{div}/>\n'
        f'    <survey name="{name}" scene={quoteattr(scene_path.as_posix() + "#" + scene_id)} '
        f'platform="data/platforms.xml#tripod" scanner="data/scanners_tls.xml#{scanner.scanner_id}">\n'
        f"{legs}    </survey>\n</document>\n"
    )


# --------------------------------------------------------------------------- running


def find_helios(helios: str | Path | None = None) -> Path:
    """The ``helios++`` binary: argument, ``HELIOS_EXE``, PATH, or the conda env ``helios``."""
    cands: list[Path] = []
    if helios:
        cands.append(Path(helios))
    if os.environ.get("HELIOS_EXE"):
        cands.append(Path(os.environ["HELIOS_EXE"]))
    for name in ("helios++", "helios++.exe"):
        hit = shutil.which(name)
        if hit:
            cands.append(Path(hit))
    for site in ("Lib/site-packages", "lib/python3.12/site-packages"):
        for exe in ("helios++.exe", "helios++"):
            cands.append(DEFAULT_CONDA_HELIOS / site / "pyhelios" / "bin" / exe)
    for c in cands:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "helios++ not found: create the conda env (conda create -n helios -c conda-forge "
        "helios) or set HELIOS_EXE to pyhelios/bin/helios++"
    )


def _env_for(exe: Path) -> dict[str, str]:
    """PATH with the conda env's DLL folders (Windows) so the binary loads outside the env."""
    env = dict(os.environ)
    root = exe.parents[4] if len(exe.parents) > 4 else exe.parent  # envs/helios
    extra = [root / "Library" / "bin", root, root / "bin"]
    env["PATH"] = os.pathsep.join(
        [str(p) for p in extra if p.is_dir()] + [env.get("PATH", "")]
    )
    return env


def run_survey(
    survey: Path, out_dir: Path, threads: int = 4, helios: str | Path | None = None
) -> Path:
    """Run HELIOS++ on a survey; returns the directory holding ``legNNN_points.xyz``."""
    exe = find_helios(helios)
    pkg = exe.parent.parent  # .../pyhelios
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(exe),
        str(survey),
        "--output",
        str(out_dir),
        "-j",
        str(threads),
        "--assets",
        str(survey.parent),
        "--assets",
        str(pkg),
        "--assets",
        str(pkg / "data"),
        "--legacyEnergyModel",  # what the pyhelios entry point passes too
    ]
    log = out_dir / "helios.log"
    with open(log, "w", encoding="utf-8") as fh:
        rc = subprocess.call(
            cmd,
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=survey.parent,
            env=_env_for(exe),
        )
    if rc != 0:
        raise RuntimeError(f"helios++ exited with {rc}; see {log}")
    legs = sorted(out_dir.rglob("leg000_points.xyz"), key=lambda p: p.stat().st_mtime)
    if not legs:
        raise RuntimeError(f"helios++ wrote no point files under {out_dir}; see {log}")
    return legs[-1].parent


def read_legs(
    run_dir: Path, keep_ground: bool = False, chunk_rows: int = 2_000_000
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """xyz, hit object id and leg index from all ``legNNN_points.xyz`` in a run.

    Each file is streamed in ``chunk_rows`` row chunks (four columns parsed); ground
    returns (part 0) are dropped chunk by chunk unless ``keep_ground``.
    """
    import pandas as pd

    cols = [0, 1, 2, _XYZ_COLS["hit_object_id"]]
    xyz, part, leg = [], [], []
    for f in sorted(run_dir.glob("leg*_points.xyz")):
        idx = int(f.name[3:6])
        if f.stat().st_size == 0:
            continue
        reader = pd.read_csv(
            f,
            sep=r"\s+",
            header=None,
            usecols=cols,
            dtype={0: np.float64, 1: np.float64, 2: np.float64, cols[3]: np.int32},
            chunksize=chunk_rows,
            engine="c",
        )
        for chunk in reader:
            a = chunk[cols].to_numpy()
            p = a[:, 3].astype(np.int32)
            keep = slice(None) if keep_ground else p != 0
            xyz.append(np.ascontiguousarray(a[keep, :3], dtype=np.float64))
            part.append(p[keep])
            leg.append(np.full(len(part[-1]), idx, dtype=np.int32))
    if not xyz:
        return np.empty((0, 3)), np.empty(0, np.int32), np.empty(0, np.int32)
    return np.vstack(xyz), np.concatenate(part), np.concatenate(leg)


def scan(
    target: ScenePart,
    work_dir: Path,
    positions: list[ScanPosition],
    neighbours: list[ScenePart] | None = None,
    scanner: ScannerSetup | None = None,
    ground_half_size_m: float = 60.0,
    threads: int = 4,
    helios: str | Path | None = None,
    name: str = "synthetic_tls",
    keep_ground: bool = False,
) -> ScanResult:
    """Scan ``target`` (and ``neighbours``) from ``positions``; points relative to the target base."""
    scanner = scanner or ScannerSetup()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    ground = write_ground_obj(work_dir / "ground.obj", ground_half_size_m)
    parts = [
        (ground, "z", (0.0, 0.0, 0.0)),
        (Path(target.obj).resolve(), target.up_axis, target.offset),
    ]
    for nb in neighbours or []:
        parts.append((Path(nb.obj).resolve(), nb.up_axis, nb.offset))
    scene_path = work_dir / "scene.xml"
    scene_path.write_text(scene_xml(parts, "scene"), encoding="utf-8")
    survey = work_dir / "survey.xml"
    survey.write_text(
        survey_xml(name, scene_path, "scene", positions, scanner), encoding="utf-8"
    )
    run_dir = run_survey(survey, work_dir / "output", threads=threads, helios=helios)
    xyz, part, leg = read_legs(run_dir, keep_ground=keep_ground)
    xyz = xyz - np.asarray(target.offset, dtype=np.float64)
    return ScanResult(xyz, part, leg, run_dir, list(positions))


def scan_alone(
    obj: Path,
    work_dir: Path,
    n_positions: int = 4,
    distance_m: float = 10.0,
    up_axis: str = "z",
    window_half_deg: float | None = None,
    **kw,
) -> ScanResult:
    """Mode (a): one tree at the origin, ``n_positions`` tripods at ``distance_m``."""
    pos = ring_positions(n_positions, distance_m, window_half_deg=window_half_deg)
    return scan(ScenePart(Path(obj), up_axis=up_axis), work_dir, pos, **kw)


def scan_stand(
    obj: Path,
    neighbours: list[ScenePart],
    work_dir: Path,
    n_positions: int = 4,
    distance_m: float = 10.0,
    up_axis: str = "z",
    **kw,
) -> ScanResult:
    """Mode (b): the tree at the origin inside its neighbours; full 360 degree scans."""
    pos = ring_positions(n_positions, distance_m)
    return scan(
        ScenePart(Path(obj), up_axis=up_axis),
        work_dir,
        pos,
        neighbours=neighbours,
        **kw,
    )


def save(result: ScanResult, out_dir: Path) -> dict[str, Path]:
    """Write ``target.npy`` (C's ``read_points`` input), ``all.npz`` (xyz, part, position)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"target": out_dir / "target.npy", "all": out_dir / "all.npz"}
    np.save(paths["target"], result.tree(1))
    np.savez_compressed(
        paths["all"], xyz=result.xyz, part=result.part, position=result.position
    )
    return paths


# --------------------------------------------------------------------------- CLI


def _parse_neighbours(spec: Path | None, up: str) -> list[ScenePart]:
    """CSV ``obj,x,y[,z]`` per neighbour."""
    if spec is None:
        return []
    out = []
    for line in Path(spec).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lower().startswith("obj"):
            continue
        cols = [c.strip() for c in line.split(",")]
        z = float(cols[3]) if len(cols) > 3 and cols[3] else 0.0
        out.append(ScenePart(Path(cols[0]), (float(cols[1]), float(cols[2]), z), up))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Virtual TLS scan of a tree OBJ with HELIOS++"
    )
    ap.add_argument("obj", type=Path, help="target tree OBJ, stem base at its origin")
    ap.add_argument("out", type=Path, help="work and output directory")
    ap.add_argument("--up", default="z", choices=("z", "y"))
    ap.add_argument("--positions", type=int, default=4)
    ap.add_argument("--distance", type=float, default=10.0)
    ap.add_argument("--neighbours", type=Path, help="CSV obj,x,y[,z] (stand mode)")
    ap.add_argument(
        "--window", type=float, help="alone mode: head half-angle around the tree"
    )
    ap.add_argument("--resolution", type=float, default=ScannerSetup.resolution_deg)
    ap.add_argument("--pulse-freq", type=int, default=ScannerSetup.pulse_freq_hz)
    ap.add_argument("--scanner", default=ScannerSetup.scanner_id)
    ap.add_argument("--height", type=float, default=ScannerSetup.height_m)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--keep-ground", action="store_true", help="keep ground returns")
    ap.add_argument(
        "--helios",
        help="path to helios++ (default: HELIOS_EXE, PATH, conda env helios)",
    )
    a = ap.parse_args(argv)
    scanner = ScannerSetup(
        a.scanner, a.pulse_freq, resolution_deg=a.resolution, height_m=a.height
    )
    nbs = _parse_neighbours(a.neighbours, a.up)
    common = {
        "scanner": scanner,
        "threads": a.threads,
        "helios": a.helios,
        "keep_ground": a.keep_ground,
    }
    if nbs:
        res = scan_stand(a.obj, nbs, a.out, a.positions, a.distance, a.up, **common)
    else:
        res = scan_alone(
            a.obj, a.out, a.positions, a.distance, a.up, a.window, **common
        )
    paths = save(res, a.out)
    ids, n = np.unique(res.part, return_counts=True)
    counts = {int(k): int(v) for k, v in zip(ids, n, strict=True)}
    print(f"{len(res.xyz)} points, per part {counts}; target -> {paths['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
