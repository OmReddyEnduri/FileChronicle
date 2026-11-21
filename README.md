# FileChronicle

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Storage](https://img.shields.io/badge/storage-SQLite%20WAL-success.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-local--first-orange.svg)]()

> Local-first file intelligence, differential snapshot engine, and revision recovery system.

FileChronicle is a zero-dependency, local-first differential snapshot engine designed to record, track, and restore file states across development workspaces. It combines SHA-256 content addressing, line-level unified diffs, and compressed SQLite blob storage.

---

## Key Features

- **Local-First & Offline**: All records are retained locally in SQLite (`~/.filechronicle/chronicle.db`).
- **Content-Addressable Blobs**: SHA-256 deduplication and zlib compression.
- **Differential Snapshots**: Line diffs (+/- additions and removals).
- **Safe Recovery**: Restore files with automatic backup (`.bak`) preservation.
- **Project Tracking**: Manage multiple independent workspaces from one CLI.
- **Zero External Dependencies**: Pure Python standard library.

---

## Architecture Diagram

```
+-------------------------------------------------------------+
|                     Working Workspace                       |
|         (src/, docs/, tests/, .chronicleignore)             |
+------------------------------+------------------------------+
                               |
                   [ chronicle snapshot ]
                               |
                               v
+-------------------------------------------------------------+
|                     FileChronicle Engine                    |
|   - Path Normalization & Ignore Pattern Evaluator           |
|   - 64KB Streaming SHA-256 Hasher & Binary Detection        |
|   - Line-by-Line Differ (difflib unified diff)              |
|   - zlib Compression & Blob Deduplication                   |
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|            SQLite Engine (~/.filechronicle/chronicle.db)    |
|   - projects       : tracked root directories               |
|   - snapshots      : metadata, tags, change counters        |
|   - file_revisions : rel_path, hashes, unified diff cache   |
|   - blobs          : content-addressable zlib payload       |
+-------------------------------------------------------------+
```

---

## Installation & Setup

FileChronicle runs on Python 3.8+:

```bash
git clone https://github.com/OmReddyEnduri/FileChronicle.git
cd FileChronicle
pip install -e .
```

Or run directly without installation:

```bash
python -m filechronicle.cli --help
```

---

## Command Reference

### 1. Initialize Tracking
Initialize tracking for the current directory or a specified folder:

```bash
chronicle init
chronicle init /path/to/project --name "MyService"
```

### 2. Take a Snapshot
Capture a point-in-time differential snapshot:

```bash
chronicle snapshot -m "Implemented authentication module"
```

### 3. Check Workspace Status
Inspect untracked, modified, or deleted files:

```bash
chronicle status
chronicle status --all
```

### 4. Inspect Differential Diffs
Show unified diff between two snapshots:

```bash
chronicle diff 1 2
chronicle diff snap-20261121-110000 snap-20261121-120000 --file src/app.py
```

### 5. File History
View all recorded changes and diff metrics for a file:

```bash
chronicle history src/app.py
```

### 6. Restore File Version
Safely roll back a file to an earlier snapshot:

```bash
# Safely restore (creates .bak if modified)
chronicle restore src/app.py 1

# Force overwrite without backup
chronicle restore src/app.py 1 --force

# Restore to alternative location
chronicle restore src/app.py 1 --output src/app_recovered.py
```

### 7. Snapshot Log
List historical snapshot tags, dates, and summaries:

```bash
chronicle log
chronicle projects
```

---

## Testing

Run the test suite:

```bash
python -m unittest discover tests -v
```

---

## License

MIT License (c) 2026 OmReddyEnduri.
