---
description: Pick the next unchecked backlog item and work only on it
---

1. Read only `docs/BACKLOG.md`. Take the first unchecked item (skip E-items and anything marked ANLAŞILMADI; ask me instead). If I gave an id in $ARGUMENTS, use that one.
2. Locate the relevant code with grep/glob. Do not read whole files.
3. If the item is large (D-phase or touches many files), give a plan of at most 8 lines and wait for my OK. Otherwise implement directly.
4. Verify it works (run / test / show evidence).
5. Mark the item `[x]` with a 1-2 line note in `docs/BACKLOG.md`.
6. Reply in at most 5 lines: what changed, files, how verified, what is next. Then suggest `/clear`.
