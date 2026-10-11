"""Deploy the backend to the hosted Supabase project in ../.env, then verify it end to end. Run it yourself:

    python tools/deploy_supabase.py

Steps (each must succeed before the next):
  1. db push            apply supabase/migrations (schemas, RLS, api functions, nightly stats job)
  2. config push        only the two settings in supabase-hosted/supabase/config.toml: Data API exposes only the
                        `api` schema, anonymous sign-ins on. Every other project setting is left unchanged.
  3. functions deploy   ingest + jev-proxy Edge Functions
  4. secrets            JEV_API_KEY for jev-proxy (read from ../.env, never printed)
  5. verify             tools/test_supabase_backend.py against the hosted project (throwaway players, cleaned up)
Needs `npx supabase login` once. Already linked by `python tools/supabase_cli.py link`.
"""
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "tools" / "supabase_cli.py")]
STEPS = [
    ("apply migrations", CLI + ["db", "push", "--yes"]),
    # supabase-hosted/supabase/config.toml declares only these two settings, so nothing else on the project changes.
    ("push project config (api schema only, anonymous sign-ins)", CLI + ["config", "push", "--workdir", "supabase-hosted", "--yes"]),
    ("deploy Edge Functions", CLI + ["functions", "deploy", "ingest", "jev-proxy", "--use-api"]),
    ("set the Jev secret", CLI + ["secrets-jev"]),
    ("verify end to end", [sys.executable, str(ROOT / "tools" / "test_supabase_backend.py")]),
]


def main():
    for name, cmd in STEPS:
        print(f"\n== {name}")
        if subprocess.run(cmd, cwd=ROOT).returncode != 0:
            print(f"stopped: '{name}' failed (output above). Nothing after it ran.")
            return 1
    print("\nBackend deployed and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
