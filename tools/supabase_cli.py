"""Run the Supabase CLI with this project's settings from ../.env, without secrets on the command line or in output.

    python tools/supabase_cli.py link                 # link to SUPABASE_PROJECT_ID (uses DATABASE_PASSWORD)
    python tools/supabase_cli.py db push --dry-run    # any other supabase arguments pass straight through
    python tools/supabase_cli.py secrets-jev          # set the JEV_API_KEY Edge Function secret from ../.env

Needs `npx supabase login` once. Output is scrubbed of anything that looks like a key or token.
"""
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SECRET = re.compile(r"(sb_(publishable|secret)_|eyJ|sbp_|nvapi-|sk-)[A-Za-z0-9._\-]+")


def env():
    out = dict(os.environ)
    for line in (ROOT.parent / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if out.get("DATABASE_PASSWORD"):
        out.setdefault("SUPABASE_DB_PASSWORD", out["DATABASE_PASSWORD"])
    return out


def run(args, e, stdin=None):
    cmd = "npx --yes supabase@2.120.0 " + " ".join(args)
    p = subprocess.run(cmd, cwd=ROOT, env=e, shell=True, input=stdin, capture_output=True, text=True)
    print(SECRET.sub(lambda m: m.group(1) + "<redacted>", (p.stdout or "") + (p.stderr or "")))
    return p.returncode


def main():
    e = env()
    args = sys.argv[1:]
    if args[:1] == ["link"]:
        return run(["link", "--project-ref", e["SUPABASE_PROJECT_ID"]], e)
    if args[:1] == ["secrets-jev"]:
        tmp = ROOT / "supabase" / ".temp-secrets.env"
        try:
            tmp.write_text(f"JEV_API_KEY={e['JEV_API_KEY']}\n", encoding="utf-8")
            return run(["secrets", "set", "--env-file", str(tmp), "--project-ref", e["SUPABASE_PROJECT_ID"]], e)
        finally:
            tmp.unlink(missing_ok=True)
    return run(args, e)


if __name__ == "__main__":
    sys.exit(main())
