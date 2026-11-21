# 📜 FileChronicle

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Architecture: Local-First](https://img.shields.io/badge/architecture-local--first-green.svg)]()
[![Database: SQLite WAL](https://img.shields.io/badge/storage-SQLite%20WAL-orange.svg)](https://www.sqlite.org/wal.html)

> **Local-first universal file intelligence, differential snapshot engine, and revision recovery system.**

FileChronicle is a lightweight, high-performance file versioning and tracking utility that operates completely locally on your workstation. It captures point-in-time differential snapshots of your directories, computes unified line diffs, compresses content with zlib into a deduplicated SQLite blob store, and lets you inspect and restore any previous version instantly.

---

## ✨ Features

- **📸 Instant Differential Snapshots**: Captures directory states with file change tracking (added, modified, deleted) and SHA-256 integrity verification.
- **🗜️ Content-Addressable Blob Storage**: Files are compressed (zlib) and deduplicated using SHA-256 hashes inside an embedded SQLite database (`~/.filechronicle/chronicle.db`).
- **🔍 Visual Unified Diffing**: Generates colored, terminal-friendly unified diffs comparing any two snapshots or working directory modifications.
- **⏮️ Safe File Restoration**: Roll back any single file or directory to a specific snapshot with automatic backup protection (`.bak` fallback).
- **🚫 Smart Ignore Engine**: Supports project `.chronicleignore` files plus built-in exclusion rules for `.git`, `node_modules`, virtual environments, and caches.
- **⚡ Terminal Workstation**: Comprehensive CLI offering `init`, `snapshot`, `status`, `diff`, `history`, `restore`, `log`, `cat`, and `projects`.

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/OmReddyEnduri/FileChronicle.git
cd FileChronicle

# Install locally
pip install -e .
```

---

## 🛠️ CLI Quickstart

```bash
# Initialize tracking for current directory
chronicle init . --name "MyProject"

# Capture a snapshot with a message
chronicle snapshot -m "Initial commit"

# Check working directory changes
chronicle status

# View unified diff between snapshots
chronicle diff 1 2

# Inspect revision history of a specific file
chronicle history src/main.py

# Restore previous file version safely
chronicle restore src/main.py --snapshot 1

# Print file content from a historical snapshot
chronicle cat src/main.py --snapshot 1
```

---

## 🧪 Running Automated Tests

```bash
python -m unittest discover -v tests
```

21 automated unit tests cover hashing, binary detection, differ, SQLite deduplication, directory traversal, ignore resolution, unicode/emoji handling, and CLI command execution.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.  
Copyright (c) 2026 OmReddyEnduri
