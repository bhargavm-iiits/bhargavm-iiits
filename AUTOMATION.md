# Automatic project organization

[Run or inspect the workflow](https://github.com/bhargavm-iiits/bhargavm-iiits/actions/workflows/update-profile.yml).

## What happens automatically

- GitHub Actions checks the public repository inventory every hour, at minute 17.
- New projects are classified from their existing topics, description, README, project structure, and dependency manifests.
- The category topic is added while preserving existing topics. It makes the new project appear in the matching repository filter.
- The public profile directory and category counts are regenerated. A commit is created only when the saved directory data changes.
- The text contribution total at the top is refreshed from GitHub. The checked time is shown, and automation-only contribution changes are ignored to avoid an endless commit loop.
- Existing curated classifications and descriptions are retained through `profile.json` overrides.
- Private repositories are never listed or published. The profile repository itself is excluded.
- Code from other repositories is never executed. Only bounded text files are inspected.

GitHub schedules can be delayed and are not instant repository-creation notifications. Use **Run workflow** for an immediate check. GitHub may disable scheduled workflows in a public repository after a period of inactivity; the Actions page shows the state and can re-enable them.

## GitHub credential

The workflow reads the encrypted repository secret **PROJECTS_TOKEN**. The built-in `GITHUB_TOKEN` can publish this profile, but cannot edit topics in other repositories.

For a dedicated fine-grained personal access token:

1. Select resource owner `bhargavm-iiits` and **All repositories**, so repositories created later are included.
2. Allow repository **Administration: Read and write** for the GitHub topic-update endpoint. Allow **Contents: Read** for manifest and README inspection. Metadata read access is included automatically.
3. Choose an expiry you can maintain, and store the value in this repository's Actions secret named `PROJECTS_TOKEN`.
4. Run the workflow and check the summary. Rotate the secret before the token expires.

GitHub's topic endpoint requires Administration write permission. Protect this credential: that permission is broader than just changing topics. Keep the secret in GitHub Actions, never in a source file, log, issue, or chat.

The workflow uses the repository-scoped `GITHUB_TOKEN` for its own commits, and `PROJECTS_TOKEN` only for the public-repository discovery and topic-update script. The `actions/checkout` dependency is pinned to a full commit SHA. Privileged jobs run only on the default branch, scheduled events, and manual dispatch; there is no pull-request event that exposes the secret.

## Adjusting a category

Automatic classification uses deterministic rules, not an LLM service. An ambiguous project is placed in **Other Projects** instead of receiving an unsupported technology claim.

To choose a category explicitly, add an entry to `profile.json` under `overrides`, following the existing examples. Available category IDs are `vr-xr`, `ar`, `unity`, `ml`, `genai`, `fullstack`, `portfolio`, and `other`. A push that changes this configuration reruns the workflow.

The renderer updates only the block between `PROJECT-DIRECTORY:START` and `PROJECT-DIRECTORY:END`; your header and footer outside it are preserved.

## Local verification

```text
python -m unittest discover -s tests -v
python scripts/sync_projects.py --check
python scripts/render_profile.py
```

`--check` does not change files or repository topics. For API rate limits, an existing `GH_TOKEN` or `GITHUB_TOKEN` can authenticate read-only checks. Updating topics requires `PROJECTS_TOKEN` belonging to the configured account owner.

## Calendar and commit identity

The top of the profile contains an ordinary text heading with GitHub's contribution total and its checked time. It is updated by the hourly workflow when new non-automation activity is available. It is not a screenshot or an embedded image. The native interactive contribution graph remains in GitHub's own fixed section; the heading includes a link to it. GitHub calculates that graph and may take time to reflect new commits.

Profile changes and automatic directory commits use `bhargav.m23@iiits.in`. The five initial enhancement commits were assigned the requested author and committer dates: two on October 24, 2026, and three on October 25, 2026, using the Asia/Kolkata UTC+05:30 offset.
