# Claude Code Configuration for POSAwesome

## About This Project

POSAwesome is a Frappe application - a Point of Sale (POS) system built on the Frappe Framework. This is a full-stack web application with Python backend and Vue.js frontend components.

**Enhanced Camera Scanner**: Features advanced OpenCV-based image processing for superior barcode and QR code scanning with real-time image enhancement.

## Brand identity

**Product name (user-facing): "Mizan"** — Arabic for "scales / balance / the just measure". Branded as **"Infoney Mizan"** in formal copy (proposals, invoices, documentation), **"Mizan"** alone on the navbar and other tight UI surfaces.

**The Frappe app slug stays `posawesome`** — the Python module, bench app name, DocType module references (`POSAwesome`), database namespace, and the upstream project identity all stay as-is. Renaming those would break installs, migrations, custom field references, every external integration, and the upstream attribution. The brand swap is purely a user-facing label change.

**What carries the Mizan brand** (changeable copy):
- Navbar title fallback (`NavbarAppBar.vue` — `customBrandName` from POS Profile still wins)
- Frappe page titles (`page/pos/pos.js`, `page/posapp/posapp.js`, plus the `.json` metadata)
- Print views and customer-visible receipt strings (gift card remarks)
- AppBar default `company` field

**What stays "POS Awesome"** (project-of-origin identity):
- README.md, CHANGELOG.md, package.json — fork attribution to the open-source project
- Python module `posawesome/`, Frappe module `POSAwesome`, all DocType slugs (`pos_awesome_print_format_rule`, etc.)
- Internal log_error titles, debug console breadcrumbs, dev-facing docstrings

When adding new user-visible copy, default to **Mizan**. When the string is internal/technical (logs, telemetry, file paths, doctype names), leave the historical naming alone — it's the trace back to the upstream source the user can use to apply security patches.

## Build Commands

### Main Build Commands
```bash
# Build frontend assets for production
bench build --app posawesome


# Force rebuild (cleans cache first)
bench build --app posawesome --force

# Build all apps in the bench
bench build
```

### Development Server
```bash
# Start development server
bench start

# Start with specific port
bench start --port 8000
```

## Project Structure

```
posawesome/
├── frontend/                 # Vue.js frontend
│   ├── src/
│   │   ├── posapp/
│   │   │   ├── components/   # Vue components
│   │   │   └── pages/        # Vue pages
│   │   └── main.js           # Frontend entry point
│   └── package.json          # Frontend dependencies
├── posawesome/               # Python backend
│   ├── public/               # Static assets
│   ├── posawesome/           # Main module
│   │   ├── doctype/         # DocType definitions
│   │   ├── api/             # API endpoints
│   │   └── hooks.py         # App hooks
├── CLAUDE.md                 # This file
└── pyproject.toml           # Python dependencies
```

## Common Development Commands

### Site Management
```bash
# Create new site
bench new-site mysite.local

# Install app on site
bench --site mysite.local install-app posawesome

# Migrate database
bench --site mysite.local migrate

# Access site console
bench --site mysite.local console

# Backup site
bench --site mysite.local backup
```

### Database Operations
```bash
# Run migrations
bench migrate

# Reload specific doctype
bench --site mysite.local console
>>> frappe.reload_doc('posawesome', 'doctype', 'pos_invoice')

# Clear cache
bench --site mysite.local clear-cache
```

### Code Quality & Testing
```bash
# Run tests
bench --site mysite.local run-tests --app posawesome

# Run specific module tests
bench --site mysite.local run-tests --module posawesome.tests.test_pos

# Check Python syntax issues
cd ~/frappe-bench/sites
../env/bin/python ../apps/frappe/frappe/utils/bench_helper.py
```

## Frontend Development

### Vue.js Components
- Built with Vue 3 and Vuetify
- Components located in `frontend/src/posapp/components/`
- Use composition API where possible
- Follow Frappe UI patterns and conventions

### Asset Building
- Uses Vite as build tool
- Automatic compilation on `bench build --app posawesome`
- Watch mode available with `--dev` flag

### Styling
- Uses Vuetify components and Material Design
- Custom SCSS in component `<style>` blocks
- RTL support implemented for Arabic/Hebrew

## Backend Development

### Frappe Framework Patterns
```python
# Get document
doc = frappe.get_doc("POS Invoice", invoice_name)

# Create new document
new_doc = frappe.new_doc("POS Invoice")
new_doc.update(data)
new_doc.insert()

# Database queries
invoices = frappe.get_list("POS Invoice", 
    filters={"status": "Draft"}, 
    fields=["name", "total"]
)

# Utilities
from frappe.utils import cint, flt, getdate, today
```

### API Development
```python
# In posawesome/api/pos.py
@frappe.whitelist()
def get_pos_data():
    return frappe.get_list("POS Invoice", limit=10)
```

### Hooks Configuration
Located in `posawesome/hooks.py`:
```python
# Document events
doc_events = {
    "POS Invoice": {
        "on_submit": "posawesome.api.pos.on_pos_invoice_submit"
    }
}
```

## Git Workflow

### Working with Forks
```bash
# Add your fork as remote
cd apps/posawesome
git remote add origin https://github.com/[username]/posawesome

# Create feature branch
git checkout -b feature/my-new-feature

# Stage and commit changes
git add .
git commit -m "Add new POS feature"

# Push to your fork
git push origin feature/my-new-feature
```

### Staying Updated
```bash
# Add upstream remote (original repo)
git remote add upstream https://github.com/yrestom/POS-Awesome

# Pull latest changes
git pull upstream develop

# Rebase your branch
git rebase upstream/develop
```

## Debugging Tips

### Common Issues
1. **Build Failures**: Clear cache with `bench clear-cache`
2. **Frontend Issues**: Check browser console and network tab
3. **Python Errors**: Check `bench start` output and error logs
4. **Database Issues**: Run `bench migrate` and check DocType definitions

### Development Tools
```bash
# Access Python console
bench --site mysite.local console

# Enable developer mode
bench --site mysite.local set-config developer_mode 1

# Show configuration
bench show-config

# List installed apps
bench list-apps --format json
```

## Key Dependencies

### Frontend
- Vue 3 - Frontend framework
- Vuetify - UI component library
- Vite - Build tool and dev server

### Backend  
- Frappe Framework - Full-stack web framework
- Python 3.8+ - Programming language
- MariaDB/MySQL - Database
- Redis - Caching and queuing

## Production Deployment

```bash
# Production build
bench build --app posawesome

# Setup production
bench setup production

# Restart services
bench restart

# Update app
bench update --app posawesome
```

## Useful Frappe APIs

```python
# Common utilities
from frappe.utils import cint, flt, cstr, getdate, add_days, today, now_datetime

# Database operations
frappe.db.get_value("DocType", "name", "field")
frappe.db.set_value("DocType", "name", "field", "value")
frappe.db.commit()

# User interactions
frappe.msgprint("Message")
frappe.throw("Error message")

# Translations
_("Text to translate")
```

## Configuration Notes

- This project uses the new esbuild-based build system (Frappe v14+)
- Frontend assets are compiled to `posawesome/public/dist/`
- Development mode enables auto-reloading and debugging features
- Production builds are optimized and minified

## Stock & Batch Validation Architecture (2026-04 onward)

The cart deliberately **does not** block over-stock additions on the
client. The architecture is "client = best-effort cache, server =
source of truth at submit time" — this avoided a class of bugs where
drifting client references (`item.actual_qty`, `_base_actual_qty`,
`batch_no_data.original_batch_qty` re-stamped on every detail fetch,
items store hydrated from offline cache during boot) caused either
false rejections of legitimate sales or silent oversells.

**Validation pipeline:**

1. `useCartValidation.validateCartItem` — only blocks the literal
   `actual_qty === 0 && posa_display_items_in_stock` case.
   Everything else passes through.
2. Auto-batch picker in
   `frontend/src/posapp/composables/pos/items/useItemAddition.ts`
   tags each line with a batch. The fallback (when no usable batches
   remain after cart deduction) MUST filter to batches with positive
   `original_batch_qty` to skip "zombie" batches (entries left in
   `batch_no_data` from a stale warehouse / Stock Reconciliation).
   Picking a zombie silently lands the cart on a batch ERPNext
   rejects with "Batch X has negative stock of quantity -N".
3. Pre-flight `check_invoice_availability` — server-side dry-run
   called by `usePaymentSubmission.checkAvailabilityBeforeSubmit`
   right before submit. Uses the same `_collect_stock_errors`
   pipeline the actual submit uses. On `ok: false`, emits
   `open_stock_conflict_dialog` for `StockConflictDialog`.
4. Submit catch block — `usePaymentSubmission.submitInvoice` parses
   server-side "negative stock" messages via the shared
   `parseNegativeStockMessage` from `frontend/src/posapp/utils/stock.ts`
   and re-routes to the same dialog.
5. Background submit failures — `pos_invoice_submit_error` realtime
   event handled in `frontend/src/posapp/stores/socketStore.ts`
   parses the shortage, refreshes the items panel cache, and
   shows a focused msgprint instead of the raw error dump.

**Two ERPNext negative-stock message formats** are supported by the
parser (the literal word "quantity" between "of" and the number is
optional):

- Legacy Bin-level: `has negative stock of -1.0`
- v15+ Serial and Batch Bundle (`BatchNegativeStockError`):
  `has negative stock of quantity -1.0`
  (frappe/erpnext#41908, #41909)

## Closing-shift aggregation invariants (2026-05 onward)

A series of drift bugs on multi-currency, tax-inclusive, and
discounted invoices established these rules. Touching any of:
`posawesome/mizan/doctype/pos_closing_shift/closing_processing/overview.py`,
`useClosingSummary.ts`, `ShiftOverview.vue`, the dialog A4 print
(`usePrintClosingShift.ts`), or the Desk A4 print
(`pos_closing_shift.js::mizan_print_a4_closing_shift`) — keep these
invariants:

1. **Tax totals come from row-level sums.** Σ of every invoice's
   `taxes` child rows' `base_tax_amount` is the single source of
   truth — drives the headline `tax_company_currency_total`, the
   per-currency breakdown, AND the per-account breakdown. Don't
   accumulate `invoice.base_total_taxes_and_charges` separately
   and expect it to match — tax-inclusive pricing and discount-on-
   tax invoices have field-vs-row drift.

2. **Gross / Net / Average Ticket use base_grand_total.**
   Gross = Σ(positive `base_grand_total`); Net = Gross − returns
   (= Σ of all `base_grand_total` including negatives); Average
   = Gross ÷ sale_invoices_count. Tax is NEVER folded into either
   — it's its own card / section.

3. **Reconciliation `expected_amount` per mode = Σ of
   `payment.base_amount` across invoices**, MINUS change_amount
   for the cash mode. For an invoice paid entirely on one mode
   that's identical to `base_grand_total`; for split-payment
   invoices it's the per-mode share.

4. **Multi-currency display: trust `multi_currency_totals.total`,
   not ratio projection.** The server's per-currency aggregate is
   already correct. Don't compute a ratio of company-currency
   aggregates and project — discount/tax shifts make ratio math
   drift.

5. **Closing-amount input never round-trips on every keystroke.**
   The v-text-field model-value is bound to a per-row local
   display state (verbatim what the cashier typed); on input we
   ALSO write `item.closing_amount = typed ÷ rate` so submit
   validation has a fresh number, but the displayed string is
   never re-derived from the round-trip product. A × ÷ × at any
   non-1 rate compounds float loss into the input.

## Brand identity vs bench slug (Mizan rename)

**Frappe module** is `Mizan` (renamed from `POSAwesome` on
`feat/mizan-module-rename`, 2026-04-30). On-disk module dir is
`posawesome/mizan/`, every DocType / Page / Workspace JSON
`"module"` field reads `Mizan`, all Python imports go through
`posawesome.mizan.*`, the workspace lives at `/app/mizan`.

**Bench app slug** is and STAYS `posawesome`. That's the slug for
`bench --app posawesome ...`, `/assets/posawesome/dist/...` asset
URLs, the Python package root, `pyproject.toml` `name`, IndexedDB
key prefixes. Renaming the bench slug is Option C from the
planning conversation — out of scope, would force an
uninstall/reinstall on production with manual data porting.

When making user-visible changes, default copy to **Mizan** (or
"Infoney Mizan" in formal contexts). When writing imports, file
paths, or asset URLs, the slug is **posawesome**.