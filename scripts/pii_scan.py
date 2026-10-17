"""Scan every git-tracked file for personal data and secrets. Python standard library only.

    python scripts/pii_scan.py                  # built-in patterns
    python scripts/pii_scan.py --terms FILE     # plus private words, one per line

Keep the --terms file OUTSIDE the repository: it holds the words you do not want published
(your user name, employer, project names), so committing it would publish them.
A term found on a line that starts with "Author:" or with a copyright notice is reported
as allowed. Exit code 1 when anything else is found.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}",
    "phone": r"(?<![\w.-])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w.-])"
             r"|\+\d{1,3}[\s-]?\d{5}[\s-]?\d{5}\b",
    "street address": r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
                      r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Parkway|Pkwy)\b",
    "windows path": r"(?<![A-Za-z])[A-Za-z]:(?:\\|/)+[A-Za-z0-9_ .-]+",
    "user home path": r"(?<![\w.])/(?:home|Users)/[A-Za-z0-9_.-]+",
    "aws key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "api token": r"\bsk-[A-Za-z0-9_-]{16,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "private key": r"-{5}BEGIN",
    "ip address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}
ALLOWED_IPS = {"127.0.0.1"}


def tracked_files(root):
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [root / p for p in out.decode("utf-8").split("\0") if p]


def scan(root, terms):
    rules = [(k, re.compile(v)) for k, v in PATTERNS.items()]
    rules += [("term '" + t + "'", re.compile(r"(?<![A-Za-z])" + re.escape(t) + r"(?![a-z])", re.I)) for t in terms]
    findings, allowed, n = [], [], 0
    for path in tracked_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: nothing to scan as text
        n += 1
        rel = path.relative_to(root).as_posix()
        for no, line in enumerate(text.splitlines(), 1):
            for kind, rx in rules:
                for m in rx.finditer(line):
                    if kind == "ip address" and m.group(0) in ALLOWED_IPS:
                        continue
                    row = f"{rel}:{no}: {kind}: {m.group(0)!r}"
                    author_line = line.lstrip("# ").startswith("Author:") or line.lstrip().startswith(("Copyright", "MIT License. Copyright"))
                    (allowed if kind.startswith("term") and author_line else findings).append(row)
    return n, findings, allowed


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--terms", help="file with private words, one per line (keep it outside the repo)")
    ap.add_argument("--root", default=".", help="repository root (default: current folder)")
    a = ap.parse_args()
    terms = []
    if a.terms:
        terms = [t.strip() for t in Path(a.terms).read_text(encoding="utf-8").splitlines() if t.strip() and not t.startswith("#")]
    n, findings, allowed = scan(Path(a.root).resolve(), terms)
    for f in findings:
        print("FINDING " + f)
    for f in allowed:
        print("allowed " + f)
    print(f"pii_scan: {n} tracked text files, {len(PATTERNS)} patterns + {len(terms)} private terms, "
          f"{len(findings)} findings, {len(allowed)} allowed author lines")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
