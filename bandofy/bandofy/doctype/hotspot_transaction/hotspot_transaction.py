# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HotspotTransaction(Document):
	def before_insert(self):
		if not self.status:
			self.status = "Pending"
