---
name: GitHub history publishing
description: Why a GitHub connector does not replace Git transport for preserving a local commit graph
---

For integrating unrelated Git histories, prefer an authenticated Git push of the locally reviewed merge commit over reconstructing a branch through the GitHub REST API. An authorized GitHub connection may support individual Git-object writes but not Git transport authentication; bulk object uploads can be rejected with HTTP 429 before a complete commit graph exists on the remote.

**Why:** A flattened API snapshot would publish the files but discard the original local ancestry, violating the history-preservation goal. Partial object uploads are not a reviewable branch.

**How to apply:** Keep the local integration branch and both remotes, do not force-push or create a partial snapshot, and request approved Git transport authorization before publishing the actual merge commit and opening a PR.