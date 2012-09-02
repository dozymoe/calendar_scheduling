# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Calendar Scheduling',
    'name_de_DE' : 'Kalender Terminplanung',
    'name_es_CO' : 'Planificador del calendario',
    'name_es_ES' : 'Planificador del calendario',
    'name_fr_FR' : 'Programmation calendrier',
    'version': '1.8.4',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add Scheduling support on CalDAV',
    'description_de_DE' : 'Fügt Unterstützung für die Terminplanung in CalDAV hinzu',
    'description_es_CO' : 'Añade gestión de planificación de eventos a CalDAV',
    'description_es_ES' : 'Añade la gestión de planificación de eventos a CalDAV',
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
        'de_DE.csv',
        'es_ES.csv',
        'es_CO.csv',
        'fr_FR.csv',
    ],
}
