# Copyright (C) 2023 - Today: OaaFS
# @author: Sylvain LE GAL (https://twitter.com/legalsylvain)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import imaplib
import socket

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WebmailAccount(models.Model):
    _name = "webmail.account"
    _description = "Webmail Accounts"
    _rec_name = "login"

    url = fields.Char(required=True)

    port = fields.Integer(required=True)

    login = fields.Char(required=True)

    user_id = fields.Many2one(comodel_name="res.users", required=True)

    password = fields.Char(required=True)

    folder_ids = fields.One2many(
        comodel_name="webmail.folder",
        inverse_name="account_id",
        readonly=True,
    )

    cron_id = fields.Many2one(
        string="Odoo Cron",
        comodel_name="ir.cron",
        readonly=True,
        help="Cron Task that will fetch account mails",
        ondelete="cascade",
    )

    folder_qty = fields.Integer(compute="_compute_folder_qty", store=True)

    mail_qty = fields.Integer(compute="_compute_mail_qty", store=True)

    # Overload Section
    @api.model_create_multi
    def create(self, vals_list):
        accounts = super().create(vals_list)
        for account in accounts:
            account.cron_id = self.env["ir.cron"].create(account._prepare_cron())
        return accounts

    # Compute Section
    @api.depends("folder_ids")
    def _compute_folder_qty(self):
        for account in self:
            account.folder_qty = len(account.folder_ids)

    @api.depends("folder_ids.mail_qty")
    def _compute_mail_qty(self):
        for account in self:
            account.mail_qty = sum(account.mapped("folder_ids.mail_qty"))

    # Action Section
    def button_test_connexion(self):
        self.ensure_one()
        client = self._get_imap_client_connected()
        client.close()
        client.logout()

    def button_fetch_folders(self):
        self._fetch_folders()

    def button_fetch_mails_by_batch(self):
        for folder in self.mapped("folder_ids"):
            folder._fetch_mails()
            self.env.cr.commit()  # pylint: disable=invalid-commit

    def action_view_folders(self):
        folders = self.mapped("folder_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_folder"
        )
        action["domain"] = [("id", "in", folders.ids)]
        return action

    def action_view_mails(self):
        mails = self.mapped("folder_ids.mail_ids")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "webmail.action_webmail_mail"
        )
        action["domain"] = [("id", "in", mails.ids)]
        return action

    # Private Section
    def _get_imap_client_connected(self):
        self.ensure_one()
        try:
            client = imaplib.IMAP4_SSL(self.url)
        except socket.gaierror as e:
            raise UserError(
                _(
                    "server '%s' has not been reached. Possible Reasons: \n"
                    "- the server doesn't exist"
                    "- your odoo instance faces to network issue"
                )
                % (self.url)
            ) from e

        try:
            client.login(self.login, self.password)
        except imaplib.IMAP4.error as e:
            raise UserError(
                _(
                    "Authentication failed. Possible Reasons: \n"
                    "- your credentials are incorrect (%s // **********)"
                )
                % (self.login)
            ) from e

        return client

    def _fetch_folders(self):
        for account in self:
            client = account._get_imap_client_connected()
            status, folder_datas = client.list()
            client.logout()

            for folder_data in folder_datas:
                self.env["webmail.folder"]._create_if_not_exists(account, folder_data)

    @api.model
    def _fetch_mail_by_cron(self, account_ids):
        accounts = self.browse(account_ids)
        for account in accounts:
            account._fetch_folders()
            account.mapped("folder_ids")._fetch_mails()

    def _prepare_cron(self):
        self.ensure_one()
        return {
            "name": f"Fetch Mails for account #{self.id}",
            "interval_type": "minutes",
            "interval_number": 10,
            "model_id": self.env["ir.model"]
            .search([("model", "=", self._name)], limit=1)
            .id,
            "state": "code",
            "code": f"model._fetch_mail_by_cron({self.ids})",
            "active": False,
        }
