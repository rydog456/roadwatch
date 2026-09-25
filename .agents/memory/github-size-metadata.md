---
name: GitHub repository size metadata
description: Verify the actual Git tree before concluding a public repository has no source code.
---

GitHub's reported repository `size` can be zero while the default branch contains substantial source code. Do not treat `size: 0` as evidence of an empty repository.

**Why:** A public backend repository in this project reported zero size through the repository API but had a populated Git tree and working source files.

**How to apply:** Check branch refs and the recursive Git tree (or clone read-only) before telling the user that a repository is empty or asking them to upload its contents.