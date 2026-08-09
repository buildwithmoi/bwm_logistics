# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ShipmentContainer(Document):
	"""One of the boxes a booking is carried in.

	A booking routinely spans several containers — a purchase split across two
	40-footers is one commercial event, not two. The single `Shipment.container`
	link this replaces could not express that.
	"""

	pass
