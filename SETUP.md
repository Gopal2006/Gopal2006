# Profile README setup and verification

This bundle contains the profile README and a small GitHub Actions updater. The updater uses Python's standard library; no `pip install` step is required.

## Files

- `README.md` — the profile content.
- `assets/terminal-banner.svg` — custom terminal-inspired header graphic.
- `.github/workflows/update-profile.yml` — scheduled and manual workflow.
- `scripts/update_profile.py` — fetches and formats public GitHub data.
- `scripts/test_update_profile.py` — offline unit tests for key formatting behavior.

## Install in the profile repository

The profile repository must be named exactly `Gopal2006` and be public for its root `README.md` to render on `https://github.com/Gopal2006`.

Copy the bundle's files into the root of `Gopal2006/Gopal2006`, preserving the paths exactly. Commit and push to `main`.

The workflow has three triggers:

- first/configuration pushes to `main` that touch the README, updater, or workflow;
- a daily schedule at 02:23 UTC;
- a manual run via **GitHub → Actions → Update profile data → Run workflow**.

`GITHUB_TOKEN` is supplied automatically by Actions. The workflow grants it `contents: write` solely so it can commit generated README updates. No personal access token, manually configured secret, or third-party API key is required.

## What updates automatically

- recent **public** GitHub activity from GitHub's user-events API;
- recent publicly visible pull requests opened by `Gopal2006`, with open/closed/merged status;
- counts for public repositories, followers, stars on repositories owned by this account, and the account creation year;
- the “Last data update” timestamp.

GitHub's public events endpoint has a limited recent-history window (currently up to 30 days). Private activity is not shown. If there is no recent public event or no public PR yet, the README says so instead of inventing content.

The timestamp changes only when one of the generated data sections changes. Therefore the scheduled workflow does not commit a new timestamp every day and does not generate artificial daily activity.

The two GitHub Readme Stats images are optional third-party image services. They refresh independently and may occasionally be unavailable; the locally generated stats and activity do not depend on them.

## Verify locally

From the bundle root, run:

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m py_compile scripts/update_profile.py scripts/test_update_profile.py
```

To manually refresh against GitHub, optionally set a token for higher API rate limits and run:

```bash
export GITHUB_TOKEN="YOUR_TOKEN_IF_NEEDED"
python scripts/update_profile.py
```

Do not paste tokens into the README or commit them. The token is optional for local use; GitHub Actions supplies its own token automatically.

## Verify after publishing

1. Open `https://github.com/Gopal2006/Gopal2006` and confirm the banner renders and all links work.
2. Open the **Actions** tab and inspect the `Update profile data` workflow run. The first successful run replaces the initial generated-section placeholders.
3. Open the README and verify the stats and activity blocks. If a third-party stats image fails, the rest of the README should remain readable.
4. Check that the workflow creates a commit only when the generated public data changes.

## Accuracy notes

- The skill section deliberately distinguishes “comfortable” from “currently learning.”
- Neon Cinematics is described as deployed, with media/3D performance optimization as the current focus.
- VoxNav is described as a locally tested, not-yet-deployed prototype.
- No usage counts, adoption figures, merged PR counts, or unverified technology proficiency claims are included.
