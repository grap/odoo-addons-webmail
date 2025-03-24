# Copyright (C) 2025 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from random import randint

from odoo import api, fields, models


class WebmailTag(models.Model):
    _name = "webmail.tag"
    _order = "name"
    _description = "Webmail Tags"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(required=True)

    color = fields.Integer(default=lambda x: x._get_default_color())

    _sql_constraints = [
        ("name_uniq", "unique (name)", "A tag with the same name already exists."),
    ]

    @api.model
    def name_create(self, name):
        existing_tag = self.search([("name", "=ilike", name.strip())], limit=1)
        if existing_tag:
            return existing_tag.id, existing_tag.display_name
        return super().name_create(name)
