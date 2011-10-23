# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name' : 'Calendar Scheduling',
    'name_bg_BG' : 'График към календар',
    'name_de_DE' : 'Kalender Terminplanung',
    'name_es_CO' : 'Planificador del calendario',
    'name_es_ES' : 'Planificador del calendario',
    'name_fr_FR' : 'Programmation calendrier',
    'name_ru_RU' : 'Календарное планирование',
    'version' : '2.1.0',
    'author' : 'B2CK',
    'email': 'info@b2ck.com',
    'website': 'http://www.tryton.org/',
    'description': 'Add Scheduling support on CalDAV',
    'description_bg_BG' : 'Добавя график към CalDAV',
    'description_de_DE' : 'Fügt Unterstützung für die Terminplanung in CalDAV hinzu',
    'description_es_CO' : 'Añade gestión de planificación de eventos a CalDAV',
    'description_es_ES' : 'Añade la gestión de planificación de eventos a CalDAV',
    'description_fr_FR' : 'Ajoute la gestion de la programmation d\'évènements au CalDAV',
    'description_ru_RU' : 'Добавление поддержки планирования для CalDAV',
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
        'locale/bg_BG.po',
        'locale/cs_CZ.po',
        'locale/de_DE.po',
        'locale/es_ES.po',
        'locale/es_CO.po',
        'locale/fr_FR.po',
        'locale/nl_NL.po',
        'locale/ru_RU.po',
    ],
}
