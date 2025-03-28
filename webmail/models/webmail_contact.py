# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mail import formataddr


class WebmailContact(models.Model):
    _name = "webmail.contact"
    _inherit = ["avatar.mixin"]
    _order = "name"

    _description = "Webmail Contacts"

    name = fields.Char()

    email = fields.Char(required=True)

    author_mail_ids = fields.One2many(
        comodel_name="webmail.mail", inverse_name="author_contact_id"
    )

    formatted_address = fields.Char(compute="_compute_formatted_address", store=True)

    author_mail_qty = fields.Integer(compute="_compute_author_mail_qty", store=True)

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "email_uniq",
            "unique (email)",
            "A contact with the same email already exists.",
        ),
    ]

    # ###########################
    # Compute Section
    # ###########################
    @api.depends("author_mail_ids.author_contact_id")
    def _compute_author_mail_qty(self):
        for contact in self:
            contact.author_mail_qty = len(contact.author_mail_ids)

    @api.depends("email", "name")
    def _compute_formatted_address(self):
        for contact in self:
            contact.formatted_address = formataddr((contact.name, contact.email))

    # ###########################
    # Button & Action Section
    # ###########################

    def action_view_mails(self):
        mails = self.mapped("author_mail_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_mail"
        )
        action["domain"] = [("id", "in", mails.ids)]
        return action

    # ###########################
    # Private Section
    # ###########################
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
            email = email.lower()
            existing_contact = self.with_context(active_test=False).search(
                [("email", "=", email)]
            )
            if existing_contact:
                if not existing_contact.name and name:
                    existing_contact.write({"name": name})
                return existing_contact
            else:
                return self.create({"name": name, "email": email})
