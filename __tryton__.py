# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Calendar Scheduling',
    'name_fr_FR' : 'Programmation calendrier',
    'version' : '0.0.1',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add Scheduling support on CalDAV',
    'description_fr_FR': 'Ajoute la gestion de la programmation d\'évènements au CalDAV',
    'depends' : [
        'ir',
        'res',
        'webdav',
        'calendar',
    ],
    'xml' : [
        'res.xml',
    ],
    'translation': [
    ],
}
