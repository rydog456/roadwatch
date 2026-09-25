---
name: GitHub history publishing
description: Why a GitHub connector does not replace Git transport for preserving a local commit graph
---

For integrating unrelated Git histories, prefer an authenticated Git push of the locally reviewed merge commit. If the terminal has no Git transport authorization but a GitHub API connection is authorized, exact history can still be preserved through the Git data API: binary blobs can be uploaded individually, while a tree request with inline UTF-8 content creates many text blobs at once; then commits with original metadata and parents reproduce the local hashes. Verify every resulting tree and commit hash before creating a remote ref.

**Why:** Bulk individual object uploads triggered HTTP 429, and a flattened API snapshot would discard the original ancestry. Inline tree content avoided the bulk-upload rate limit while retaining the exact two-parent history.

**How to apply:** Keep the local integration branch and both remotes. If using the API fallback, upload only non-UTF-8 blobs separately, create each original tree and commit in parent order, compare returned hashes, and create the branch ref only after the complete graph is present. Never force-push or create a partial snapshot.