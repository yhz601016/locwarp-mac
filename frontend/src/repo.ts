/**
 * Single source of truth for "where does this build live on GitHub".
 * The in-app update checker polls `https://api.github.com/repos/<REPO>/releases/latest`,
 * so publishing a new release (the macOS CI workflow does this on every `v*` tag)
 * is all it takes for existing installs to show an "update available" badge.
 */
export const GITHUB_REPO = 'yhz601016/locwarp-mac';
export const UPSTREAM_REPO = 'keezxc1223/locwarp';
