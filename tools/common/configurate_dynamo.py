#!/usr/bin/env python
"""Dynamo Configuration Manager - Manage CLI environments.

Usage:
    configurate-dynamo show                          # Display active config
    configurate-dynamo detect [--save]               # Auto-detect installations
    configurate-dynamo switch <profile>              # Switch active environment
    configurate-dynamo validate [--profile NAME]     # Health-check environment
    configurate-dynamo fix [--profile NAME] [--dry-run]  # Fix known issues
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import click
import yaml

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.common.config import (
    get_config,
    get_config_path,
    get_dynamo_cli_path,
    invalidate_config_cache,
)

# Critical DLLs that must be present alongside DynamoCLI.exe
CRITICAL_DEPENDENCIES = [
    "System.Configuration.ConfigurationManager.dll",
]

# Revit versions to scan for DynamoForRevit installations
REVIT_YEARS = range(2021, 2027)


def output_result(data: dict):
    """Output result to stdout as JSON."""
    click.echo(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _load_raw_config() -> dict:
    """Load the raw YAML config as a dict."""
    config_path = get_config_path()
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _save_config(data: dict) -> None:
    """Write the config dict back to the YAML file."""
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    invalidate_config_cache()


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


def _detect_framework(cli_dir: Path) -> str:
    """Detect .NET framework from runtimeconfig.json.

    Returns 'net8.0', 'net48', or 'unknown'.
    """
    runtimeconfig = cli_dir / "DynamoCLI.runtimeconfig.json"
    if runtimeconfig.exists():
        try:
            with open(runtimeconfig, "r", encoding="utf-8") as f:
                rc = json.load(f)
            tfm = rc.get("runtimeOptions", {}).get("tfm", "")
            if tfm:
                return tfm
            # Fallback: check framework name
            fw_name = (
                rc.get("runtimeOptions", {})
                .get("framework", {})
                .get("name", "")
            )
            if "NETCore" in fw_name or "Microsoft.NETCore" in fw_name:
                return "net8.0"
        except (json.JSONDecodeError, KeyError):
            pass

    # Legacy .exe.config indicates .NET Framework
    exe_config = cli_dir / "DynamoCLI.exe.config"
    if exe_config.exists():
        return "net48"

    return "unknown"


def _detect_engine(framework: str) -> str:
    """Infer the Python engine from the framework version."""
    if framework == "net48":
        return "IronPython2"
    return "CPython3"


def _detect_version(cli_dir: Path) -> str:
    """Attempt to detect the Dynamo version from package.json or directory name."""
    pkg = cli_dir / "pkg.json"
    if pkg.exists():
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("version", "unknown")
        except (json.JSONDecodeError, KeyError):
            pass
    return "3.3"


def _check_missing_dependencies(cli_path: str) -> list[str]:
    """Return list of critical DLLs missing from the CLI directory."""
    cli_dir = Path(cli_path).parent
    missing = []
    for dll in CRITICAL_DEPENDENCIES:
        if not (cli_dir / dll).exists():
            missing.append(dll)
    return missing


def _detect_sandboxed() -> Optional[dict]:
    """Detect sandboxed DynamoCLI installation."""
    root = _project_root()
    sandboxed_cli = root / ".sandboxed" / "DynamoCLI.exe"
    if not sandboxed_cli.exists():
        return None

    cli_dir = sandboxed_cli.parent
    framework = _detect_framework(cli_dir)
    return {
        "name": "sandbox",
        "cli_path": str(sandboxed_cli),
        "version": _detect_version(cli_dir),
        "engine": _detect_engine(framework),
        "framework": framework,
        "missing_deps": _check_missing_dependencies(str(sandboxed_cli)),
    }


def _detect_revit_installs() -> list[dict]:
    """Scan for DynamoForRevit installations across Revit versions."""
    results = []
    for year in REVIT_YEARS:
        cli_path = Path(
            f"C:\\Program Files\\Autodesk\\Revit {year}\\AddIns\\DynamoForRevit\\DynamoCLI.exe"
        )
        if cli_path.exists():
            cli_dir = cli_path.parent
            framework = _detect_framework(cli_dir)
            results.append({
                "name": f"revit_{year}",
                "cli_path": str(cli_path),
                "version": _detect_version(cli_dir),
                "engine": _detect_engine(framework),
                "framework": framework,
                "missing_deps": _check_missing_dependencies(str(cli_path)),
            })
    return results


def _find_donor_file(filename: str) -> Optional[Path]:
    """Locate a DLL in the sandboxed installation for copying."""
    root = _project_root()
    donor = root / ".sandboxed" / filename
    if donor.exists():
        return donor
    return None


# ---------------------------------------------------------------------------
# Public functions (one per subcommand)
# ---------------------------------------------------------------------------

def show_config() -> dict:
    """Display the current active configuration."""
    config = get_config()
    raw = _load_raw_config()

    dynamo = config.get("dynamo", {})
    active_profile = dynamo.get("active_profile", "<not set>")
    profiles = raw.get("profiles", {})

    return {
        "success": True,
        "active_profile": active_profile,
        "cli_path": dynamo.get("cli_path", "<not set>"),
        "version": dynamo.get("version", "<not set>"),
        "engine": dynamo.get("engine", "<not set>"),
        "default_timeout": dynamo.get("default_timeout", 300),
        "available_profiles": list(profiles.keys()) if profiles else [],
    }


def detect_environments(save: bool = False) -> dict:
    """Auto-detect installed Dynamo CLI environments."""
    found: list[dict] = []

    sandbox = _detect_sandboxed()
    if sandbox:
        found.append(sandbox)

    revit_installs = _detect_revit_installs()
    found.extend(revit_installs)

    if not found:
        return {
            "success": True,
            "message": "No Dynamo CLI installations detected.",
            "environments": [],
        }

    result: dict[str, Any] = {
        "success": True,
        "environments": found,
    }

    if save:
        raw = _load_raw_config()
        profiles: dict[str, dict] = {}
        for env in found:
            profiles[env["name"]] = {
                "cli_path": env["cli_path"],
                "version": env["version"],
                "engine": env["engine"],
                "framework": env["framework"],
            }
        raw["profiles"] = profiles
        _save_config(raw)
        result["saved"] = True
        result["message"] = f"Saved {len(profiles)} profile(s) to config."

    return result


def switch_profile(profile_name: str) -> dict:
    """Switch the active CLI environment to the given profile."""
    raw = _load_raw_config()
    profiles = raw.get("profiles", {})

    if profile_name not in profiles:
        available = list(profiles.keys())
        return {
            "success": False,
            "error": f"Profile '{profile_name}' not found. Available: {available}",
        }

    profile = profiles[profile_name]
    cli_path = profile["cli_path"]

    if not Path(cli_path).exists():
        return {
            "success": False,
            "error": f"CLI executable not found: {cli_path}",
        }

    # Update the top-level dynamo section
    raw.setdefault("dynamo", {})
    raw["dynamo"]["cli_path"] = cli_path
    raw["dynamo"]["version"] = profile.get("version", raw["dynamo"].get("version", "3.3"))
    raw["dynamo"]["engine"] = profile.get("engine", raw["dynamo"].get("engine", "CPython3"))
    raw["dynamo"]["active_profile"] = profile_name

    _save_config(raw)

    return {
        "success": True,
        "message": f"Switched to profile '{profile_name}'.",
        "cli_path": cli_path,
        "version": raw["dynamo"]["version"],
        "engine": raw["dynamo"]["engine"],
    }


def validate_environment(profile_name: Optional[str] = None) -> dict:
    """Health-check a Dynamo CLI environment.

    If profile_name is None, validates the currently active config.
    """
    if profile_name:
        raw = _load_raw_config()
        profiles = raw.get("profiles", {})
        if profile_name not in profiles:
            return {
                "success": False,
                "error": f"Profile '{profile_name}' not found.",
            }
        cli_path = profiles[profile_name]["cli_path"]
    else:
        cli_path = get_dynamo_cli_path()

    checks: list[dict] = []

    # Check 1: CLI executable exists
    cli_exists = Path(cli_path).exists()
    checks.append({
        "check": "cli_exists",
        "passed": cli_exists,
        "detail": cli_path,
    })

    if not cli_exists:
        return {
            "success": False,
            "checks": checks,
            "summary": "CLI executable not found.",
        }

    # Check 2: Critical dependencies
    missing = _check_missing_dependencies(cli_path)
    checks.append({
        "check": "critical_dependencies",
        "passed": len(missing) == 0,
        "detail": f"missing: {missing}" if missing else "all present",
    })

    # Check 3: Quick execution test
    try:
        # Run CLI with a non-existent graph to verify it can at least start
        result = subprocess.run(
            [cli_path, "-o", "NONEXISTENT_FILE.dyn"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(Path(cli_path).parent),
        )
        stderr_lower = (result.stderr or "").lower()
        stdout_lower = (result.stdout or "").lower()
        combined = stderr_lower + stdout_lower

        has_assembly_error = "could not load file or assembly" in combined
        checks.append({
            "check": "execution_test",
            "passed": not has_assembly_error,
            "detail": (
                "assembly loading error detected"
                if has_assembly_error
                else "CLI starts without assembly errors"
            ),
        })
    except subprocess.TimeoutExpired:
        checks.append({
            "check": "execution_test",
            "passed": False,
            "detail": "timed out after 30s",
        })
    except Exception as e:
        checks.append({
            "check": "execution_test",
            "passed": False,
            "detail": str(e),
        })

    all_passed = all(c["passed"] for c in checks)
    return {
        "success": all_passed,
        "checks": checks,
        "summary": "All checks passed." if all_passed else "Some checks failed.",
    }


def fix_environment(profile_name: Optional[str] = None, dry_run: bool = False) -> dict:
    """Fix known issues in a Dynamo CLI environment.

    Currently fixes: missing System.Configuration.ConfigurationManager.dll
    """
    if profile_name:
        raw = _load_raw_config()
        profiles = raw.get("profiles", {})
        if profile_name not in profiles:
            return {
                "success": False,
                "error": f"Profile '{profile_name}' not found.",
            }
        cli_path = profiles[profile_name]["cli_path"]
    else:
        cli_path = get_dynamo_cli_path()

    cli_dir = Path(cli_path).parent
    if not cli_dir.exists():
        return {
            "success": False,
            "error": f"CLI directory not found: {cli_dir}",
        }

    actions: list[dict] = []

    # Fix missing critical dependencies
    missing = _check_missing_dependencies(cli_path)
    for dll in missing:
        donor = _find_donor_file(dll)
        if donor is None:
            actions.append({
                "action": "copy_dll",
                "file": dll,
                "status": "skipped",
                "reason": "donor file not found in .sandboxed/",
            })
            continue

        dest = cli_dir / dll
        if dry_run:
            actions.append({
                "action": "copy_dll",
                "file": dll,
                "source": str(donor),
                "destination": str(dest),
                "status": "dry_run",
            })
        else:
            try:
                shutil.copy2(str(donor), str(dest))
                actions.append({
                    "action": "copy_dll",
                    "file": dll,
                    "source": str(donor),
                    "destination": str(dest),
                    "status": "copied",
                })
            except PermissionError:
                actions.append({
                    "action": "copy_dll",
                    "file": dll,
                    "source": str(donor),
                    "destination": str(dest),
                    "status": "failed",
                    "reason": (
                        "Permission denied. Run as administrator to copy "
                        "files into Program Files."
                    ),
                })
            except Exception as e:
                actions.append({
                    "action": "copy_dll",
                    "file": dll,
                    "source": str(donor),
                    "destination": str(dest),
                    "status": "failed",
                    "reason": str(e),
                })

    if not missing:
        return {
            "success": True,
            "message": "No issues detected. All critical dependencies are present.",
            "actions": [],
        }

    all_ok = all(
        a["status"] in ("copied", "dry_run") for a in actions
    )
    return {
        "success": all_ok,
        "dry_run": dry_run,
        "actions": actions,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Manage Dynamo CLI environments."""


@cli.command()
def show():
    """Display current active configuration."""
    try:
        result = show_config()
        output_result(result)
    except Exception as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)


@cli.command()
@click.option("--save", is_flag=True, help="Save detected profiles to config file")
def detect(save: bool):
    """Auto-detect installed Dynamo CLI environments."""
    try:
        result = detect_environments(save=save)
        output_result(result)
    except Exception as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)


@cli.command()
@click.argument("profile_name")
def switch(profile_name: str):
    """Switch the active CLI environment to PROFILE_NAME."""
    try:
        result = switch_profile(profile_name)
        output_result(result)
        if not result.get("success"):
            sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)


@cli.command()
@click.option("--profile", "profile_name", default=None, help="Profile name to validate (default: active)")
def validate(profile_name: Optional[str]):
    """Health-check a Dynamo CLI environment."""
    try:
        result = validate_environment(profile_name=profile_name)
        output_result(result)
        if not result.get("success"):
            sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)


@cli.command()
@click.option("--profile", "profile_name", default=None, help="Profile name to fix (default: active)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
def fix(profile_name: Optional[str], dry_run: bool):
    """Fix known issues in a Dynamo CLI environment."""
    try:
        result = fix_environment(profile_name=profile_name, dry_run=dry_run)
        output_result(result)
        if not result.get("success"):
            sys.exit(1)
    except Exception as e:
        output_result({"success": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    cli()
