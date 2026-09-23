# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe import _
from frappe.model.document import Document


class HotspotVoucherBatch(Document):
	def generate_vouchers(self):
		remaining = (self.quantity or 0) - (self.generated_count or 0)
		if remaining <= 0:
			frappe.throw(_("All vouchers for this batch are already generated."))

		package = frappe.db.get_value(
			"Hotspot Package",
			self.package_name,
			["price", "duration_minutes"],
			as_dict=True,
		)
		if not package:
			frappe.throw(_("Could not find package {0}.").format(self.package_name))

		created = 0

		for _i in range(remaining):
			voucher = frappe.new_doc("Hotspot Voucher")
			voucher.voucher_code = _build_unique_voucher_code()
			voucher.status = "Unused"
			voucher.site = self.site
			voucher.batch = self.name
			voucher.package_name = self.package_name
			voucher.price = package.price
			voucher.duration_minutes = package.duration_minutes
			voucher.expires_on = self.expires_on
			voucher.insert(ignore_permissions=True)
			created += 1

		self.generated_count = (self.generated_count or 0) + created
		self.status = "Generated"
		self.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		return created


def _build_unique_voucher_code():
	"""6 random digits, no letters -- easy to key in on a phone keypad."""
	for _i in range(20):
		code = str(secrets.randbelow(900000) + 100000)
		if not frappe.db.exists("Hotspot Voucher", {"voucher_code": code}):
			return code

	frappe.throw(_("Unable to generate a unique voucher code. Please retry."))


@frappe.whitelist()
def generate_vouchers_for_batch(batch):
	doc = frappe.get_doc("Hotspot Voucher Batch", batch)
	doc.check_permission("write")
	count = doc.generate_vouchers()
	return {"created": count, "batch": doc.name}
