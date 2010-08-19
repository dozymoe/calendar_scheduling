#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields


class User(ModelSQL, ModelView):
    _name = 'res.user'

    calendar_email_notification_new = fields.Boolean(
            'New invitations')
    calendar_email_notification_update = fields.Boolean(
            'Changed invitations')
    calendar_email_notification_cancel = fields.Boolean(
            'Cancelled invitations')
    calendar_email_notification_partstat = fields.Boolean(
            'Invitation Replies')

    def default_calendar_email_notification_new(self):
        return True

    def default_calendar_email_notification_update(self):
        return True

    def default_calendar_email_notification_cancel(self):
        return True

    def default_calendar_email_notification_partstat(self):
        return True

    def __init__(self):
        super(User, self).__init__()
        self._preferences_fields += [
            'calendar_email_notification_new',
            'calendar_email_notification_update',
            'calendar_email_notification_cancel',
            'calendar_email_notification_partstat',
        ]

User()
