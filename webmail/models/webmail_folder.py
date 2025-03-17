# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WebmailFolder(models.Model):
    _name = "webmail.folder"
    _description = "Webmail Folders"
    _order = "technical_name"

    name = fields.Char(required=True, readonly=True)

    parent_id = fields.Many2one(
        comodel_name="webmail.folder",
        readonly=True,
    )

    webmail_account_id = fields.Many2one(
        comodel_name="webmail.account",
        ondelete="cascade",
        required=True,
        readonly=True,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        related="webmail_account_id.user_id",
        store=True,
        readonly=True,
    )

    mail_ids = fields.One2many(
        comodel_name="webmail.mail",
        inverse_name="folder_id",
    )

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    technical_name = fields.Char(required=True, readonly=True)

    # Compute Section
    @api.depends("mail_ids")
    def _compute_mail_qty(self):
        for folder in self:
            folder.mail_qty = len(folder.mail_ids)

    # Action Section
    def button_fetch_mails(self):
        self._fetch_mails()

    def action_view_mails(self):
        mails = self.mapped("mail_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_mail"
        )
        action["domain"] = [("id", "in", mails.ids)]
        return action

    # Private Section
    def _get_or_create(self, webmail_account, technical_name):
        separator = "/"
        # Check if folder exist in Odoo
        existing_folder = self.search(
            [
                ("webmail_account_id", "=", webmail_account.id),
                ("technical_name", "=", technical_name),
            ]
        )
        if existing_folder:
            return existing_folder

        name_parts = technical_name.split(separator)
        vals = {
            "webmail_account_id": webmail_account.id,
            "technical_name": technical_name,
            "name": name_parts[-1],
        }
        if separator in technical_name:
            vals.update(
                {
                    "parent_id": self._get_or_create(
                        webmail_account, separator.join(name_parts[:-1])
                    ).id
                }
            )

        _logger.debug(
            f"[FETCH] {webmail_account.login}:" f" Creation of folder {vals['name']}."
        )
        return self.create(vals)

    def _fetch_mails(self):
        for webmail_folder in self:
            client = webmail_folder.webmail_account_id._get_client_connected()
            _logger.info(f"Fetching Mails for folder {webmail_folder.technical_name}")
            status, select_code = client.select(f'"{webmail_folder.technical_name}"')
            if status != "OK":
                client.logout()
                raise UserError(
                    _(
                        "Folder %(folder_name)s doesn't exists"
                        " for account %(account_login)s."
                    )
                    % (
                        {
                            "folder_name": webmail_folder.technical_name,
                            "account_login": webmail_folder.webmail_account_id.login,
                        }
                    )
                )
            status, search_result = client.search(None, "ALL")
            num_list = search_result[0].split()
            for num in num_list:
                _logger.info(
                    f" {num.decode()}/{len(num_list)}:"
                    f" Get Mail in {webmail_folder.technical_name})."
                )
                status, mail_data = client.fetch(num, "(RFC822)")
                self.env["webmail.mail"]._create_or_update_mail(
                    webmail_folder, mail_data[0][1]
                )
            client.logout()
