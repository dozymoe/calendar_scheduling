#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.tools import get_smtp_server
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import email.utils
import logging


class Event(ModelSQL, ModelView):
    _name = 'calendar.event'

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

    def subject_body(self, cursor, user, type, event, owner, context=None):
        lang_obj = self.pool.get('ir.lang')

        if context is None:
            context = {}

        if not (event and owner):
            return "", ""
        lang = owner.language
        if not lang:
            lang_ids = lang_obj.search(cursor, user, [
                ('code', '=', 'en_US'),
                ], limit=1, context=context)
            lang = lang_obj.browse(cursor, user, lang_ids[0], context=context)
        context = context.copy()
        context['language'] = lang.code

        summary = event.summary
        if not summary:
            summary = self.raise_user_error(cursor, 'no_subject',
                    raise_exception=False, context=context)

        date = lang_obj.strftime(event.dtstart.timetuple(), lang.code,
                lang.date)
        if not event.all_day:
            date += ' ' + lang_obj.strftime(event.dtstart.timetuple(),
                    lang.code, '%H:%M')
            date += ' -'
            if event.dtstart.date() != event.dtend.date():
                date += ' ' + lang_obj.strftime(event.dtend.timetuple(),
                        lang.code, lang.date)
            date += ' ' + lang_obj.strftime(event.dtend.timetuple(),
                    lang.code, '%H:%M')
        else:
            if event.dtstart.date() != event.dtend.date():
                date += ' - ' + lang_obj.strftime(event.dtend.timetuple(),
                        lang.code, lang.date)
        if event.timezone:
            date += ' ' + event.timezone

        subject = self.raise_user_error(cursor, type + '_subject',
                (summary, date), raise_exception=False, context=context)
        body = self.raise_user_error(cursor, type + '_body', (summary, ),
                raise_exception=False, context=context)
        separator = self.raise_user_error(cursor, 'separator',
                raise_exception=False, context=context)
        bullet = self.raise_user_error(cursor, 'bullet', raise_exception=False,
                context=context)

        fields_names = ['summary', 'dtstart', 'location', 'attendees']
        fields = self.fields_get(cursor, user, fields_names=fields_names,
                context=context)
        fields['dtstart']['string'] = self.raise_user_error(cursor,
                'when', raise_exception=False, context=context)
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
                else:
                    value = event[field]
                if lang.direction == 'ltr':
                    body += fields[field]['string'] + separator + ' ' \
                            + value + '\n'
                else:
                    body += value + ' ' + separator \
                            + fields[field]['string'] + '\n'
        return subject, body

    def create_msg(self, cursor, user, from_addr, to_addrs, subject,
            body, ical=None, context=None):

        if not to_addrs:
            return None

        msg = MIMEMultipart()
        msg['To'] = ', '.join(to_addrs)
        msg['From'] = from_addr
        msg['Subject'] = subject

        inner = MIMEMultipart('alternative')

        msg_body = MIMEBase('text', 'plain')
        msg_body.set_payload(body, 'UTF-8')
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

    def send_msg(self, cursor, user_id, from_addr, to_addrs, msg,
            type, event, context=None):
        '''
        Send message

        :param cursor: the database cursor
        :param user_id: the user id
        :param from_addr: a from-address string
        :param to_addrs: a list of to-address strings
        :param msg: a message string
        :param type: the type (new, update, cancel)
        :param event: a BrowseRecord of the calendar.event
        :param context: the context
        :return: list of email addresses sent
        '''
        user_obj = self.pool.get('res.user')

        if not to_addrs:
            return to_addrs
        to_addrs = list(set(to_addrs))

        user_ids = user_obj.search(cursor, user_id, [
            ('email', 'in', to_addrs),
            ], context=context)
        for user in user_obj.browse(cursor, user_id, user_ids, context=context):
            if not user['calendar_email_notification_' + type]:
                to_addrs.remove(user.email)

        success = False
        try:
            server = get_smtp_server()
            server.sendmail(from_addr, to_addrs, msg.as_string())
            server.quit()
            success = to_addrs
        except:
            logging.getLogger('calendar_scheduling').error(
                    'Unable to deliver scheduling mail for event %s' % event.id)
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
            if attendee.status == 'declined':
                continue
            if attendee.email == organizer:
                continue
            if attendee.schedule_agent and\
                    attendee.schedule_agent != 'SERVER':
                continue
            to_notify.append(attendee)

        return to_notify, owner

    def create(self, cursor, user, values, context=None):
        attendee_obj = self.pool.get('calendar.event.attendee')
        res = super(Event, self).create(cursor, user, values, context=context)

        event = self.browse(cursor, user, res, context=context)

        to_notify, owner = self.attendees_to_notify(event)
        if not to_notify:
            return res

        ical = self.event2ical(cursor, user, event, context=context)
        ical.add('method')
        ical.method.value = 'REQUEST'

        attendee_emails = [a.email for a in to_notify]

        subject, body = self.subject_body(cursor, user, 'new', event, owner,
                context=context)
        msg = self.create_msg(cursor, user, owner.email, attendee_emails,
                subject, body, ical, context=context)
        sent = self.send_msg(cursor, user, owner.email,
                attendee_emails, msg, 'new', event, context=context)

        vals = {'status': 'needs-action'}
        if sent:
            vals['schedule_status'] = '1.1' #successfully sent
        else:
            vals['schedule_status'] = '5.1' #could not complete delivery
        attendee_obj.write(cursor, user, [a.id for a in to_notify],
                vals, context=context)

        return res

    def write(self, cursor, user, ids, values, context=None):
        attendee_obj = self.pool.get('calendar.event.attendee')
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not values or not ids:
            return super(Event, self).write(cursor, user, ids, values,
                    context=context)

        event_edited = False
        for k in values:
            if k != 'attendees':
                event_edited = True
                break

        # store old attendee info
        events = self.browse(cursor, user, ids, context=context)
        event2former_emails = {}
        former_organiser_mail = {}
        former_organiser_lang = {}
        for event in events:
            to_notify, owner = self.attendees_to_notify(event)
            event2former_emails[event.id] = [a.email for a in to_notify]
            former_organiser_mail[event.id] = owner and owner.email
            former_organiser_lang[event.id] = owner and owner.language \
                and owner.language.code

        res = super(Event, self).write(cursor, user, ids, values,
                context=context)

        events = self.browse(cursor, user, ids, context=context)

        for event in events:
            current_attendees, owner = self.attendees_to_notify(event)
            owner_email = owner and owner.email
            current_emails = [a.email for a in current_attendees]
            former_emails = event2former_emails.get(event.id, [])
            missing_mails = filter(lambda mail: mail not in current_emails,
                    former_emails)

            if missing_mails:
                ctx = context and context.copy() or {}
                ctx['skip_schedule_agent'] = True
                ical = self.event2ical(cursor, user, event, context=ctx)
                ical.add('method')
                ical.method.value = 'CANCEL'

                subject, body = self.subject_body(cursor, user, 'cancel', event,
                        owner, context=context)
                msg = self.create_msg(cursor, user,
                        former_organiser_mail[event.id], missing_mails, subject,
                        body, ical, context=context)
                sent = self.send_msg(cursor, user,
                        former_organiser_mail[event.id], missing_mails, msg,
                        'cancel', event, context=context)

            new_attendees = filter(lambda a: a.email not in former_emails,
                current_attendees)
            old_attendees = filter(lambda a: a.email in former_emails,
                current_attendees)
            ctx = context and context.copy() or {}
            ctx['skip_schedule_agent'] = True
            ical = self.event2ical(cursor, user, event, context=ctx)
            if not hasattr(ical, 'method'):
                ical.add('method')

            sent_succes = []
            sent_fail = []
            if event_edited:
                if event.status == 'cancelled':
                    ical.method.value = 'CANCEL'
                    #send cancel to old attendee
                    subject, body = self.subject_body(cursor, user, 'cancel',
                            event, owner, context=context)
                    msg = self.create_msg(cursor, user,
                            owner_email, [a.email for a in old_attendees],
                            subject, body, ical, context=context)
                    sent = self.send_msg(cursor, user,
                            owner_email, [a.email for a in old_attendees], msg,
                            'cancel', event, context=context)
                    if sent:
                        sent_succes += old_attendees
                    else:
                        sent_fail += old_attendees

                else:
                    ical.method.value = 'REQUEST'
                    #send update to old attendees
                    subject, body = self.subject_body(cursor, user, 'update',
                            event, owner, context=context)
                    msg = self.create_msg(cursor, user,
                            owner_email, [a.email for a in old_attendees],
                            subject, body, ical, context=context)
                    sent = self.send_msg(cursor, user,
                            owner_email, [a.email for a in old_attendees], msg,
                            'update', event, context=context)
                    if sent:
                        sent_succes += old_attendees
                    else:
                        sent_fail += old_attendees
                    #send new to new attendees
                    subject, body = self.subject_body(cursor, user, 'new',
                            event, owner, context=context)
                    msg = self.create_msg(cursor, user,
                            owner_email, [a.email for a in new_attendees],
                            subject, body, ical, context=context)
                    sent = self.send_msg(cursor, user,
                            owner_email, [a.email for a in new_attendees], msg,
                            'new', event, context=context)
                    if sent:
                        sent_succes += new_attendees
                    else:
                        sent_fail += new_attendees

            else:
                if event.status != 'cancelled':
                    ical.method.value = 'REQUEST'
                    #send new to new attendees
                    subject, body = self.subject_body(cursor, user, 'new',
                            event, owner, context=context)
                    msg = self.create_msg(cursor, user,
                            owner_email, [a.email for a in new_attendees],
                            subject, body, ical, context=context)
                    sent = self.send_msg(cursor, user,
                            owner_email, [a.email for a in new_attendees], msg,
                            'new', event, context=context)
                    if sent:
                        sent_succes += new_attendees
                    else:
                        sent_fail += new_attendees

                vals = {'status': 'needs-action'}
                vals['schedule_status'] = '1.1' #successfully sent
                attendee_obj.write(cursor, user,
                        [a.id for a in sent_succes], vals, context=context)
                vals['schedule_status'] = '5.1' #could not complete delivery
                attendee_obj.write(cursor, user,
                        [a.id for a in sent_fail], vals, context=context)
        return res

    def delete(self, cursor, user, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]

        events = self.browse(cursor, user, ids, context=context)
        for event in events:
            if event.status == 'cancelled':
                continue
            to_notify, owner = self.attendees_to_notify(event)
            if not to_notify:
                continue

            ical = self.event2ical(cursor, user, event, context=context)
            ical.add('method')
            ical.method.value = 'CANCEL'

            attendee_emails = [a.email for a in to_notify]
            subject, body = self.subject_body(cursor, user, 'cancel',
                    event, owner, context=context)
            msg = self.create_msg(cursor, user, owner.email, attendee_emails,
                    subject, body, ical, context=context)
            sent = self.send_msg(cursor, user, owner.email,
                    attendee_emails, msg, 'cancel', event, context=context)

        return super(Event, self).delete(cursor, user, ids, context=context)

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

    def default_schedule_agent(self, cursor, user, context=None):
        return 'SERVER'

    def attendee2values(self, cursor, user, attendee, context=None):
        res = super(Attendee, self).attendee2values(cursor, user, attendee,
                context=context)
        if hasattr(attendee, 'schedule_status'):
            if attendee.schedule_status in dict(self.schedule_status.selection):
                res['schedule_status'] = attendee.schedule_status
        if hasattr(attendee, 'schedule_agent'):
            if attendee.schedule_agent in dict(self.schedule_agent.selection):
                res['schedule_agent'] = attendee.schedule_agent
        return res

    def attendee2attendee(self, cursor, user, attendee, context=None):
        res = super(Attendee, self).attendee2attendee(cursor, user, attendee,
                context=context)

        context = context or {}

        if attendee.schedule_status:
            if hasattr(res, 'schedule_status_param'):
                if res.schedule_status_param in dict(self.schedule_status.selection):
                    res.schedule_status_param = attendee.schedule_status
            else:
                res.schedule_status_param = attendee.schedule_status
        elif hasattr(res, 'schedule_status_param'):
            if res.schedule_status_param in dict(self.schedule_status.selection):
                del res.schedule_status_param

        if context.get('skip_schedule_agent'):
            return res

        if attendee.schedule_agent:
            if hasattr(res, 'schedule_agent_param'):
                if res.schedule_agent_param in dict(self.schedule_agent.selection):
                    res.schedule_agent_param = attendee.schedule_agent
            else:
                res.schedule_agent_param = attendee.schedule_agent
        elif hasattr(res, 'schedule_agent_param'):
            if res.schedule_agent_param in dict(self.schedule_agent.selection):
                del res.schedule_agent_param

        return res

Attendee()
