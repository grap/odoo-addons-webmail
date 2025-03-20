# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class WebmailContact(models.Model):
    _name = "webmail.contact"
    _inherit = ["avatar.mixin"]

    _description = "Webmail Contacts"

    name = fields.Char()

    email = fields.Char(required=True)

    def _get_or_create(self, text, multi=False):
        if multi:
            # we have to split
            raise UserError(_("Not Implemented"))
        else:
            email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
            email = email and email.group()
            name = re.search(r'"(?P<name>.*)"', text)
            name = name and name.group("name")
            if not email:
                raise UserError(_(f"No email found in {text}"))
            existing_contact = self.search([("email", "=", email)])
            if existing_contact:
                if not existing_contact.name and name:
                    existing_contact.write({"name": name})
                return existing_contact
            else:
                return self.create({"name": name, "email": email})
