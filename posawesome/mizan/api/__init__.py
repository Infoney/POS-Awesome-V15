"""POS-Awesome (Mizan) API package.

Intentionally empty — submodules (`utilities`, `items`, `invoices`,
`shifts`, etc.) are imported on demand by Frappe's whitelisted-method
dispatch (`frappe.get_attr("posawesome.mizan.api.<submodule>.<fn>")`),
which only needs the parent package to exist as a namespace, not to
pre-load every child.

History: this file used to eagerly do `from .X import …` for ~13
submodules. None of the eager re-exports were actually consumed
(grep for `from posawesome.mizan.api import …` is empty across the
whole repo). They were dead weight — and they opened a cold-start
race: under concurrent first-hit load, two worker threads racing
through the package init could each hold one submodule's
`_ModuleLock` while waiting for another, and Python's import system
would abort one of them with

    Failed to get method for command posawesome.mizan.api.<X>.<fn>
    with deadlock detected by _ModuleLock('posawesome.mizan.api.<Y>')

Self-resolved on the next request once `sys.modules` was warm, but
recurred after every `bench restart` / worker recycle. Reported
twice on AL-KHANSA: once on `get_terminal_employees` (lock on
`shifts`) and once on `get_current_user_language` (lock on
`shifts`).

If a future caller wants `from posawesome.mizan.api import get_items`
shorthand back, prefer adding it inline at the import site rather
than re-introducing the eager block here.
"""
