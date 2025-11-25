#!/usr/bin/env python3
"""Cython compilation orchestration script.

Replaces the legacy unified compiler/mypyc pipeline with a slimmer Cython-first
workflow. Configured via `[tool.cython-compiler]` in `pyproject.toml`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path
from typing import Any, Callable, cast

from setuptools import Distribution, Extension
from setuptools.command.build_ext import build_ext

try:  # Python 3.11+
    import tomllib as _tomllib_mod
except ModuleNotFoundError:  # pragma: no cover - fallback for <3.11
    import tomli as _tomllib_mod  # noqa: F401

from Cython.Build import cythonize as _cythonize_raw  # type: ignore[import-untyped]

# Cast to Any to suppress Pyright "partially unknown" errors from untyped stubs
_tomllib: Any = _tomllib_mod
_cythonize: Callable[..., list[Any]] = cast(Any, _cythonize_raw)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "build" / "cython" / "state.json"


@dataclass(frozen=True)
class Target:
    name: str
    module: str
    source: Path
    group: str
    stage: str
    description: str


@dataclass(frozen=True)
class CompilerConfig:
    build_dir: Path
    cache_dir: Path
    language_level: int
    annotate: bool
    profile: bool
    force_rebuild: bool
    summary_file: Path
    baseline_file: Path
    environment_file: Path
    metrics: list[str]
    alert_thresholds: dict[str, float]
    test_command: list[str]
    parallel: int | None
    optimize: str | None
    extra_compile_args: list[str]


def _load_pyproject(pyproject: Path) -> dict[str, Any]:
    with pyproject.open("rb") as fh:
        return cast(dict[str, Any], _tomllib.load(fh))


def load_config(pyproject: Path) -> tuple[CompilerConfig, list[Target]]:
    data = _load_pyproject(pyproject)
    tool = data.get("tool", {})
    raw = tool.get("cython-compiler")
    if raw is None:
        raise SystemExit("pyproject.toml 缺少 [tool.cython-compiler] 配置")

    build_dir = PROJECT_ROOT / raw.get("build_dir", "build/cython")
    cache_dir = PROJECT_ROOT / raw.get("cache_dir", "build/cython/.cache")
    summary_file = PROJECT_ROOT / raw.get("summary_file", "build/cython/compile_report.json")
    baseline_file = PROJECT_ROOT / raw.get(
        "baseline_file", "build/cython/baseline_pre_migration.json"
    )
    environment_file = PROJECT_ROOT / raw.get("environment_file", "build/cython/environment.json")

    parallel_setting = raw.get("parallel", "auto")
    if isinstance(parallel_setting, str):
        if parallel_setting.lower() == "auto":
            parallel = os.cpu_count()
        elif parallel_setting.lower() in {"off", "none"}:
            parallel = None
        else:
            raise SystemExit(f"未知的 parallel 設定: {parallel_setting}")
    else:
        parallel = int(parallel_setting)

    # Optional optimization hints for C compiler; purely additive.
    optimize: str | None = None
    extra_compile_args: list[str] = []

    optimize_raw = raw.get("optimize")
    if optimize_raw is not None:
        optimize = str(optimize_raw)
        if optimize not in {"O0", "O1", "O2", "O3"}:
            raise SystemExit(f"未知的 optimize 設定: {optimize}")
        extra_compile_args.append(f"-{optimize}")

    if raw.get("march_native", False):
        extra_compile_args.append("-march=native")

    config = CompilerConfig(
        build_dir=build_dir,
        cache_dir=cache_dir,
        language_level=int(raw.get("language_level", 3)),
        annotate=bool(raw.get("annotate", True)),
        profile=bool(raw.get("profile", False)),
        force_rebuild=bool(raw.get("force_rebuild", False)),
        summary_file=summary_file,
        baseline_file=baseline_file,
        environment_file=environment_file,
        metrics=list(raw.get("metrics", [])),
        alert_thresholds=dict(raw.get("alert-thresholds", {})),
        test_command=list(raw.get("test_command", ["pytest", "-m", "performance", "-q"])),
        parallel=parallel,
        optimize=optimize,
        extra_compile_args=extra_compile_args,
    )

    targets_cfg = raw.get("targets", [])
    if not targets_cfg:
        raise SystemExit("[tool.cython-compiler.targets] 不可為空")

    targets: list[Target] = []
    for entry in targets_cfg:
        try:
            target = Target(
                name=str(entry["name"]),
                module=str(entry["module"]),
                source=(PROJECT_ROOT / entry["source"]).resolve(),
                group=str(entry.get("group", "default")),
                stage=str(entry.get("stage", "unspecified")),
                description=str(entry.get("description", "")),
            )
        except KeyError as exc:  # pragma: no cover - config errors
            raise SystemExit(f"target 定義缺少欄位: {exc}") from exc
        targets.append(target)

    return config, targets


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _hash_options(config: CompilerConfig, target: Target) -> str:
    payload = json.dumps(
        {
            "language_level": config.language_level,
            "annotate": config.annotate,
            "profile": config.profile,
            "module": target.module,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def needs_build(target: Target, config: CompilerConfig, state: dict[str, Any], force: bool) -> bool:
    if force or config.force_rebuild:
        return True
    prev = state.get(target.name)
    if not prev:
        return True
    source_hash = _hash_file(target.source)
    options_hash = _hash_options(config, target)
    return prev.get("source") != source_hash or prev.get("options") != options_hash


def _extension_relative_path(module: str) -> Path:
    parts = module.split(".")
    rel = Path(*parts)
    return rel


def _copy_artifact(source: Path, module: str) -> Path:
    rel = _extension_relative_path(module)
    dest_dir = PROJECT_ROOT / rel.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    module_name = rel.name
    for suffix in EXTENSION_SUFFIXES:
        candidate = dest_dir / f"{module_name}{suffix}"
        if candidate.exists():
            candidate.unlink()

    destination = dest_dir / source.name
    shutil.copy2(source, destination)
    return destination


def build_single_target(
    target: Target,
    config: CompilerConfig,
) -> tuple[dict[str, Any], Path | None]:
    build_root = config.build_dir / "lib" / target.name
    temp_root = config.build_dir / "temp" / target.name
    build_root.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    directives = {"language_level": config.language_level}
    if config.profile:
        directives["profile"] = True

    extensions = [
        Extension(
            name=target.module,
            sources=[str(target.source)],
            extra_compile_args=config.extra_compile_args,
        )
    ]
    cythonized: list[Extension] = _cythonize(
        extensions,
        annotate=config.annotate,
        nthreads=config.parallel or 0,
        compiler_directives=directives,
    )
    dist = Distribution({"name": f"cython-{target.name}", "ext_modules": cythonized})
    cmd = build_ext(dist)
    cmd.build_lib = str(build_root)
    cmd.build_temp = str(temp_root)
    cmd.ensure_finalized()
    cmd.run()

    rel = _extension_relative_path(target.module)
    artifact_path: Path | None = None
    for suffix in EXTENSION_SUFFIXES:
        candidate = build_root / rel.with_suffix(suffix)
        if candidate.exists():
            artifact_path = candidate
            break
    if artifact_path is None:
        raise RuntimeError(f"找不到產生的檔案: {target.module}")

    final_path = _copy_artifact(artifact_path, target.module)
    return {"artifact": str(final_path.relative_to(PROJECT_ROOT))}, final_path


def compile_targets(
    config: CompilerConfig,
    targets: list[Target],
    selected: set[str] | None,
    *,
    force: bool,
    refresh_baseline: bool,
) -> int:
    config.build_dir.mkdir(parents=True, exist_ok=True)
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    state = load_state()
    summary: list[dict[str, Any]] = []
    compiled = 0
    failures = 0

    for target in targets:
        if selected and target.name not in selected and target.module not in selected:
            continue

        needs = needs_build(target, config, state, force)
        print(f"➡️  {target.name}: {'build' if needs else 'skip'}")
        if not needs:
            summary.append({"name": target.name, "module": target.module, "status": "cached"})
            continue

        start = time.perf_counter()
        try:
            result, _artifact = build_single_target(target, config)
            duration = time.perf_counter() - start
            compiled += 1
            record = {
                "name": target.name,
                "module": target.module,
                "status": "succeeded",
                "duration_seconds": round(duration, 3),
            }
            record.update(result)
            summary.append(record)
            state[target.name] = {
                "source": _hash_file(target.source),
                "options": _hash_options(config, target),
                "artifact": result["artifact"],
            }
        except Exception as exc:  # pragma: no cover - build error surfaces here
            failures += 1
            summary.append(
                {
                    "name": target.name,
                    "module": target.module,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"❌ {target.name} failed: {exc}")

    save_state(state)
    write_summary(config.summary_file, summary)

    if refresh_baseline and failures == 0:
        run_baseline(config)

    print(f"✅ Compiled {compiled} modules ({len(summary)} checked). Failures: {failures}")
    return 1 if failures else 0


def write_summary(summary_file: Path, summary: list[dict[str, Any]]) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": summary,
    }
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    summary_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_baseline(config: CompilerConfig) -> None:
    print("📊 重新建立性能基線...")
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "performance_baseline_test.py"),
            "--output",
            str(config.baseline_file),
        ],
        check=True,
    )


def run_tests(config: CompilerConfig) -> int:
    print("🧪 執行測試:", " ".join(config.test_command))
    return subprocess.run(config.test_command, cwd=PROJECT_ROOT).returncode


def clean_outputs(config: CompilerConfig) -> None:
    print("🧹 清理 Cython 產物...")
    shutil.rmtree(config.build_dir, ignore_errors=True)
    STATE_FILE.unlink(missing_ok=True)
    # Remove compiled shared objects under src/cython_ext
    ext_dir = PROJECT_ROOT / "src" / "cython_ext"
    if ext_dir.exists():
        for suffix in EXTENSION_SUFFIXES:
            for so_file in ext_dir.rglob(f"*{suffix}"):
                so_file.unlink(missing_ok=True)


def show_status(config: CompilerConfig) -> None:
    if not config.summary_file.exists():
        print("尚未執行過編譯。")
        return
    data = json.loads(config.summary_file.read_text(encoding="utf-8"))
    print(f"📄 最新報告: {config.summary_file} ({data.get('timestamp')})")
    for entry in data.get("results", []):
        print(
            f" - {entry['name']:>24} :: {entry['status']}"
            + (f" ({entry.get('artifact')})" if entry.get("artifact") else "")
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cython 傳統模組編譯器")
    parser.add_argument(
        "command",
        choices=["compile", "clean", "status", "test"],
        nargs="?",
        default="compile",
        help="動作（預設: compile）",
    )
    parser.add_argument("--pyproject", default="pyproject.toml", help="pyproject 路徑")
    parser.add_argument("--module", action="append", help="僅編譯指定模組/target 名稱，可重複")
    parser.add_argument("--force", action="store_true", help="忽略快取強制重新編譯")
    parser.add_argument(
        "--optimize",
        choices=["O0", "O1", "O2", "O3"],
        help="覆寫 C 編譯優化等級（O0/O1/O2/O3），預設沿用設定檔或編譯器預設值",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        help="覆寫並行編譯執行緒數，預設沿用 [tool.cython-compiler].parallel",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="強制啟用增量編譯（忽略設定檔中的 force_rebuild）",
    )
    parser.add_argument("--refresh-baseline", action="store_true", help="編譯成功後刷新性能基線")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config, targets = load_config(PROJECT_ROOT / args.pyproject)

    # Allow CLI overrides to adjust config according to spec requirements.
    if args.parallel is not None or args.optimize is not None or args.incremental:
        optimize = args.optimize if args.optimize is not None else config.optimize

        extra_compile_args = list(config.extra_compile_args)
        if args.optimize is not None:
            # Remove any existing -O* flags to avoid duplicates.
            extra_compile_args = [f for f in extra_compile_args if not f.startswith("-O")]
            extra_compile_args.append(f"-{args.optimize}")

        force_rebuild = False if args.incremental else config.force_rebuild

        config = replace(
            config,
            parallel=args.parallel if args.parallel is not None else config.parallel,
            optimize=optimize,
            extra_compile_args=extra_compile_args,
            force_rebuild=force_rebuild,
        )

    force = args.force
    if args.incremental:
        # Incremental builds should not force recompilation.
        force = False

    selected = set(args.module or []) if args.module else None

    if args.command == "compile":
        exit_code = compile_targets(
            config,
            targets,
            selected,
            force=force,
            refresh_baseline=args.refresh_baseline,
        )
        raise SystemExit(exit_code)
    if args.command == "clean":
        clean_outputs(config)
        return
    if args.command == "status":
        show_status(config)
        return
    if args.command == "test":
        raise SystemExit(run_tests(config))


if __name__ == "__main__":
    main()
