# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


from odoo import api, fields, models


class WebmailProvider(models.Model):
    _name = "webmail.provider"
    _inherit = ["avatar.mixin"]
    _description = "Webmail Providers"
    _order = "name"

    name = fields.Char(required=True)

    imap_url = fields.Char(required=True)

    imap_port = fields.Integer(required=True, default=993)

    smtp_url = fields.Char(
        required=True,
        compute="_compute_smtp_url",
        readonly=False,
        store=True,
        precompute=True,
    )

    smtp_port = fields.Integer(required=True, default=465)

    documentation_url = fields.Char()

    @api.depends("imap_url")
    def _compute_smtp_url(self):
        for provider in self.filtered(lambda x: not x.smtp_url):
            provider.smtp_url = provider.imap_url
