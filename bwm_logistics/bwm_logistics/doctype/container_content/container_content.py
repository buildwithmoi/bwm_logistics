# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ContainerContent(Document):
	"""What is physically inside a container, and whose it is.

	The container is the box; this is its manifest. `customer` empty means the
	goods are ours (own-goods trading); set, it names the customer whose cargo
	is riding in a consolidated box — which is what lets a milestone notification
	say "your 200 cartons" rather than naming a container the customer has no
	way to identify.
	"""

	pass
