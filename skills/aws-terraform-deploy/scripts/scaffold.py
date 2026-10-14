#!/usr/bin/env python3
"""Create a Terraform project skeleton for AWS from this skill's template.

Usage:
  python scaffold.py <target-dir> --project myapp --region ap-south-1 \
      [--envs dev,prod] [--state-bucket myapp-tfstate-123456789012] [--account-id 123456789012]

Standard library only. Refuses to overwrite existing files unless --force is given.
"""
import argparse
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template"
TEXT_SUFFIXES = {".tf", ".hcl", ".md", ".yml", ".yaml", ".sh", ".ps1", ".tfvars", ""}


def render(text, subs):
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--project", required=True, help="short lowercase name, letters/digits/hyphens")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--envs", default="dev,prod", help="comma list from: dev, staging, prod")
    ap.add_argument("--state-bucket", help="S3 bucket for Terraform state (must be globally unique)")
    ap.add_argument("--account-id", help="12-digit AWS account ID to lock the provider to")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", a.project):
        sys.exit("--project must be 2-31 chars: lowercase letters, digits, hyphens, starting with a letter.")
    if a.account_id and not re.fullmatch(r"\d{12}", a.account_id):
        sys.exit("--account-id must be exactly 12 digits.")
    envs = [e.strip() for e in a.envs.split(",") if e.strip()]
    bad = [e for e in envs if e not in ("dev", "staging", "prod")]
    if bad:
        sys.exit(f"Unknown environment(s): {', '.join(bad)}. Use dev, staging, prod.")

    bucket = a.state_bucket or f"{a.project}-tfstate-CHANGE-ME"
    subs = {"__PROJECT__": a.project, "__REGION__": a.region}
    target = Path(a.target)
    written, skipped = [], []

    def write(rel, content, executable=False):
        dest = target / rel
        if dest.exists() and not a.force:
            skipped.append(str(rel))
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8", newline="\n")
        if executable:
            dest.chmod(0o755)
        written.append(str(rel))

    for src in sorted(TEMPLATE.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE)
        if src.suffix in TEXT_SUFFIXES or src.name.startswith("."):
            write(rel, render(src.read_text(encoding="utf-8"), subs), executable=src.suffix == ".sh")

    acct = f'["{a.account_id}"]' if a.account_id else "[]  # TODO: add your AWS account ID to enable the safety check"
    for env in envs:
        write(Path("envs") / f"{env}.tfvars",
              f'environment         = "{env}"\naws_region          = "{a.region}"\nallowed_account_ids = {acct}\n')
        write(Path("envs") / f"{env}.backend.hcl",
              f'bucket = "{bucket}"\nregion = "{a.region}"\n')

    print(f"Created Terraform skeleton in {target.resolve()}")
    for w in written:
        print("  +", w)
    for s in skipped:
        print("  = kept existing", s)
    if not a.state_bucket:
        print("\nNote: set the real state bucket name in envs/*.backend.hcl (see README, bootstrap step).")


if __name__ == "__main__":
    main()
