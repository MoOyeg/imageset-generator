"""
Maintenance Blueprint — Data integrity check, reset, and refresh-all endpoints.
"""

import json
import os
import traceback
from datetime import datetime
from flask import Blueprint, Response, stream_with_context, jsonify, current_app

from routes.shared import (
    RESET_MIN_VERSION,
    CATALOG_BASE_URLS,
    sse_event,
    _reset_refresh_versions,
    _reset_refresh_channels,
    _reset_save_channels,
    _reset_refresh_catalogs,
    _reset_refresh_releases,
    _reset_refresh_operators,
    _reset_refresh_dependencies,
)
from routes.ocp import do_refresh_versions, do_refresh_ocp_channels, do_refresh_ocp_releases
from routes.operators import do_refresh_ocp_operators

maintenance_bp = Blueprint('maintenance', __name__)

# Module-level state flags
_reset_in_progress = False
_check_in_progress = False


@maintenance_bp.route("/check", methods=["POST"])
def check_data_integrity():
    """Check all cached data files for integrity and redownload any faulty ones via SSE streaming."""
    global _check_in_progress, _reset_in_progress

    if _check_in_progress:
        return jsonify({
            'status': 'error',
            'message': 'A check is already in progress. Please wait for it to complete.'
        }), 409

    if _reset_in_progress:
        return jsonify({
            'status': 'error',
            'message': 'A reset is in progress. Please wait for it to complete.'
        }), 409

    def generate():
        global _check_in_progress
        _check_in_progress = True
        failures = []
        fixed_count = 0
        total_checked = 0

        try:
            # --- Load versions ---
            yield sse_event("log", "Loading OCP versions...")
            versions_file = os.path.join("data", "ocp-versions.json")
            versions = []
            try:
                if os.path.exists(versions_file):
                    with open(versions_file, 'r') as f:
                        data = json.load(f)
                    versions = data.get("releases", [])
                if not versions:
                    raise ValueError("No versions found in file")
                yield sse_event("log", f"  Loaded {len(versions)} versions from static file.")
            except Exception as e:
                yield sse_event("log", f"  FAILED: {str(e)} — redownloading...")
                try:
                    versions = _reset_refresh_versions()
                    failures.append({"version": "-", "type": "versions", "detail": "ocp-versions.json missing/corrupt", "fixed": True})
                    fixed_count += 1
                    yield sse_event("log", f"  FIXED: Downloaded {len(versions)} versions.")
                except Exception as e2:
                    failures.append({"version": "-", "type": "versions", "detail": f"ocp-versions.json — repair failed: {str(e2)}", "fixed": False})
                    yield sse_event("log", f"  ERROR: Could not repair versions: {str(e2)}")
                    yield sse_event("error", json.dumps({"status": "error", "message": f"Cannot load versions: {str(e2)}", "failures": failures}))
                    return

            # Filter to >= RESET_MIN_VERSION
            filtered = []
            min_parts = tuple(map(int, RESET_MIN_VERSION.split('.')))
            for v in versions:
                try:
                    if tuple(map(int, v.split('.'))) >= min_parts:
                        filtered.append(v)
                except ValueError:
                    continue
            filtered.sort(key=lambda x: tuple(map(int, x.split('.'))))
            yield sse_event("log", f"  Checking {len(filtered)} versions (>= {RESET_MIN_VERSION}): {', '.join(filtered)}\n")

            # --- Load channels file once (shared across versions) ---
            channels_file = os.path.join("data", "ocp-channels.json")
            all_channels = {}
            channels_modified = False
            try:
                if os.path.exists(channels_file):
                    with open(channels_file, 'r') as f:
                        all_channels = json.load(f).get("channels", {})
            except Exception:
                all_channels = {}

            # --- Load releases file once ---
            releases_file = os.path.join("data", "channel-releases.json")
            all_releases = {}
            try:
                if os.path.exists(releases_file):
                    with open(releases_file, 'r') as f:
                        all_releases = json.load(f).get("channel_releases", {})
            except Exception:
                all_releases = {}

            # --- Check each version ---
            for idx, v in enumerate(filtered):
                step = idx + 1
                yield sse_event("progress", json.dumps({"step": step, "total": len(filtered), "description": f"Checking version {v}"}))
                yield sse_event("log", f"--- Checking version {v} ({step}/{len(filtered)}) ---")

                # Check channels
                total_checked += 1
                version_channels = all_channels.get(v, [])
                if not version_channels:
                    yield sse_event("log", f"  Channels: MISSING — redownloading...")
                    try:
                        ch = _reset_refresh_channels(v)
                        all_channels[v] = ch
                        channels_modified = True
                        failures.append({"version": v, "type": "channels", "detail": f"No channels for {v}", "fixed": True})
                        fixed_count += 1
                        yield sse_event("log", f"  Channels: FIXED — found {len(ch)} channels")
                    except Exception as e:
                        failures.append({"version": v, "type": "channels", "detail": f"No channels for {v} — repair failed: {str(e)}", "fixed": False})
                        yield sse_event("log", f"  Channels: ERROR — {str(e)}")
                else:
                    yield sse_event("log", f"  Channels: OK ({len(version_channels)} channels)")

                # Check catalogs
                total_checked += 1
                catalogs_file = os.path.join("data", f"catalogs-{v}.json")
                catalogs_ok = False
                try:
                    if os.path.exists(catalogs_file):
                        with open(catalogs_file, 'r') as f:
                            cat_data = json.load(f)
                        cat_list = cat_data.get(v, cat_data) if isinstance(cat_data, dict) else cat_data
                        if isinstance(cat_list, list) and len(cat_list) > 0:
                            catalogs_ok = True
                    if not catalogs_ok:
                        raise ValueError("Empty or missing")
                    yield sse_event("log", f"  Catalogs: OK ({len(cat_list)} catalogs)")
                except Exception:
                    yield sse_event("log", f"  Catalogs: MISSING — redownloading...")
                    try:
                        cats = _reset_refresh_catalogs(v)
                        failures.append({"version": v, "type": "catalogs", "detail": f"catalogs-{v}.json missing/corrupt", "fixed": True})
                        fixed_count += 1
                        yield sse_event("log", f"  Catalogs: FIXED — found {len(cats)} catalogs")
                    except Exception as e:
                        failures.append({"version": v, "type": "catalogs", "detail": f"catalogs-{v}.json — repair failed: {str(e)}", "fixed": False})
                        yield sse_event("log", f"  Catalogs: ERROR — {str(e)}")

                # Check operators for each catalog
                for catalog_url in CATALOG_BASE_URLS:
                    catalog_index = catalog_url.split('/')[-1]
                    total_checked += 1
                    ops_file = os.path.join("data", f"operators-{catalog_index}-{v}.json")
                    try:
                        if not os.path.exists(ops_file):
                            raise ValueError("File not found")
                        with open(ops_file, 'r') as f:
                            ops_data = json.load(f)
                        ops_list = ops_data.get("operators", [])
                        if not ops_list:
                            raise ValueError("Empty operators list")
                        yield sse_event("log", f"  Operators ({catalog_index}): OK ({len(ops_list)} operators)")
                    except Exception:
                        yield sse_event("log", f"  Operators ({catalog_index}): MISSING — redownloading...")
                        try:
                            count = _reset_refresh_operators(catalog_url, v)
                            failures.append({"version": v, "type": "operators", "detail": f"{catalog_index} v{v} missing/corrupt", "fixed": True})
                            fixed_count += 1
                            yield sse_event("log", f"  Operators ({catalog_index}): FIXED — saved {count} operators")
                        except Exception as e:
                            failures.append({"version": v, "type": "operators", "detail": f"{catalog_index} v{v} — repair failed: {str(e)}", "fixed": False})
                            yield sse_event("log", f"  Operators ({catalog_index}): ERROR — {str(e)}")

                # Check dependencies for each catalog
                for catalog_url in CATALOG_BASE_URLS:
                    catalog_index = catalog_url.split('/')[-1]
                    total_checked += 1
                    deps_file = os.path.join("data", f"deps-{catalog_index}-{v}.json")
                    try:
                        if not os.path.exists(deps_file):
                            raise ValueError("File not found")
                        with open(deps_file, 'r') as f:
                            deps_data = json.load(f)
                        if not deps_data.get("dependencies") and not deps_data.get("gvk_providers"):
                            raise ValueError("Empty dependency data")
                        dep_count = len(deps_data.get("dependencies", {}))
                        gvk_count = len(deps_data.get("gvk_providers", {}))
                        yield sse_event("log", f"  Dependencies ({catalog_index}): OK ({dep_count} deps, {gvk_count} GVKs)")
                    except Exception:
                        yield sse_event("log", f"  Dependencies ({catalog_index}): MISSING — regenerating...")
                        try:
                            dep_count = _reset_refresh_dependencies(catalog_url, v)
                            failures.append({"version": v, "type": "dependencies", "detail": f"deps-{catalog_index}-{v}.json missing/corrupt", "fixed": True})
                            fixed_count += 1
                            yield sse_event("log", f"  Dependencies ({catalog_index}): FIXED — {dep_count} operators with deps")
                        except Exception as e:
                            failures.append({"version": v, "type": "dependencies", "detail": f"deps-{catalog_index}-{v}.json — repair failed: {str(e)}", "fixed": False})
                            yield sse_event("log", f"  Dependencies ({catalog_index}): ERROR — {str(e)}")

                # Check releases for each channel of this version
                for ch in version_channels:
                    total_checked += 1
                    if ch in all_releases and all_releases[ch]:
                        pass
                    else:
                        yield sse_event("log", f"  Releases ({ch}): MISSING — redownloading...")
                        try:
                            rels = _reset_refresh_releases(v, ch)
                            all_releases[ch] = rels
                            failures.append({"version": v, "type": "releases", "detail": f"No releases for {ch}", "fixed": True})
                            fixed_count += 1
                            yield sse_event("log", f"  Releases ({ch}): FIXED — found {len(rels)} releases")
                        except Exception as e:
                            failures.append({"version": v, "type": "releases", "detail": f"{ch} — repair failed: {str(e)}", "fixed": False})
                            yield sse_event("log", f"  Releases ({ch}): ERROR — {str(e)}")

                yield sse_event("log", "")

            # Save channels if any were repaired
            if channels_modified:
                _reset_save_channels(all_channels)

            # --- Summary ---
            unfixed = [f for f in failures if not f["fixed"]]
            if not failures:
                msg = f"All checks passed. Verified {total_checked} items across {len(filtered)} versions."
                yield sse_event("log", f"=== {msg} ===")
                yield sse_event("complete", json.dumps({"status": "success", "message": msg, "failures": [], "fixed_count": 0, "total_checked": total_checked}))
            elif not unfixed:
                msg = f"Check complete. Found and repaired {fixed_count} issue(s) across {len(filtered)} versions."
                yield sse_event("log", f"=== {msg} ===")
                yield sse_event("complete", json.dumps({"status": "warning", "message": msg, "failures": failures, "fixed_count": fixed_count, "total_checked": total_checked}))
            else:
                msg = f"Check complete. {len(unfixed)} issue(s) could not be repaired ({fixed_count} fixed). Review errors above."
                yield sse_event("log", f"=== {msg} ===")
                yield sse_event("complete", json.dumps({"status": "error", "message": msg, "failures": failures, "fixed_count": fixed_count, "total_checked": total_checked}))

        except Exception as e:
            current_app.logger.error(f"Check failed: {traceback.format_exc()}")
            yield sse_event("error", json.dumps({"status": "error", "message": f"Check failed: {str(e)}", "failures": failures}))
        finally:
            _check_in_progress = False

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@maintenance_bp.route("/reset", methods=["POST"])
def reset_all_data():
    """Delete all cached data and re-download everything from 4.13+ via SSE streaming."""
    global _reset_in_progress

    if _reset_in_progress:
        return jsonify({
            'status': 'error',
            'message': 'A reset is already in progress. Please wait for it to complete.'
        }), 409

    def generate():
        global _reset_in_progress
        _reset_in_progress = True

        try:
            # --- Delete all files in data/ ---
            yield sse_event("log", "Deleting all cached data files...")
            data_dir = "data"
            if os.path.exists(data_dir):
                deleted_count = 0
                for f in os.listdir(data_dir):
                    filepath = os.path.join(data_dir, f)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        deleted_count += 1
                yield sse_event("log", f"  Deleted {deleted_count} files.")
            else:
                os.makedirs(data_dir)
            yield sse_event("log", "All data files deleted.\n")

            # --- Step 1/5: Refresh versions ---
            yield sse_event("progress", json.dumps({"step": 1, "total": 5, "description": "Refreshing OCP versions"}))
            yield sse_event("log", "Step 1/5: Refreshing OCP versions...")
            try:
                versions = _reset_refresh_versions()
                yield sse_event("log", f"  Found {len(versions)} versions: {', '.join(versions)}")
            except Exception as e:
                yield sse_event("log", f"  ERROR: {str(e)}")
                yield sse_event("error", json.dumps({"status": "error", "message": f"Failed to refresh versions: {str(e)}"}))
                return

            # Filter to 4.13+
            filtered = []
            for v in versions:
                try:
                    parts = tuple(map(int, v.split('.')))
                    min_parts = tuple(map(int, RESET_MIN_VERSION.split('.')))
                    if parts >= min_parts:
                        filtered.append(v)
                except ValueError:
                    continue
            filtered.sort(key=lambda x: tuple(map(int, x.split('.'))))
            yield sse_event("log", f"  Processing {len(filtered)} versions (>= {RESET_MIN_VERSION}): {', '.join(filtered)}\n")

            # --- Step 2/5: Refresh channels ---
            yield sse_event("progress", json.dumps({"step": 2, "total": 5, "description": "Refreshing channels"}))
            yield sse_event("log", "Step 2/5: Refreshing channels for all versions...")
            all_channels = {}
            for v in filtered:
                yield sse_event("log", f"  Refreshing channels for {v}...")
                try:
                    ch = _reset_refresh_channels(v)
                    all_channels[v] = ch
                    yield sse_event("log", f"    Found {len(ch)} channels")
                except Exception as e:
                    all_channels[v] = []
                    yield sse_event("log", f"    WARNING: {str(e)}")
            _reset_save_channels(all_channels)
            yield sse_event("log", "  Channels saved.\n")

            # --- Step 3/5: Refresh catalogs ---
            yield sse_event("progress", json.dumps({"step": 3, "total": 5, "description": "Refreshing catalogs"}))
            yield sse_event("log", "Step 3/5: Refreshing catalogs for all versions...")
            for v in filtered:
                yield sse_event("log", f"  Refreshing catalogs for {v}...")
                try:
                    cats = _reset_refresh_catalogs(v)
                    yield sse_event("log", f"    Found {len(cats)} catalogs")
                except Exception as e:
                    yield sse_event("log", f"    WARNING: {str(e)}")
            yield sse_event("log", "  All catalogs refreshed.\n")

            # --- Step 4/5: Refresh releases ---
            yield sse_event("progress", json.dumps({"step": 4, "total": 5, "description": "Refreshing releases"}))
            yield sse_event("log", "Step 4/5: Refreshing channel releases...")
            for v in filtered:
                channels_for_v = all_channels.get(v, [])
                for ch in channels_for_v:
                    yield sse_event("log", f"  Refreshing releases for {ch} (version {v})...")
                    try:
                        rels = _reset_refresh_releases(v, ch)
                        yield sse_event("log", f"    Found {len(rels)} releases")
                    except Exception as e:
                        yield sse_event("log", f"    WARNING: {str(e)}")
            yield sse_event("log", "  All releases refreshed.\n")

            # --- Step 5/5: Refresh operators ---
            yield sse_event("progress", json.dumps({"step": 5, "total": 5, "description": "Refreshing operators"}))
            yield sse_event("log", "Step 5/5: Refreshing operators for all catalogs and versions...")
            total_ops = len(filtered) * len(CATALOG_BASE_URLS)
            current_op = 0
            for v in filtered:
                for catalog_url in CATALOG_BASE_URLS:
                    current_op += 1
                    catalog_name = catalog_url.split('/')[-1]
                    yield sse_event("log", f"  [{current_op}/{total_ops}] Refreshing operators: {catalog_name} v{v}...")
                    try:
                        count = _reset_refresh_operators(catalog_url, v)
                        deps_file = os.path.join("data", f"deps-{catalog_name}-{v}.json")
                        deps_ok = os.path.exists(deps_file)
                        yield sse_event("log", f"    Saved {count} operator entries" + (" + dependencies" if deps_ok else ""))
                    except Exception as e:
                        yield sse_event("log", f"    WARNING: Failed - {str(e)}")
            yield sse_event("log", "\nAll operators and dependencies refreshed.\n")

            # --- Done ---
            yield sse_event("complete", json.dumps({
                "status": "success",
                "message": f"Reset complete. Processed {len(filtered)} versions with all catalogs.",
                "versions_processed": filtered
            }))

        except Exception as e:
            current_app.logger.error(f"Reset failed: {traceback.format_exc()}")
            yield sse_event("error", json.dumps({
                "status": "error",
                "message": f"Reset failed: {str(e)}"
            }))
        finally:
            _reset_in_progress = False

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@maintenance_bp.route("/refresh/all", methods=["GET"])
def refresh_all_static_data():
    """Refresh all static data files."""
    try:
        do_refresh_versions()
        do_refresh_ocp_channels()
        do_refresh_ocp_releases(version=None, channel=None)
        do_refresh_ocp_operators(catalog=None, version=None)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error refreshing static data: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }), 500

    return jsonify({
        "status": "success",
        "message": "All static data refreshed",
        "timestamp": datetime.now().isoformat()
    })
