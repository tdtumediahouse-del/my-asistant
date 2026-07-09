import os
import subprocess
from dotenv import dotenv_values

env = dotenv_values('.env')
for k, v in env.items():
    if v:
        print(f"Removing {k}...")
        subprocess.run(
            ["npx", "vercel", "env", "rm", k, "production", "--yes"],
            shell=True,
            capture_output=True
        )
        print(f"Adding {k}...")
        subprocess.run(
            ["npx", "vercel", "env", "add", k, "production"],
            input=v.encode("utf-8"),
            check=True,
            shell=True
        )
