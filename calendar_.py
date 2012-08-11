#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import logging
from trytond.model import ModelSQL, ModelView, fields
from trytond.tools import get_smtp_server
from trytond.transaction import Transaction
from trytond.pool import Pool


class Event(ModelSQL, ModelView):
    _name = 'calendar.event'

    organizer_schedule_status = fields.Selection([
            ('', ''),
            ('1.0', '1.0'),
            ('1.1', '1.1'),
            ('1.2', '1.2'),
            ('3.7', '3.7'),
            ('3.8', '3.8'),
            ('5.1', '5.1'),
            ('5.2', '5.2'),
            ('5.3', '5.3'),
            ], 'Schedule Status')
    organizer_schedule_agent = fields.Selection([
            ('', ''),
            ('NONE', 'None'),
            ('SERVER', 'Server'),
            ('CLIENT', 'Client'),
            ], 'Schedule Agent')

    def default_schedule_agent(self):
        return 'SERVER'

    def __init__(self):
        super(Event, self).__init__()
        self._error_messages.update({
            'new_subject': 'Invitation: %s @ %s',
            'new_body': 'You have been invited to the following event.\n\n',
            'update_subject': 'Updated Invitation: %s @ %s',
            'update_body': 'This event has been changed.\n\n',
            'cancel_subject': 'Cancelled Event: %s @ %s',
            'cancel_body': 'This event has been canceled.\n\n',
            'no_subject': "(No Subject)",
            'separator': ':',
            'bullet': '    * ',
            'when': 'When',
            })

    def ical2values(self, event_id, ical, calendar_id, vevent=None):
        res = super(Event, self).ical2values(event_id, ical, calendar_id,
                vevent=vevent)

        if not vevent:
            vevent = ical.vevent

        if not hasattr(vevent, 'organizer'):
            return res

        for key in ('status', 'agent'):
            field = 'organizer_schedule_' + key
            param = 'SCHEDULE-' + key.upper()
            if param in vevent.organizer.params and vevent.organizer[param] \
                    in dict(self[field].selection):
                res[field] = vevent.organizer[param]

        return res

    def event2ical(self, event):
        """
        Override default event2ical to add schedule-status and
        schedule-agent properties

        If key skip_schedule_agent is present and associated to True, will
        prevent the schedule-status to be add to the organiser property. This
        is needed when one want to generate an ical that will be used for
        scheduling message.
        """

        ical = super(Event, self).event2ical(event)
        if isinstance(event, (int, long)):
            event = self.browse(event)

        vevent = ical.vevent

        if event.organizer_schedule_status:
            if not hasattr(vevent, 'organizer'):
                vevent.add('organizer')
            vevent.organizer.params['SCHEDULE-STATUS'] = \
                (event.organizer_schedule_status,)

        if Transaction().context.get('skip_schedule_agent'):
            return ical

        if event.organizer_schedule_agent:
            if not hasattr(vevent, 'organizer'):
                vevent.add('organizer')
            vevent.organizer.params['SCHEDULE-AGENT'] = \
                event.organizer_schedule_agent

        return ical

    def subject_body(self, type, event, owner):
        lang_obj = Pool().get('ir.lang')

        if not (event and owner):
            return "", ""
        lang = owner.language
        if not lang:
            lang_ids = lang_obj.search([
                ('code', '=', 'en_US'),
                ], limit=1)
            lang = lang_obj.browse(lang_ids[0])

        with Transaction().set_context(language=lang.code):
            summary = event.summary
            if not summary:
                summary = self.raise_user_error('no_subject',
                        raise_exception=False)

        date = lang_obj.strftime(event.dtstart, lang.code, lang.date)
        if not event.all_day:
            date += ' ' + lang_obj.strftime(event.dtstart, lang.code, '%H:%M')
            if event.dtend:
                date += ' -'
                if event.dtstart.date() != event.dtend.date():
                    date += ' ' + lang_obj.strftime(event.dtend, lang.code,
                            lang.date)
                date += ' ' + lang_obj.strftime(event.dtend, lang.code,
                        '%H:%M')
        else:
            if event.dtend and event.dtstart.date() != event.dtend.date():
                date += ' - ' + lang_obj.strftime(event.dtend, lang.code,
                        lang.date)
        if event.timezone:
            date += ' ' + event.timezone

        with Transaction().set_context(language=lang.code):
            subject = self.raise_user_error(type + '_subject',
                    (summary, date), raise_exception=False)
            body = self.raise_user_error(type + '_body', (summary, ),
                    raise_exception=False)
            separator = self.raise_user_error('separator',
                    raise_exception=False)
            bullet = self.raise_user_error('bullet', raise_exception=False)

        fields_names = ['summary', 'dtstart', 'location', 'attendees']
        if type == 'cancel':
            fields_names.remove('attendees')
        with Transaction().set_context(language=lang.code):
            fields = self.fields_get(fields_names=fields_names)
            fields['dtstart']['string'] = self.raise_user_error('when',
                    raise_exception=False)
        for field in fields_names:
            if field == 'attendees':
                if lang.direction == 'ltr':
                    body += fields['attendees']['string'] + separator + '\n'
                    body += bullet + owner.email + '\n'
                    for attendee in event.attendees:
                        body += bullet + attendee.email + '\n'
                else:
                    body += separator + fields['attendees']['string'] + '\n'
                    body += owner.email + bullet + '\n'
                    for attendee in event.attendees:
                        body += attendee.email + bullet + '\n'
            elif event[field]:
                if field == 'summary':
                    value = summary
                elif field == 'dtstart':
                    value = date
                elif field == 'location':
                    value = event.location.name
                else:
                    value = event[field]
                if lang.direction == 'ltr':
                    body += fields[field]['string'] + separator + ' ' \
                            + value + '\n'
                else:
                    body += value + ' ' + separator \
                            + fields[field]['string'] + '\n'
        return subject, body

    def create_msg(self, from_addr, to_addrs, subject, body, ical=None):

        if not to_addrs:
            return None

        msg = MIMEMultipart()
        msg['To'] = ', '.join(to_addrs)
        msg['From'] = from_addr
        msg['Subject'] = subject

        inner = MIMEMultipart('alternative')

        msg_body = MIMEBase('text', 'plain')
        msg_body.set_payload(body.encode('UTF-8'), 'UTF-8')
        inner.attach(msg_body)

        attachment = MIMEBase('text', 'calendar')
        attachment.set_payload(ical.serialize())
        attachment.add_header('Content-Transfer-Encoding', 'quoted-printable',
                charset='UTF-8',
                method=ical.method.value.lower())
        inner.attach(attachment)

        msg.attach(inner)

        attachment = MIMEBase('application', 'ics')
        attachment.set_payload(ical.serialize(), 'UTF-8')
        attachment.add_header('Content-Disposition', 'attachment',
                filename='invite.ics', name='invite.ics')

        msg.attach(attachment)

        return msg

    def send_msg(self, from_addr, to_addrs, msg, type, event_id):
        '''
        Send message

        :param from_addr: a from-address string
        :param to_addrs: a list of to-address strings
        :param msg: a message string
        :param type: the type (new, update, cancel)
        :param event_id: the id of the calendar.event
        :return: list of email addresses sent
        '''
        user_obj = Pool().get('res.user')

        if not to_addrs:
            return to_addrs
        to_addrs = list(set(to_addrs))

        user_ids = user_obj.search([
            ('email', 'in', to_addrs),
            ])
        for user in user_obj.browse(user_ids):
            if not user['calendar_email_notification_' + type]:
                to_addrs.remove(user.email)

        success = False
        try:
            server = get_smtp_server()
            server.sendmail(from_addr, to_addrs, msg.as_string())
            server.quit()
            success = to_addrs
        except Exception:
            logging.getLogger('calendar_scheduling').error(
                'Unable to deliver scheduling mail for event %s' % event_id)
        return success

    @staticmethod
    def attendees_to_notify(event):
        if not event.calendar.owner:
            return [], None
        attendees = event.attendees
        organizer = event.organizer
        owner = event.calendar.owner
        if event.parent:
            if not attendees:
                attendees = event.parent.attendees
                organizer = event.parent.organizer
                owner = event.parent.calendar.owner
            elif not organizer:
                organizer = event.parent.organizer
                owner = event.parent.calendar.owner

        if organizer != owner.email:
            return [], None

        to_notify = []
        for attendee in attendees:
            if attendee.email == organizer:
                continue
            if attendee.schedule_agent and\
                    attendee.schedule_agent != 'SERVER':
                continue
            to_notify.append(attendee)

        return to_notify, owner

    def create(self, values):
        attendee_obj = Pool().get('calendar.event.attendee')
        res = super(Event, self).create(values)

        if Transaction().user == 0:
            # user is 0 means create is triggered by another one
            return res

        event = self.browse(res)

        to_notify, owner = self.attendees_to_notify(event)
        if not to_notify:
            return res

        with Transaction().set_context(skip_schedule_agent=True):
            ical = self.event2ical(event)
        ical.add('method')
        ical.method.value = 'REQUEST'

        attendee_emails = [a.email for a in to_notify]

        subject, body = self.subject_body('new', event, owner)
        msg = self.create_msg(owner.email, attendee_emails, subject, body,
                ical)
        sent = self.send_msg(owner.email, attendee_emails, msg, 'new',
                event.id)

        vals = {'status': 'needs-action'}
        if sent:
            vals['schedule_status'] = '1.1'  # successfully sent
        else:
            vals['schedule_status'] = '5.1'  # could not complete delivery
        attendee_obj.write([a.id for a in to_notify], vals)

        return res

    def write(self, ids, values):
        attendee_obj = Pool().get('calendar.event.attendee')

        if Transaction().user == 0:
            # user is 0 means write is triggered by another one
            return super(Event, self).write(ids, values)

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not values or not ids:
            return super(Event, self).write(ids, values)

        event_edited = False
        for k in values:
            if k != 'attendees':
                event_edited = True
                break

        # store old attendee info
        events = self.browse(ids)
        event2former_emails = {}
        former_organiser_mail = {}
        former_organiser_lang = {}
        for event in events:
            to_notify, owner = self.attendees_to_notify(event)
            event2former_emails[event.id] = [a.email for a in to_notify]
            former_organiser_mail[event.id] = owner and owner.email
            former_organiser_lang[event.id] = owner and owner.language \
                and owner.language.code

        res = super(Event, self).write(ids, values)

        events = self.browse(ids)

        for event in events:
            current_attendees, owner = self.attendees_to_notify(event)
            owner_email = owner and owner.email
            current_emails = [a.email for a in current_attendees]
            former_emails = event2former_emails.get(event.id, [])
            missing_mails = filter(lambda mail: mail not in current_emails,
                    former_emails)

            if missing_mails:
                with Transaction().set_context(skip_schedule_agent=True):
                    ical = self.event2ical(event)
                ical.add('method')
                ical.method.value = 'CANCEL'

                subject, body = self.subject_body('cancel', event, owner)
                msg = self.create_msg(former_organiser_mail[event.id],
                        missing_mails, subject, body, ical)
                sent = self.send_msg(former_organiser_mail[event.id],
                        missing_mails, msg, 'cancel', event.id)

            new_attendees = filter(lambda a: a.email not in former_emails,
                current_attendees)
            old_attendees = filter(lambda a: a.email in former_emails,
                current_attendees)
            with Transaction().set_context(skip_schedule_agent=True):
                ical = self.event2ical(event)
            if not hasattr(ical, 'method'):
                ical.add('method')

            sent_succes = []
            sent_fail = []
            if event_edited:
                if event.status == 'cancelled':
                    ical.method.value = 'CANCEL'
                    #send cancel to old attendee
                    subject, body = self.subject_body('cancel', event, owner)
                    msg = self.create_msg(owner_email,
                            [a.email for a in old_attendees],
                            subject, body, ical)
                    sent = self.send_msg(owner_email,
                            [a.email for a in old_attendees],
                            msg, 'cancel', event.id)
                    if sent:
                        sent_succes += old_attendees
                    else:
                        sent_fail += old_attendees

                else:
                    ical.method.value = 'REQUEST'
                    #send update to old attendees
                    subject, body = self.subject_body('update', event, owner)
                    msg = self.create_msg(owner_email,
                            [a.email for a in old_attendees],
                            subject, body, ical)
                    sent = self.send_msg(owner_email,
                            [a.email for a in old_attendees],
                            msg, 'update', event.id)
                    if sent:
                        sent_succes += old_attendees
                    else:
                        sent_fail += old_attendees
                    #send new to new attendees
                    subject, body = self.subject_body('new', event, owner)
                    msg = self.create_msg(owner_email,
                            [a.email for a in new_attendees],
                            subject, body, ical)
                    sent = self.send_msg(owner_email,
                            [a.email for a in new_attendees],
                            msg, 'new', event.id)
                    if sent:
                        sent_succes += new_attendees
                    else:
                        sent_fail += new_attendees

            else:
                if event.status != 'cancelled':
                    ical.method.value = 'REQUEST'
                    #send new to new attendees
                    subject, body = self.subject_body('new', event, owner)
                    msg = self.create_msg(owner_email,
                            [a.email for a in new_attendees],
                            subject, body, ical)
                    sent = self.send_msg(owner_email,
                            [a.email for a in new_attendees],
                            msg, 'new', event.id)
                    if sent:
                        sent_succes += new_attendees
                    else:
                        sent_fail += new_attendees

                vals = {'status': 'needs-action'}
                vals['schedule_status'] = '1.1'  # successfully sent
                attendee_obj.write([a.id for a in sent_succes], vals)
                vals['schedule_status'] = '5.1'  # could not complete delivery
                attendee_obj.write([a.id for a in sent_fail], vals)
        return res

    def delete(self, ids):
        if Transaction().user == 0:
            # user is 0 means the deletion is triggered by another one
            return super(Event, self).delete(ids)

        if isinstance(ids, (int, long)):
            ids = [ids]

        events = self.browse(ids)
        send_list = []
        for event in events:
            if event.status == 'cancelled':
                continue
            to_notify, owner = self.attendees_to_notify(event)
            if not to_notify:
                continue

            with Transaction().set_context(skip_schedule_agent=True):
                ical = self.event2ical(event)
            ical.add('method')
            ical.method.value = 'CANCEL'

            attendee_emails = [a.email for a in to_notify]
            subject, body = self.subject_body('cancel', event, owner)
            msg = self.create_msg(owner.email, attendee_emails, subject, body,
                    ical)

            send_list.append((owner.email, attendee_emails, msg, event.id,))

        res = super(Event, self).delete(ids)
        for args in send_list:
            owner_email, attendee_emails, msg, event_id = args
            self.send_msg(owner_email, attendee_emails, msg, 'cancel',
                    event_id)
        return res

Event()


class Attendee(ModelSQL, ModelView):
    _name = 'calendar.attendee'

    schedule_status = fields.Selection([
            ('', ''),
            ('1.0', '1.0'),
            ('1.1', '1.1'),
            ('1.2', '1.2'),
            ('3.7', '3.7'),
            ('3.8', '3.8'),
            ('5.1', '5.1'),
            ('5.2', '5.2'),
            ('5.3', '5.3'),
            ], 'Schedule Status')
    schedule_agent = fields.Selection([
            ('', ''),
            ('NONE', 'None'),
            ('SERVER', 'Server'),
            ('CLIENT', 'Client'),
            ], 'Schedule Agent')

    def default_schedule_agent(self):
        return 'SERVER'

    def attendee2values(self, attendee):
        res = super(Attendee, self).attendee2values(attendee)
        if hasattr(attendee, 'schedule_status'):
            if attendee.schedule_status in dict(
                    self.schedule_status.selection):
                res['schedule_status'] = attendee.schedule_status
        if hasattr(attendee, 'schedule_agent'):
            if attendee.schedule_agent in dict(self.schedule_agent.selection):
                res['schedule_agent'] = attendee.schedule_agent
        return res

    def attendee2attendee(self, attendee):
        res = super(Attendee, self).attendee2attendee(attendee)

        if attendee.schedule_status:
            if hasattr(res, 'schedule_status_param'):
                if res.schedule_status_param in dict(
                        self.schedule_status.selection):
                    res.schedule_status_param = attendee.schedule_status
            else:
                res.schedule_status_param = attendee.schedule_status
        elif hasattr(res, 'schedule_status_param'):
            if res.schedule_status_param in dict(
                    self.schedule_status.selection):
                del res.schedule_status_param

        if Transaction().context.get('skip_schedule_agent'):
            return res

        if attendee.schedule_agent:
            if hasattr(res, 'schedule_agent_param'):
                if res.schedule_agent_param in dict(
                        self.schedule_agent.selection):
                    res.schedule_agent_param = attendee.schedule_agent
            else:
                res.schedule_agent_param = attendee.schedule_agent
        elif hasattr(res, 'schedule_agent_param'):
            if res.schedule_agent_param in dict(self.schedule_agent.selection):
                del res.schedule_agent_param

        return res

Attendee()


class EventAttendee(ModelSQL, ModelView):
    _name = 'calendar.event.attendee'

    def __init__(self):
        super(EventAttendee, self).__init__()
        self._error_messages.update({
                'subject': '%s: %s @ %s',
                'body': ('%s (%s) changed his/her participation status '
                    'to: %s\n\n'),
                'accepted_body': '%s (%s) has accepted this invitation:\n\n',
                'declined_body': '%s (%s) has declined this invitattion:\n\n',
                'no_subject': "(No Subject)",
                'separator': ':',
                'bullet': '    * ',
                'when': 'When',
                })

    def subject_body(self, status, event, owner):
        lang_obj = Pool().get('ir.lang')
        event_obj = Pool().get('calendar.event')

        if not (event and owner):
            return "", ""
        lang = owner.language
        if not lang:
            lang_ids = lang_obj.search([
                ('code', '=', 'en_US'),
                ], limit=1)
            lang = lang_obj.browse(lang_ids[0])

        summary = event.summary
        if not summary:
            with Transaction().set_context(language=lang.code):
                summary = self.raise_user_error('no_subject',
                        raise_exception=False)

        date = lang_obj.strftime(event.dtstart, lang.code, lang.date)
        if not event.all_day:
            date += ' ' + lang_obj.strftime(event.dtstart, lang.code, '%H:%M')
            if event.dtend:
                date += ' -'
                if event.dtstart.date() != event.dtend.date():
                    date += ' ' + lang_obj.strftime(event.dtend, lang.code,
                            lang.date)
                date += ' ' + lang_obj.strftime(event.dtend, lang.code,
                        '%H:%M')
        else:
            if event.dtend and event.dtstart.date() != event.dtend.date():
                date += ' - ' + lang_obj.strftime(event.dtend, lang.code,
                        lang.date)
        if event.timezone:
            date += ' ' + event.timezone

        status_string = status
        fields_names = ['status']
        with Transaction().set_context(language=lang.code):
            fields = self.fields_get(fields_names=fields_names)
        for k, v in  fields['status']['selection']:
            if k == status:
                status_string = v

        with Transaction().set_context(language=lang.code):
            subject = self.raise_user_error('subject', (status, summary, date),
                    raise_exception=False)

            if status + '_body' in self._error_messages:
                body = self.raise_user_error(status + '_body',
                        (owner.name, owner.email), raise_exception=False)
            else:
                body = self.raise_user_error('body',
                        (owner.name, owner.email, status_string),
                        raise_exception=False)

            separator = self.raise_user_error('separator',
                    raise_exception=False)
            bullet = self.raise_user_error('bullet', raise_exception=False)

            fields_names = ['summary', 'dtstart', 'location', 'attendees']
            fields = event_obj.fields_get(fields_names=fields_names)
            fields['dtstart']['string'] = self.raise_user_error('when',
                    raise_exception=False)
        for field in fields_names:
            if field == 'attendees':
                organizer = event.organizer or event.parent.organizer
                if lang.direction == 'ltr':
                    body += fields['attendees']['string'] + separator + '\n'
                    if organizer:
                        body += bullet + organizer + '\n'
                    for attendee in event.attendees:
                        body += bullet + attendee.email + '\n'
                else:
                    body += separator + fields['attendees']['string'] + '\n'
                    if organizer:
                        body += owner.email + bullet + '\n'
                    for attendee in event.attendees:
                        body += attendee.email + bullet + '\n'
            elif event[field]:
                if field == 'summary':
                    value = summary
                elif field == 'dtstart':
                    value = date
                elif field == 'location':
                    value = event.location.name
                else:
                    value = event[field]
                if lang.direction == 'ltr':
                    body += fields[field]['string'] + separator + ' ' \
                            + value + '\n'
                else:
                    body += value + ' ' + separator \
                            + fields[field]['string'] + '\n'
        return subject, body

    def create_msg(self, from_addr, to_addr, subject, body, ical=None):

        if not to_addr:
            return None

        msg = MIMEMultipart()
        msg['To'] = to_addr
        msg['From'] = from_addr
        msg['Subject'] = subject

        inner = MIMEMultipart('alternative')

        msg_body = MIMEBase('text', 'plain')
        msg_body.set_payload(body.encode('UTF-8'), 'UTF-8')
        inner.attach(msg_body)

        attachment = MIMEBase('text', 'calendar')
        attachment.set_payload(ical.serialize())
        attachment.add_header('Content-Transfer-Encoding', 'quoted-printable',
                charset='UTF-8',
                method=ical.method.value.lower())
        inner.attach(attachment)

        msg.attach(inner)
        attachment = MIMEBase('application', 'ics')
        attachment.set_payload(ical.serialize(), 'UTF-8')
        attachment.add_header('Content-Disposition', 'attachment',
                filename='invite.ics', name='invite.ics')

        msg.attach(attachment)

        return msg

    def send_msg(self, from_addr, to_addr, msg, event_id):
        '''
        Send message

        :param from_addr: a from-address string
        :param to_addr: recipient address
        :param msg: a message string
        :param event_id: the id of the calendar.event
        :return: a boolean (True if the mail has been sent)
        '''
        success = False
        try:
            server = get_smtp_server()
            server.sendmail(from_addr, to_addr, msg.as_string())
            server.quit()
            success = True
        except Exception:
            logging.getLogger('calendar_scheduling').error(
                    'Unable to deliver reply mail for event %s' % event_id)
        return success

    @staticmethod
    def organiser_to_notify(attendee):
        event = attendee.event
        organizer = event.organizer or event.parent and event.parent.organizer
        if not organizer:
            return None
        if event.organizer_schedule_agent \
                and event.organizer_schedule_agent != 'SERVER':
            return None
        if organizer == event.calendar.owner.email:
            return None
        if attendee.email != event.calendar.owner.email:
            return None

        return organizer

    def write(self, ids, values):
        event_obj = Pool().get('calendar.event')

        if Transaction().user == 0:
            # user is 0 means write is triggered by another one
            return super(EventAttendee, self).write(ids, values)

        if 'status' not in values:
            return super(EventAttendee, self).write(ids, values)

        if isinstance(ids, (int, long)):
            ids = [ids]

        att2status = {}
        attendees = self.browse(ids)
        for attendee in attendees:
            att2status[attendee.id] = attendee.status

        res = super(EventAttendee, self).write(ids, values)

        attendees = self.browse(ids)
        for attendee in attendees:
            owner = attendee.event.calendar.owner
            if not owner or not owner.calendar_email_notification_partstat:
                continue
            organizer = self.organiser_to_notify(attendee)
            if not organizer:
                continue

            old, new = (att2status.get(attendee.id) or 'needs-action',
                        attendee.status or 'needs-action')

            if old == new:
                continue

            with Transaction().set_context(skip_schedule_agent=True):
                ical = event_obj.event2ical(attendee.event)
            if not hasattr(ical, 'method'):
                ical.add('method')
            ical.method.value = 'REPLY'

            subject, body = self.subject_body(new, attendee.event, owner)
            msg = self.create_msg(owner.email, organizer, subject, body, ical)

            sent = self.send_msg(owner.email, organizer, msg,
                    attendee.event.id)

            vals = {'organizer_schedule_status': sent and '1.1' or '5.1'}
            event_obj.write(attendee.event.id, vals)

        return res

    def delete(self, ids):
        event_obj = Pool().get('calendar.event')

        if Transaction().user == 0:
            # user is 0 means the deletion is triggered by another one
            return super(EventAttendee, self).delete(ids)

        if isinstance(ids, (int, long)):
            ids = [ids]
        attendees = self.browse(ids)
        send_list = []
        for attendee in attendees:
            owner = attendee.event.calendar.owner

            if attendee.status == 'declined':
                continue
            if not owner or not owner.calendar_email_notification_partstat:
                continue
            organizer = self.organiser_to_notify(attendee)
            if not organizer:
                continue

            with Transaction().set_context(skip_schedule_agent=True):
                ical = event_obj.event2ical(attendee.event)
            if not hasattr(ical, 'method'):
                ical.add('method')
            ical.method.value = 'REPLY'

            subject, body = self.subject_body('declined', attendee.event,
                    owner)
            msg = self.create_msg(owner.email, organizer, subject, body, ical)

            send_list.append((owner.email, organizer, msg, attendee.event.id))

        res = super(EventAttendee, self).delete(ids)
        for args in send_list:
            owner_email, organizer, msg, event_id = args
            sent = self.send_msg(owner_email, organizer, msg, event_id)
            vals = {'organizer_schedule_status': sent and '1.1' or '5.1'}
            event_obj.write(event_id, vals)

        return res

    def create(self, values):
        event_obj = Pool().get('calendar.event')

        res_id = super(EventAttendee, self).create(values)
        if Transaction().user == 0:
            # user is 0 means create is triggered by another one
            return res_id

        attendee = self.browse(res_id)

        owner = attendee.event.calendar.owner

        if (not attendee.status) or attendee.status in ('', 'needs-action'):
            return res_id
        if not owner or not owner.calendar_email_notification_partstat:
            return res_id
        organizer = self.organiser_to_notify(attendee)
        if not organizer:
            return res_id

        with Transaction().set_context(skip_schedule_agent=True):
            ical = event_obj.event2ical(attendee.event)
        if not hasattr(ical, 'method'):
            ical.add('method')
        ical.method.value = 'REPLY'

        subject, body = self.subject_body(attendee.status, attendee.event,
                owner)
        msg = self.create_msg(owner.email, organizer, subject, body, ical)

        sent = self.send_msg(owner.email, organizer, msg, attendee.event.id)

        vals = {'organizer_schedule_status': sent and '1.1' or '5.1'}
        event_obj.write(attendee.event.id, vals)

        return res_id

EventAttendee()
