#!/usr/bin/env python3
"""
Validate the cached data/ directory before it is committed/pushed upstream.

Guards against the "empty data" failure mode: when opm render fails (e.g. the
container has no pull secret), the reset leaves behind 0-byte or trivially-empty
files. Pushing those upstream silently breaks the app for everyone.

Exit code 0 = data looks complete and safe to push.
Exit code 1 = validation failed (details printed); caller must NOT commit/push.

Usage: validate-data.py [DATA_DIR]   (default: ./data)
"""

import json
import os
import sys

# Core files that must always exist and be non-trivial.
CORE_FILES = [
    "ocp-versions.json",
    "ocp-channels.json",
    "channel-releases.json",
]

# The default catalog whose operator list must be present + non-empty for every
# version that advertises it in its catalogs-<ver>.json.
DEFAULT_CATALOG_INDEX = "redhat-operator-index"


def fail(errors):
    print("\n[validate-data] VALIDATION FAILED:")
    for e in errors:
        print(f"  - {e}")
    print(f"\n[validate-data] {len(errors)} problem(s) found. Data is NOT safe to push.")
    sys.exit(1)


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    errors = []

    if not os.path.isdir(data_dir):
        fail([f"data directory '{data_dir}' does not exist"])

    files = sorted(
        f for f in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, f))
    )

    if not files:
        fail([f"data directory '{data_dir}' is empty"])

    json_cache = {}

    def load_json(fname):
        if fname in json_cache:
            return json_cache[fname]
        path = os.path.join(data_dir, fname)
        with open(path) as fh:
            data = json.load(fh)
        json_cache[fname] = data
        return data

    # 1) No 0-byte files, and all *.json must parse.
    for f in files:
        path = os.path.join(data_dir, f)
        if os.path.getsize(path) == 0:
            errors.append(f"{f}: file is 0 bytes (opm render / refresh likely failed)")
            continue
        if f.endswith(".json"):
            try:
                data = load_json(f)
            except Exception as e:
                errors.append(f"{f}: invalid JSON ({e})")
                continue
            # Reject trivially-empty JSON containers.
            if data in ({}, [], None, ""):
                errors.append(f"{f}: JSON is empty ({json.dumps(data)})")

    # 2) Core files present and non-empty.
    for cf in CORE_FILES:
        if cf not in files:
            errors.append(f"{cf}: required core file is missing")
        else:
            try:
                data = load_json(cf)
                if not data:
                    errors.append(f"{cf}: core file has no content")
            except Exception:
                pass  # already reported above

    # 3) For each catalogs-<ver>.json, verify it lists catalogs and that the
    #    default catalog's operator list exists and is non-empty.
    catalog_files = [f for f in files if f.startswith("catalogs-") and f.endswith(".json")]
    if not catalog_files:
        errors.append("no catalogs-*.json files found — catalog data was not generated")

    for cf in catalog_files:
        ver = cf[len("catalogs-"):-len(".json")]
        try:
            catalogs = load_json(cf)
        except Exception:
            continue  # already reported

        # catalogs-<ver>.json is {"<ver>": [ {...catalog...}, ... ]}
        entries = catalogs.get(ver) if isinstance(catalogs, dict) else None
        if not entries:
            errors.append(f"{cf}: no catalog entries for version {ver}")
            continue

        advertises_default = any(
            DEFAULT_CATALOG_INDEX in (c.get("url", "")) for c in entries
        )
        if advertises_default:
            ops_file = f"operators-{DEFAULT_CATALOG_INDEX}-{ver}.json"
            if ops_file not in files:
                errors.append(
                    f"{ver}: catalogs list {DEFAULT_CATALOG_INDEX} but {ops_file} is missing"
                )
            else:
                try:
                    ops = load_json(ops_file)
                    count = ops.get("count", 0) if isinstance(ops, dict) else 0
                    ops_list = ops.get("operators", []) if isinstance(ops, dict) else []
                    if count == 0 or not ops_list:
                        errors.append(
                            f"{ops_file}: default catalog has 0 operators (opm render likely failed for {ver})"
                        )
                except Exception:
                    pass  # already reported

    # 4) Reverse check: every version that produced default-catalog operator
    #    data must also have a catalogs-<ver>.json. Catches the case where the
    #    catalog step silently failed (e.g. oc-mirror timeout) while operators
    #    succeeded — which would otherwise slip through since check #3 only
    #    inspects versions that already have a catalogs file.
    ops_prefix = f"operators-{DEFAULT_CATALOG_INDEX}-"
    versions_with_ops = sorted(
        f[len(ops_prefix):-len(".json")]
        for f in files
        if f.startswith(ops_prefix) and f.endswith(".json")
    )
    for ver in versions_with_ops:
        cf = f"catalogs-{ver}.json"
        if cf not in files:
            errors.append(
                f"{ver}: has operator data but {cf} is missing (catalog refresh failed for this version)"
            )

    # 5) No leftover intermediate files (these indicate a mid-refresh crash).
    for f in files:
        if f.endswith("-index.json") or f.endswith("-data.json") or f.endswith("-channel.json"):
            errors.append(f"{f}: leftover intermediate file (refresh did not complete cleanly)")

    if errors:
        fail(errors)

    print(f"[validate-data] OK — {len(files)} files validated in '{data_dir}'.")
    print(f"[validate-data]   catalogs: {len(catalog_files)} version(s); "
          f"operator files: {sum(1 for f in files if f.startswith('operators-'))}")
    sys.exit(0)


if __name__ == "__main__":
    main()
