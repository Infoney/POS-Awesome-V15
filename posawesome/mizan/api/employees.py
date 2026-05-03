from __future__ import annotations

import frappe
from frappe import _


def _resolve_profile_name(pos_profile=None) -> str:
	if isinstance(pos_profile, dict):
		return str(pos_profile.get("name") or "").strip()

	if isinstance(pos_profile, str):
		return pos_profile.strip()

	return ""


def _get_terminal_users(profile_name: str) -> list[str]:
	rows = frappe.get_all(
		"POS Profile User",
		filters={"parent": profile_name},
		fields=["user"],
		order_by="idx asc, creation asc",
		ignore_permissions=True,
	)
	return [row.get("user") for row in rows if row.get("user")]


def _ensure_terminal_user(profile_name: str, user: str):
	terminal_users = _get_terminal_users(profile_name)
	if user not in terminal_users:
		frappe.throw(_("Selected cashier is not assigned to this POS profile."))
	return terminal_users


def _get_user_doc(user: str):
	user_doc = frappe.get_doc("User", user)
	if not int(getattr(user_doc, "enabled", 1) or 0):
		frappe.throw(_("Selected cashier is disabled."))
	return user_doc


def _get_user_pin(user_doc) -> str:
	# Use the lower-level password helper with `raise_exception=False`
	# so a user who hasn't set a PIN yet doesn't get the noisy
	#   Password not found for User <email> posa_pos_pin
	# entry in `Error Log` every time the Manage Pharmacist PIN form
	# pre-fetches the current value. `Document.get_password` raises +
	# logs before we can catch it; the helper just returns None.
	try:
		from frappe.utils.password import get_decrypted_password
		pin = get_decrypted_password(
			"User",
			user_doc.name,
			"posa_pos_pin",
			raise_exception=False,
		)
		return str(pin or "").strip()
	except Exception:
		return ""


def _is_pos_supervisor(user_doc) -> bool:
	return bool(getattr(user_doc, "posa_is_pos_supervisor", 0))


def _validate_new_pin(new_pin: str) -> str:
	pin = str(new_pin or "").strip()
	if not pin:
		frappe.throw(_("Enter a new PIN."))
	if not pin.isdigit():
		frappe.throw(_("PIN must contain digits only."))
	if len(pin) < 4 or len(pin) > 8:
		frappe.throw(_("PIN must be between 4 and 8 digits."))
	return pin


@frappe.whitelist()
def get_terminal_employees(pos_profile=None):
	profile_name = _resolve_profile_name(pos_profile)
	if not profile_name:
		frappe.throw(_("POS profile is required to load terminal employees."))

	users = _get_terminal_users(profile_name)
	if not users:
		return []

	# `posa_sales_person` is added by the cashier-tracking patch and
	# may not exist on tenants that haven't migrated yet. Guard the
	# fetch so the fields list adapts.
	user_fields = ["name", "full_name", "enabled", "posa_is_pos_supervisor"]
	has_sales_person_field = False
	try:
		has_sales_person_field = frappe.db.has_column("User", "posa_sales_person")
	except Exception:
		pass
	if has_sales_person_field:
		user_fields.append("posa_sales_person")

	user_rows = frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1},
		fields=user_fields,
		order_by="full_name asc, name asc",
		ignore_permissions=True,
	)
	user_map = {row.get("name"): row for row in user_rows}
	current_user = frappe.session.user

	employees = []
	for user in users:
		row = user_map.get(user)
		if not row:
			continue
		employees.append(
			{
				"user": row.get("name"),
				"full_name": row.get("full_name") or row.get("name"),
				"enabled": row.get("enabled", 1),
				"is_current": row.get("name") == current_user,
				"is_supervisor": bool(row.get("posa_is_pos_supervisor")),
				# Optional Sales Person link — when set, the POS auto-
				# selects this Sales Person as the default for any
				# transactions this cashier rings (per user spec:
				# switching cashiers also switches the default sales
				# person to the new cashier's link). Empty when the
				# user hasn't set `posa_sales_person`.
				"posa_sales_person": row.get("posa_sales_person") or "",
			}
		)

	return employees


@frappe.whitelist()
def verify_terminal_employee_pin(pos_profile=None, user=None, pin=None):
	profile_name = _resolve_profile_name(pos_profile)
	if not profile_name:
		frappe.throw(_("POS profile is required to verify cashier access."))

	user = str(user or "").strip()
	pin = str(pin or "").strip()
	if not user or not pin:
		frappe.throw(_("Cashier and PIN are required."))

	_ensure_terminal_user(profile_name, user)
	user_doc = _get_user_doc(user)
	stored_pin = _get_user_pin(user_doc)

	if not stored_pin or stored_pin != pin:
		frappe.throw(_("Invalid cashier PIN."))

	return {
		"user": user_doc.name,
		"full_name": user_doc.full_name or user_doc.name,
		"enabled": user_doc.enabled,
		"is_supervisor": _is_pos_supervisor(user_doc),
	}


@frappe.whitelist()
def get_cashier_pin_status(pos_profile=None, user=None):
	profile_name = _resolve_profile_name(pos_profile)
	if not profile_name:
		frappe.throw(_("POS profile is required to manage cashier PIN."))

	user = str(user or "").strip()
	if not user:
		frappe.throw(_("Cashier is required."))

	_ensure_terminal_user(profile_name, user)
	user_doc = _get_user_doc(user)
	existing_pin = _get_user_pin(user_doc)

	return {
		"user": user_doc.name,
		"full_name": user_doc.full_name or user_doc.name,
		"has_pin": bool(existing_pin),
		"is_supervisor": _is_pos_supervisor(user_doc),
	}


@frappe.whitelist()
def save_cashier_pin(pos_profile=None, user=None, new_pin=None, current_pin=None):
	profile_name = _resolve_profile_name(pos_profile)
	if not profile_name:
		frappe.throw(_("POS profile is required to save cashier PIN."))

	user = str(user or "").strip()
	if not user:
		frappe.throw(_("Cashier is required."))

	_ensure_terminal_user(profile_name, user)
	user_doc = _get_user_doc(user)
	existing_pin = _get_user_pin(user_doc)
	next_pin = _validate_new_pin(new_pin)

	if existing_pin and str(current_pin or "").strip() != existing_pin:
		frappe.throw(_("Current PIN is incorrect."))

	if not hasattr(user_doc, "flags") or user_doc.flags is None:
		user_doc.flags = frappe._dict() if hasattr(frappe, "_dict") else type("Flags", (), {})()
	user_doc.flags.ignore_permissions = True
	user_doc.set("posa_pos_pin", next_pin)
	user_doc.save(ignore_permissions=True)

	return {
		"user": user_doc.name,
		"full_name": user_doc.full_name or user_doc.name,
		"has_pin": True,
		"is_supervisor": _is_pos_supervisor(user_doc),
	}
