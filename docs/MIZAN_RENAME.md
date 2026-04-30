# Mizan module rename — test & deploy runbook

This branch (`feat/mizan-module-rename`) renames the Frappe **module** from
`POSAwesome` to `Mizan`. The bench app slug stays `posawesome` so asset
URLs (`/assets/posawesome/dist/...`), IndexedDB key prefixes, Python
package imports (`posawesome.X`), and external integrations keep
working unchanged.

> **Do NOT pull this branch into a production site without running the
> test plan below first.** The rename touches ~500 textual references
> plus a directory move; runtime regressions are the primary risk.

---

## What changed in this branch

| Surface | Before | After |
|---|---|---|
| On-disk module directory | `posawesome/posawesome/` | `posawesome/mizan/` |
| `posawesome/modules.txt` | `POSAwesome` | `Mizan` |
| Python imports | `from posawesome.posawesome.api…` | `from posawesome.mizan.api…` |
| `frappe.call({ method })` strings | `posawesome.posawesome.api.…` | `posawesome.mizan.api.…` |
| DocType / Page / Workspace JSON `"module"` | `POSAwesome` | `Mizan` |
| `pyproject.toml` description | "POS project that's simply awesome" | "Mizan — Point of Sale for ERPNext (Infoney)…" |
| `posawesome/hooks.py` `app_title` | already `Mizan` (set in earlier rebrand) | unchanged |
| Bench app slug, package name, asset URL | `posawesome` | **unchanged** |

Counts:
- 313 Python file references updated
- 166 frontend (`.ts` / `.vue` / `.js`) references updated
- 27 JSON files updated
- 1 directory rename
- 2 patches (`rename_module_to_mizan`, `rename_workspace_to_mizan`)

---

## Test plan — set up a fresh test bench

You'll spin up a bench dedicated to this rename so production
(`AL-KHANSA`) is never at risk.

### 1. Provision a clean bench

```bash
# On the same server (or a dev VM) — pick a fresh path
cd ~
bench init --frappe-branch version-15 mizan-test-bench
cd mizan-test-bench

# Get ERPNext
bench get-app --branch version-15 erpnext

# Pull the rename branch of THIS repo into the new bench
bench get-app --branch feat/mizan-module-rename https://github.com/Infoney/pos-remake.git
# `bench get-app` registers the app under the slug declared in
# `pyproject.toml` ("posawesome") — that slug intentionally stays the
# same after this rename. The bench app folder will be `posawesome/`,
# not `mizan/`.

# Create a test site
bench new-site mizan-test.localhost
bench --site mizan-test.localhost install-app erpnext
bench --site mizan-test.localhost install-app posawesome
```

If `install-app` succeeds, the rename is structurally sound on a fresh
DB — Frappe loaded `modules.txt` (`Mizan`), found the on-disk module
at `posawesome/mizan/`, and registered every DocType / Page / Workspace.

### 2. Smoke-test the POS shell

```bash
bench --site mizan-test.localhost set-config developer_mode 1
bench start
```

Open `http://mizan-test.localhost:8000/app/pos-awesome` (the workspace
URL slug is unchanged) and verify:

- [ ] Sidebar shows **Mizan** (not "POS Awesome").
- [ ] Workspace header reads **Mizan**, shortcut card reads **Mizan App**.
- [ ] Click "Mizan App" → POS launches, browser tab title reads **Mizan**.
- [ ] Items panel loads (proves `posawesome.mizan.api.items.get_items`
      method paths resolve from the frontend).
- [ ] Open About dialog (top-right menu → About). It should list
      `posawesome` as an installed app — that's the bench slug, NOT
      a regression. The `app_title` in `hooks.py` is "Mizan".
- [ ] DocType list (`/app/doctype`) → filter by Module = **Mizan**.
      You should see all the POS Awesome DocTypes (POS Profile,
      POS Coupon, POS Gift Card, POS Offer, etc.) listed under
      module "Mizan", not "POSAwesome".

### 3. Migrate-from-existing test (closest to production)

This is the test that actually matters — proves the patches run cleanly
on a DB that was previously installed under "POSAwesome".

```bash
# Step A: install the OLD branch first, simulating production state
bench --site mizan-test.localhost uninstall-app posawesome --force
cd apps/posawesome
git checkout pos-iteration-2   # the pre-rename branch
cd ../..
bench --site mizan-test.localhost install-app posawesome
# (Optional) seed it: create a POS Profile, log a sample invoice,
# add a gift card — anything that gets DocType records into the DB
# under module="POSAwesome".

# Step B: switch to the rename branch + migrate
cd apps/posawesome
git checkout feat/mizan-module-rename
cd ../..
bench --site mizan-test.localhost migrate
bench build --app posawesome --force
bench restart
```

Watch the migrate output. The two patches you should see run, in order:

1. `posawesome.patches.rename_module_to_mizan` — should print
   `Renamed Module Def 'POSAwesome' → 'Mizan'.` (or the manual fallback
   message).
2. `posawesome.patches.rename_workspace_to_mizan` — should print the
   delete + recreate message.

### 4. Post-migrate verification

After migrate finishes, verify the same checklist from step 2 plus:

- [ ] **Existing data still readable.** Open one of the seeded POS
      Profiles / gift cards. The form should load without
      `frappe.exceptions.DoesNotExistError` for module references.
- [ ] **Custom Field rebind.** `/app/custom-field` filtered by
      module = "Mizan" should show every `posa_*` custom field on POS
      Profile / Sales Invoice etc.
- [ ] **Background jobs still trigger.** Submit a test POS invoice —
      the scheduled tasks (`posawesome.mizan.api.…`) should fire and
      complete without `ImportError`. Check `Error Log` and the
      browser console.
- [ ] **No "POSAwesome" left.** In Frappe Desk → search "POSAwesome".
      Result should be empty (apart from any historical Error Log
      entries, which is fine — they're audit trail).

---

## Data migration plan for production (AL-KHANSA)

When you're satisfied with the test bench:

1. **Backup the production site** before anything else:
   ```bash
   bench --site al-khansa-prod backup --with-files
   ```

2. **Schedule a maintenance window** — patches run during `bench
   migrate`, which holds the request queue. Quote 5–10 minutes.

3. **Snapshot the production app folder** in case rollback is
   needed:
   ```bash
   cd apps/posawesome
   git rev-parse HEAD > /tmp/posawesome_pre_mizan_sha.txt
   ```

4. **Pull and migrate**:
   ```bash
   cd apps/posawesome
   git fetch pos-remake
   git checkout feat/mizan-module-rename     # or merge it into main first
   cd ../..
   bench --site al-khansa-prod migrate
   bench build --app posawesome --force
   bench restart
   ```

5. **Smoke-test on production** — same checklist as test bench step 4.

6. **If anything breaks**, rollback path:
   ```bash
   cd apps/posawesome
   git checkout $(cat /tmp/posawesome_pre_mizan_sha.txt)
   cd ../..
   # Restore the pre-migrate backup
   bench --site al-khansa-prod restore <path-to-backup-sql.gz> \
        --with-public-files <path> --with-private-files <path>
   bench build --app posawesome --force
   bench restart
   ```
   The rollback restores the database from the backup, so the
   "POSAwesome" Module Def + every DocType reference comes back
   together. The on-disk code reverts via the git checkout. Net effect:
   zero data loss, system back to pre-migrate state.

---

## Known leftovers (intentional, not regressions)

These still say `posawesome` after the rename — by design:

- `bench --app posawesome migrate` — the **bench app slug**, used in
  ALL bench commands. Renaming it would force a full uninstall /
  reinstall on production with manual data porting (Option C in the
  earlier discussion). Out of scope for this rename.
- `/assets/posawesome/dist/...` — the static asset URL prefix. Tied
  to the bench app slug.
- `posawesome/__init__.py`, `posawesome/hooks.py` — the Python package
  root, also tied to the bench slug.
- `pyproject.toml` `name = "posawesome"` — the bench slug declaration
  itself.
- `app_publisher = "Youssef Restom"` in `hooks.py` — historical
  attribution to the upstream open-source author. Change manually if
  you want; not breakage if left.

These DO NOT show up in any user-facing surface (cashier, admin Desk,
business reports, customer receipts). They only appear in DevOps
commands and browser DevTools Network tab.

---

## What to do if migrate fails on the test bench

Most likely failure mode: a missed reference somewhere. The grep
verification catches the common cases, but if migrate complains about
`module 'posawesome.posawesome' not found` or similar, search the repo
again:

```bash
cd apps/posawesome
grep -rn "posawesome\.posawesome" . --include="*.py" --include="*.ts" --include="*.vue" --include="*.js"
grep -rn '"module": "POSAwesome"' . --include="*.json"
```

Both should return zero matches. If they don't, the new file added a
reference that needs updating; rerun the bulk replace and commit a
follow-up.

If the `rename_module_to_mizan` patch errors out partway through, the
fallback path (`_repoint_module_references`) directly UPDATEs the
`tab*` tables. If even that fails, the rollback path in step 6 above
gets you back to a clean state.
