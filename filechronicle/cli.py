"""Command-Line Interface for FileChronicle."""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, List

from . import __version__
from .config import get_db_path
from .engine import ChronicleEngine
from .formatter import (
    colorize,
    format_diff,
    format_size,
    render_table,
    BOLD,
    CYAN,
    GREEN,
    RED,
    YELLOW,
    MAGENTA,
    GRAY,
)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for chronicle CLI."""
    parser = argparse.ArgumentParser(
        prog="chronicle",
        description="Local-first file intelligence, differential snapshots & version history.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version", action="version", version=f"FileChronicle {__version__}"
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        help="Custom path to chronicle SQLite database (default: ~/.filechronicle/chronicle.db)",
    )
    parser.add_argument(
        "--no-color",
        dest="no_color",
        action="store_true",
        help="Disable ANSI color output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: init
    cmd_init = subparsers.add_parser(
        "init", help="Initialize tracking for a directory"
    )
    cmd_init.add_argument(
        "path", nargs="?", default=".", help="Directory to track (default: current directory)"
    )
    cmd_init.add_argument(
        "--name", help="Custom alias/name for the project"
    )

    # Command: snapshot
    cmd_snap = subparsers.add_parser(
        "snapshot", help="Capture full differential snapshot"
    )
    cmd_snap.add_argument(
        "-m", "--message", default="", help="Snapshot message / description"
    )
    cmd_snap.add_argument(
        "-t", "--tag", default=None, help="Custom tag for the snapshot"
    )
    cmd_snap.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )

    # Command: status
    cmd_status = subparsers.add_parser(
        "status", help="Show modified, untracked, and deleted files since last snapshot"
    )
    cmd_status.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )
    cmd_status.add_argument(
        "-a", "--all", action="store_true", help="Include clean (unchanged) files"
    )

    # Command: diff
    cmd_diff = subparsers.add_parser(
        "diff", help="Show unified diff of changed files between two snapshots"
    )
    cmd_diff.add_argument(
        "snap_id_1", help="First snapshot ID or tag"
    )
    cmd_diff.add_argument(
        "snap_id_2", help="Second snapshot ID or tag"
    )
    cmd_diff.add_argument(
        "-f", "--file", help="Filter diff to a specific file path"
    )
    cmd_diff.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )

    # Command: history
    cmd_hist = subparsers.add_parser(
        "history", help="Show all revisions and change summaries for a file"
    )
    cmd_hist.add_argument(
        "filepath", help="Relative path of file to inspect"
    )
    cmd_hist.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )

    # Command: restore
    cmd_restore = subparsers.add_parser(
        "restore", help="Restore previous file version safely"
    )
    cmd_restore.add_argument(
        "filepath", help="Relative path of file to restore"
    )
    cmd_restore.add_argument(
        "snap_id", help="Snapshot ID or tag to restore from"
    )
    cmd_restore.add_argument(
        "-o", "--output", help="Destination path for restored file (default: original path)"
    )
    cmd_restore.add_argument(
        "-f", "--force", action="store_true", help="Force overwrite without creating .bak backup"
    )
    cmd_restore.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )

    # Command: log / list
    cmd_log = subparsers.add_parser(
        "log", help="List snapshot history for project"
    )
    cmd_log.add_argument(
        "-n", "--limit", type=int, default=20, help="Maximum snapshots to display (default: 20)"
    )
    cmd_log.add_argument(
        "-p", "--path", default=".", help="Target project path (default: current directory)"
    )

    # Command: cat
    cmd_cat = subparsers.add_parser(
        "cat", help="Print file content from a specific snapshot to stdout"
    )
    cmd_cat.add_argument("filepath", help="Relative path of file")
    cmd_cat.add_argument("snap_id", help="Snapshot ID or tag")
    cmd_cat.add_argument("-p", "--path", default=".", help="Target project path")

    # Command: projects
    cmd_proj = subparsers.add_parser(
        "projects", help="List all tracked project directories"
    )

    return parser


def handle_init(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    target = Path(args.path).resolve()
    project, is_new = engine.init_project(str(target), name=args.name)
    if is_new:
        print(colorize(f"✓ Initialized FileChronicle tracking in {target}", GREEN))
        print(f"  Project: {colorize(project.name, BOLD)}")
        print(f"  Database: {engine.db_path}")
        print("  Run 'chronicle snapshot' to take your first baseline snapshot.")
    else:
        print(colorize(f"• Directory is already tracked as project '{project.name}'", YELLOW))
        print(f"  Root: {project.root_path}")
        print(f"  Database: {engine.db_path}")
    return 0


def handle_snapshot(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        project = engine.get_project(args.path)
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1

    snap, summary = engine.create_snapshot(
        project=project,
        message=args.message,
        tag=args.tag,
    )

    added_cnt = summary["files_added"]
    mod_cnt = summary["files_modified"]
    del_cnt = summary["files_deleted"]

    print(colorize(f"✓ Snapshot captured successfully!", GREEN))
    print(f"  Snapshot ID  : {colorize(str(snap.id), BOLD + CYAN)} ({snap.snapshot_tag})")
    print(f"  Message      : {snap.message}")
    print(f"  Timestamp    : {snap.created_at}")
    print(f"  Total Files  : {summary['total_files']} ({format_size(summary['total_bytes'])})")
    print(
        f"  Differential : {colorize(f'+{added_cnt} added', GREEN)}, "
        f"{colorize(f'~{mod_cnt} modified', YELLOW)}, "
        f"{colorize(f'-{del_cnt} deleted', RED)}"
    )
    return 0


def handle_status(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        project = engine.get_project(args.path)
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1

    statuses = engine.status(project)
    if not args.all:
        statuses = [s for s in statuses if s.status != "clean"]

    if not statuses:
        print(colorize(f"Working tree clean. No changes detected since last snapshot in '{project.name}'.", GREEN))
        return 0

    print(f"Status for project '{colorize(project.name, BOLD)}' ({project.root_path}):\n")

    headers = ["Status", "File Path", "Size", "Hash (short)"]
    rows = []
    for s in statuses:
        if s.status == "untracked":
            status_str = colorize("+ untracked", GREEN)
            sha_disp = s.sha256[:10] if s.sha256 else "-"
            size_disp = format_size(s.file_size)
        elif s.status == "modified":
            status_str = colorize("~ modified", YELLOW)
            sha_disp = s.sha256[:10] if s.sha256 else "-"
            size_disp = format_size(s.file_size)
        elif s.status == "deleted":
            status_str = colorize("- deleted", RED)
            sha_disp = s.old_sha256[:10] if s.old_sha256 else "-"
            size_disp = "-"
        else:
            status_str = colorize("• clean", GRAY)
            sha_disp = s.sha256[:10] if s.sha256 else "-"
            size_disp = format_size(s.file_size)

        rows.append([status_str, s.rel_path, size_disp, sha_disp])

    print(render_table(headers, rows, alignments=["L", "L", "R", "L"]))
    return 0


def handle_diff(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        diff_results = engine.diff_snapshots(
            snap_id_1=args.snap_id_1,
            snap_id_2=args.snap_id_2,
            target_path=args.path,
            file_filter=args.file,
        )
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1

    if not diff_results:
        print(colorize(f"No changes detected between snapshot {args.snap_id_1} and {args.snap_id_2}.", GREEN))
        return 0

    print(colorize(f"--- Differential comparison: Snap {args.snap_id_1} -> Snap {args.snap_id_2} ---", BOLD))
    for res in diff_results:
        print("\n" + colorize(f"=== {res.rel_path} ({res.change_type}) ===", BOLD + CYAN))
        if res.lines_added > 0 or res.lines_deleted > 0:
            print(f"Lines: {colorize(f'+{res.lines_added}', GREEN)} {colorize(f'-{res.lines_deleted}', RED)}")
        print(format_diff(res.diff_text))

    return 0


def handle_history(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        records = engine.file_history(args.filepath, target_path=args.path)
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1

    if not records:
        print(colorize(f"No snapshot history found for file '{args.filepath}'.", YELLOW))
        return 0

    print(f"Revision history for '{colorize(args.filepath, BOLD)}':\n")
    headers = ["Snap ID", "Tag", "Timestamp", "Change", "Lines (+/-)", "Size", "Message"]
    rows = []

    for snap, rev in records:
        if rev.change_type == "added":
            c_type = colorize("+ added", GREEN)
        elif rev.change_type == "modified":
            c_type = colorize("~ modified", YELLOW)
        elif rev.change_type == "deleted":
            c_type = colorize("- deleted", RED)
        else:
            c_type = colorize("• unchanged", GRAY)

        lines_str = f"+{rev.lines_added}/-{rev.lines_deleted}" if (rev.lines_added or rev.lines_deleted) else "-"
        size_str = format_size(rev.file_size) if rev.file_size > 0 else "-"
        short_msg = snap.message[:30] + "..." if len(snap.message) > 30 else snap.message

        rows.append([
            str(snap.id),
            snap.snapshot_tag,
            snap.created_at[:19].replace("T", " "),
            c_type,
            lines_str,
            size_str,
            short_msg,
        ])

    print(render_table(headers, rows, alignments=["R", "L", "L", "L", "R", "R", "L"]))
    return 0


def handle_restore(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        restored_path = engine.restore_file(
            rel_path=args.filepath,
            snapshot_id=args.snap_id,
            target_path=args.path,
            output_path=args.output,
            force=args.force,
            backup=not args.force,
        )
        print(colorize(f"✓ Restored '{args.filepath}' from snapshot {args.snap_id}", GREEN))
        print(f"  Target location: {restored_path}")
        if not args.force and restored_path.with_suffix(restored_path.suffix + ".bak").exists():
            print(colorize(f"  Previous version backed up to: {restored_path}.bak", GRAY))
        return 0
    except ValueError as e:
        print(colorize(f"Restore failed: {e}", RED), file=sys.stderr)
        return 1


def handle_log(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        project = engine.get_project(args.path)
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1

    snapshots = engine.db.list_snapshots(project.id, limit=args.limit)
    if not snapshots:
        print(colorize(f"No snapshots recorded yet for project '{project.name}'.", YELLOW))
        return 0

    print(f"Snapshots for '{colorize(project.name, BOLD)}' (latest {len(snapshots)}):\n")
    headers = ["ID", "Tag", "Timestamp", "Files", "Size", "Changes (+/~/-)", "Message"]
    rows = []

    for s in snapshots:
        diff_summary = f"+{s.files_added}/~{s.files_modified}/-{s.files_deleted}"
        rows.append([
            str(s.id),
            s.snapshot_tag,
            s.created_at[:19].replace("T", " "),
            str(s.total_files),
            format_size(s.total_bytes),
            diff_summary,
            s.message,
        ])

    print(render_table(headers, rows, alignments=["R", "L", "L", "R", "R", "R", "L"]))
    return 0


def handle_cat(engine: ChronicleEngine, args: argparse.Namespace) -> int:
    try:
        content = engine.get_file_content(args.filepath, args.snap_id, target_path=args.path)
        sys.stdout.buffer.write(content)
        return 0
    except ValueError as e:
        print(colorize(f"Error: {e}", RED), file=sys.stderr)
        return 1


def handle_projects(engine: ChronicleEngine) -> int:
    projects = engine.db.list_projects()
    if not projects:
        print(colorize("No projects currently tracked by FileChronicle.", YELLOW))
        return 0

    print(colorize("Tracked FileChronicle Projects:\n", BOLD))
    headers = ["ID", "Project Name", "Root Directory", "Registered"]
    rows = []
    for p in projects:
        rows.append([
            str(p.id),
            p.name,
            p.root_path,
            p.created_at[:19].replace("T", " "),
        ])
    print(render_table(headers, rows, alignments=["R", "L", "L", "L"]))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.no_color:
        os.environ["NO_COLOR"] = "1"
        from . import formatter
        formatter.USE_COLOR = False

    if not args.command:
        parser.print_help()
        return 0

    db_path = Path(args.db_path).resolve() if args.db_path else None
    engine = ChronicleEngine(db_path=db_path)

    if args.command == "init":
        return handle_init(engine, args)
    elif args.command == "snapshot":
        return handle_snapshot(engine, args)
    elif args.command == "status":
        return handle_status(engine, args)
    elif args.command == "diff":
        return handle_diff(engine, args)
    elif args.command == "history":
        return handle_history(engine, args)
    elif args.command == "restore":
        return handle_restore(engine, args)
    elif args.command == "log":
        return handle_log(engine, args)
    elif args.command == "cat":
        return handle_cat(engine, args)
    elif args.command == "projects":
        return handle_projects(engine)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
