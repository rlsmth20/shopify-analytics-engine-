"""One-shot rename: slelfly → skubase across all source files.

Runs from PowerShell. Uses Python's native file I/O so it bypasses the
WSL filesystem-cache bug that corrupted files when we used sed -i earlier.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# Folders we touch
INCLUDE_DIRS = ["frontend", "backend", "marketing", "docs"]

# Folders we skip
SKIP_DIRS = {".git", "node_modules", ".next", ".next-dev", "__pycache__", ".venv", "dist", "build"}

# Extensions we process
EXTS = {".tsx", ".ts", ".jsx", ".js", ".py", ".css", ".md", ".json", ".html", ".txt"}

# Replacements applied in order. Most specific first.
REPLACEMENTS = [
    ("slelfly.com", "skubase.io"),
    ("Slelfly", "Skubase"),
    ("slelfly", "skubase"),
    (">sf</span>", ">sb</span>"),  # brand mark
]


def should_process(path: str) -> bool:
    rel = os.path.relpath(path, ROOT)
    parts = rel.replace("\\", "/").split("/")
    if any(p in SKIP_DIRS for p in parts):
        return False
    ext = os.path.splitext(path)[1].lower()
    return ext in EXTS


def main():
    files_scanned = 0
    files_changed = 0
    total_replacements = 0

    for top in INCLUDE_DIRS:
        top_path = os.path.join(ROOT, top)
        if not os.path.isdir(top_path):
            continue
        for dirpath, dirnames, filenames in os.walk(top_path):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if not should_process(full):
                    continue
                files_scanned += 1
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    print(f"  skip (binary?): {os.path.relpath(full, ROOT)}")
                    continue

                new_content = content
                file_replacements = 0
                for old, new in REPLACEMENTS:
                    count = new_content.count(old)
                    if count > 0:
                        new_content = new_content.replace(old, new)
                        file_replacements += count

                if new_content != content:
                    with open(full, "w", encoding="utf-8", newline="\n") as f:
                        f.write(new_content)
                    files_changed += 1
                    total_replacements += file_replacements
                    print(f"  changed ({file_replacements}): {os.path.relpath(full, ROOT)}")

    print(f"\n=== Done: {files_changed}/{files_scanned} files changed, {total_replacements} replacements ===")


if __name__ == "__main__":
    main()