# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import email
import logging
from datetime import date
from .tools import client_select

import imap_tools
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .tools import decode_imap4_utf7

_logger = logging.getLogger(__name__)

_IGNORE_FOLDERS = ["Drafts", "Trash"]


class WebmailFolder(models.Model):
    _name = "webmail.folder"
    _description = "Webmail Folders"
    _order = "technical_name"
    _rec_name = "complete_name"

    name = fields.Char(required=True, readonly=True)

    parent_id = fields.Many2one(
        comodel_name="webmail.folder",
        readonly=True,
    )

    account_id = fields.Many2one(
        comodel_name="webmail.account",
        ondelete="cascade",
        required=True,
        readonly=True,
    )

    user_id = fields.Many2one(
        comodel_name="res.users",
        related="account_id.user_id",
        store=True,
        readonly=True,
    )

    mail_ids = fields.One2many(
        comodel_name="webmail.mail",
        inverse_name="folder_id",
    )

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    technical_name = fields.Char(required=True, readonly=True)

    complete_name = fields.Char(
        compute="_compute_complete_name", recursive=True, store=True
    )

    last_fetch_date = fields.Date(readonly=True)

    limited_fetch = fields.Boolean(
        compute="_compute_limited_fetch",
        inverse="_inverse_limited_fetch",
        readonly=False,
        store=True,
    )

    included_in_cron_fetch = fields.Boolean(
        compute="_compute_included_in_cron_fetch", readonly=False, store=True
    )

    # ###########################
    # Compute Section
    # ###########################
    api.depends("technical_name")

    def _compute_included_in_cron_fetch(self):
        for folder in self:
            folder.included_in_cron_fetch = folder.technical_name in [
                "INBOX",
                "Junk",
                "Sent",
            ]

    @api.depends("last_fetch_date")
    def _compute_limited_fetch(self):
        for folder in self:
            folder.limited_fetch = folder.last_fetch_date

    def _inverse_limited_fetch(self):
        for folder in self:
            if folder.limited_fetch:
                folder.last_fetch_date = date.today()
            else:
                folder.last_fetch_date = False

    @api.depends("name", "parent_id.name")
    def _compute_complete_name(self):
        for folder in self:
            if folder.parent_id:
                folder.complete_name = " / ".join(
                    [folder.parent_id.complete_name, folder.name]
                )
            else:
                folder.complete_name = folder.name

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
    def _create_if_not_exists(self, webmail_account, folder_data):
        technical_name = folder_data.decode().split(' "/" ')[-1]
        complete_name = decode_imap4_utf7(folder_data.decode()).split(' "/" ')[-1]
        if complete_name in _IGNORE_FOLDERS:
            return
        if technical_name.startswith('"') and technical_name.endswith('"'):
            technical_name = technical_name[1:-1]
        self._recursive_get_or_create(webmail_account, complete_name, technical_name)

    def _recursive_get_or_create(self, webmail_account, complete_name, technical_name):
        separator = "/"
        # Check if folder exist in Odoo
        existing_folder = self.search(
            [
                ("account_id", "=", webmail_account.id),
                ("technical_name", "=", technical_name),
            ]
        )
        if existing_folder:
            return existing_folder

        technical_name_parts = technical_name.split(separator)
        complete_name_parts = complete_name.split(separator)
        vals = {
            "account_id": webmail_account.id,
            "technical_name": technical_name,
            "name": complete_name_parts[-1],
        }
        if separator in technical_name:
            vals.update(
                {
                    "parent_id": self._recursive_get_or_create(
                        webmail_account,
                        separator.join(complete_name_parts[:-1]),
                        separator.join(technical_name_parts[:-1]),
                    ).id
                }
            )

        _logger.debug(
            f"[FETCH] {webmail_account.login}:" f" Creation of folder {vals['name']}."
        )
        return self.create(vals)

    def _fetch_mails(self):
        for webmail_folder in self:
            client = webmail_folder.account_id._get_imap_client_connected()
            status, _select_code = client_select(client, f'"{webmail_folder.technical_name}"')
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
                            "account_login": webmail_folder.account_id.login,
                        }
                    )
                )
            if webmail_folder.last_fetch_date:
                fetch_date = webmail_folder.last_fetch_date + relativedelta(days=-1)
                domain = str(imap_tools.AND(date_gte=fetch_date))
                _logger.info(
                    f"Fetching Mails for folder '{webmail_folder.complete_name}'"
                    f" Since {fetch_date} ..."
                )
            else:
                domain = "ALL"
                _logger.info(
                    f"Fetching ALL mails for folder {webmail_folder.complete_name} ..."
                )
            status, search_result = client.search(None, domain)
            num_list = search_result[0].split()
            for index, num in enumerate(num_list, start=1):
                _logger.info(
                    f" {index}/{len(num_list)}:"
                    f" Get Mail #{num.decode()} in folder"
                    f" '{webmail_folder.complete_name}'."
                )
                status, mail_data = client.fetch(num, "(RFC822)")
                email_message = email.message_from_bytes(
                    mail_data[0][1], policy=email.policy.default
                )
                self.env["webmail.mail"]._create_or_update_mail(
                    webmail_folder, email_message
                )
            client.logout()
            if webmail_folder.last_fetch_date != date.today():
                webmail_folder.last_fetch_date = date.today()
