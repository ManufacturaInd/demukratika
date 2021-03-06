#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import codecs
import shutil
import click
from zenlog import log

from distutils.dir_util import copy_tree
from collections import OrderedDict
import datetime
from dateutil import parser as dateparser
from babel.dates import format_date as babel_format_date
import unicodecsv as csv
import json
import mistune
import jinja2


MP_DATASET_FILE = os.path.expanduser("~/Datasets/parlamento-deputados/data/deputados.json")
MPINFO_DATASET_FILE = os.path.expanduser("~/Datasets/parlamento-deputados/data/deputados-extra.csv")
GOV_DATASET_FILE = os.path.expanduser("~/Datasets/governos/data/governos.csv")
GOVPOST_DATASET_FILE = os.path.expanduser("~/Datasets/governos/data/governos-cargos.csv")
TRANSCRIPTS_DIR = os.path.expanduser("./transcricoes/")
TRANSCRIPT_DATASET_FILE = os.path.expanduser("~/Datasets/parlamento-datas_sessoes/data/datas-debates.csv")
TRANSCRIPT_DATASET_FILE_2 = os.path.expanduser("~/Datasets/parlamento-datas_sessoes/data/datas-parlamento.csv")

OUTPUT_DIR = "_output"
MEDIA_SOURCE_DIR = "_media"
MEDIA_PATH = "media/"
TRANSCRIPTS_PATH = "sessoes/"
MPS_PATH = "deputados/"
PHOTO_URL_BASE = '/media/img/deputados/'
TEMPLATE_DIR = "templates/"

MESES = ['janeiro', 'fevereiro', u'março', 'abril', 'maio', 'junho', 'julho',
         'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def get_date_dataset():
    data = csv.reader(open(TRANSCRIPT_DATASET_FILE, 'r'))
    # skip first row
    data.next()

    more_data = csv.reader(open(TRANSCRIPT_DATASET_FILE_2, 'r'))
    # skip first row
    more_data.next()

    data = list(data)

    for newrow in more_data:
        exists = False
        leg, sess, num = newrow[:3]
        for row in data:
            if row[:3] == [leg, sess, num]:
                exists = True
                break
        if not exists:
            data.append(newrow)
            # print newrow

    return data


def get_gov_dataset():
    data = csv.reader(open(GOV_DATASET_FILE, 'r'))
    # skip first row
    data.next()
    return list(data)


def get_mp_dataset():
    data = json.loads(open(MP_DATASET_FILE, 'r').read())
    info_data = csv.reader(open(MPINFO_DATASET_FILE, 'r'))
    info_data.next()
    for row in info_data:
        mp = data[row[0]]
        mp['email'] = row[3]
        mp['wikipedia_url'] = row[4]
        mp['twitter_url'] = row[6]
        mp['blog_url'] = row[7]
        mp['website_url'] = row[8]
    return data


def get_govpost_dataset():
    data = csv.reader(open(GOVPOST_DATASET_FILE, 'r'))
    # skip first row
    data.next()
    return list(data)


def replace_letters(s, letters, l):
    for letter in letters:
        s = s.replace(letter, l)
    return s


def slugify(s):
    s = s.strip()
    s = s.lower()
    s = s.replace("-", "")
    s = s.replace(" ", "-")
    s = s.replace("'", "-")
    s = replace_letters(s, u"áàâã", u"a")
    s = replace_letters(s, u"éèê", u"e")
    s = replace_letters(s, u"íì", u"i")
    s = replace_letters(s, u"óòôõ", u"o")
    s = replace_letters(s, u"úù", u"u")
    s = replace_letters(s, u"ç", u"c")
    return s


def to_list(s):
    l = s.split(';')
    new_l = []
    for item in l:
        item = item.strip(' "')
        if item:
            new_l.append(item)
    return new_l


def generate_datedict():
    # process dates into a year->dates dict
    datedict = OrderedDict()
    data = get_date_dataset()
    all_dates = [dateparser.parse(row[3]) for row in data]
    all_years = list(set([d.year for d in all_dates]))
    for year in all_years:
        # populate it with its months
        # if current year, trim future months
        if int(year) == datetime.date.today().year:
            month = datetime.date.today().month
            months = range(1, month + 1)
        else:
            months = range(1, 13)
        datedict[year] = {}
        for month in months:
            datedict[year][month] = {}
            import calendar
            days_in_month = calendar.monthrange(year, month)[-1]
            all_days = range(1, days_in_month + 1)
            session_days = [datetime.date(d.year, d.month, d.day) for d in all_dates
                            if d.month == month and d.year == year]
            for day_number in all_days:
                day_date = datetime.date(year, month, day_number)
                if day_date in session_days:
                    has_session = True
                else:
                    has_session = False
                datedict[year][month][day_number] = {'weekday': day_date.weekday(),
                                                     'has_session': has_session}
    return datedict


def generate_mp_list(only_active=True):
    mps = []
    data = get_mp_dataset()
    for id in data:
        mp = data[id]
        if only_active and not mp['active']:
            continue
        mp['slug'] = slugify(mp['shortname'])
        if 'occupation' in mp and len(mp['occupation']) == 1:
            mp['occupation'] = mp['occupation'][0]
        mps.append(mp)
    return mps


def render_template_into_file(env, templatename, filename, context=None, place_in_outdir=True):
    target_dir = os.path.join(OUTPUT_DIR, os.path.dirname(filename))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    template = env.get_template(templatename)
    if not context:
        context = {}
    html = template.render(**context)
    if place_in_outdir:
        filename = os.path.join(OUTPUT_DIR, filename)
    outfile = codecs.open(filename, 'w', 'utf-8')
    outfile.write(html)
    outfile.close()


def get_session_text(leg, sess, num, html=True):
    if 'S' in num:
        sourcefile = "%02d-%d-%s.txt" % (int(leg), int(sess), num)
    else:
        sourcefile = "%02d-%d-%03d.txt" % (int(leg), int(sess), int(num))
    sourcepath = os.path.join(TRANSCRIPTS_DIR, sourcefile)
    text = codecs.open(sourcepath, 'r', 'utf-8').read()
    if html:
        entries = text.split('\n\n')
        newentries = []
        for e in entries:
            # adicionar linebreak extra para dividir parágrafos
            newentries.append(e.replace('\n', '\n\n'))
        newtext = "\n\n".join(newentries)
        newhtml = mistune.markdown(newtext)
        return newhtml.replace("_", "")
    else:
        return text


def delete_and_create_dir(d):
    """Deletes a directory if it exists, and creates a new one with the
    same name."""
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)


def create_dir(d):
    """Deletes a directory if it exists, and creates a new one with the
    same name."""
    if not os.path.exists(d):
        os.makedirs(d)


def format_date(value, format='medium'):
    if type(value) not in (datetime.date, datetime.datetime):
        log.error(type(value))
        value = dateparser.parse(value)
    return babel_format_date(value, format, locale="pt_PT")


@click.option("-f", "--fast-run", help="Generate only a few transcripts to save time", is_flag=True, default=False)
@click.command()
def generate_site(fast_run):
    # flush output
    create_dir(OUTPUT_DIR)
    create_dir(os.path.join(OUTPUT_DIR, TRANSCRIPTS_PATH))
    create_dir(os.path.join(OUTPUT_DIR, MPS_PATH))
    create_dir(os.path.join(OUTPUT_DIR, MEDIA_PATH))

    # init Jinja
    env = jinja2.Environment(loader=jinja2.FileSystemLoader([TEMPLATE_DIR]),
                             extensions=['jinja2htmlcompress.SelectiveHTMLCompress'],
                             trim_blocks=True, lstrip_blocks=True)
    env.filters['date'] = format_date

    # generate pages
    log.info("Copying static files...")
    copy_tree(MEDIA_SOURCE_DIR, os.path.join(OUTPUT_DIR, MEDIA_PATH))

    log.info("Generating index...")
    render_template_into_file(env, 'index.html', 'index.html')

    log.info("Generating MP index...")
    mps = generate_mp_list()
    context = {"mps": mps}
    render_template_into_file(env, 'mp_list.html', "deputados/index.html", context)

    gov_data = get_gov_dataset()
    govpost_data = list(get_govpost_dataset())
    gov_mp_ids = [int(row[2]) for row in govpost_data if row[2]]
    date_data = get_date_dataset()

    log.info("Generating MP pages...")
    for mp in mps:
        id = int(mp['id'])
        mp['photo_url'] = PHOTO_URL_BASE + str(id) + ".jpg"
        # determine government posts
        if id in gov_mp_ids:
            mp['govposts'] = []
            govpost_rows = [row for row in govpost_data if row[2].strip() and int(row[2]) == id]
            for row in govpost_rows:
                gov_number = int(row[0])
                gov = None
                for r in gov_data:
                    if int(r[0]) == gov_number:
                        gov = {'number': r[0], 'start_date': dateparser.parse(r[1]), 'end_date': dateparser.parse(r[2])}
                        break
                if not gov:
                    log.critical("Gov not found!")
                mp['govposts'].append({
                    'post': row[3],
                    'start_date': dateparser.parse(row[4]),
                    'end_date': dateparser.parse(row[5]),
                    'gov': gov,
                })
        # parse dates
        for m in mp['mandates']:
            m['start_date'] = dateparser.parse(m['start_date'])
            m['end_date'] = dateparser.parse(m['end_date'])
            # nice effect: if no end date, set to today

        context = {'mp': mp, 'l': None}
        filename = os.path.join(MPS_PATH, mp['slug'], 'index.html')
        render_template_into_file(env, 'mp_detail.html', filename, context)

    log.info("Generating session index...")
    datedict = generate_datedict()
    all_years = [y for y in datedict]
    for year_number in datedict:
        year = datedict[year_number]
        context = {'year': year,
                   'year_number': year_number,
                   'all_years': all_years,
                   'datedict': datedict,
                   }
        target_dir = os.path.join(TRANSCRIPTS_PATH + "%s/" % year_number)
        filename = target_dir + "index.html"
        # print filename
        render_template_into_file(env, 'day_list.html', filename, context)

    # get most recent year and make the session index
    y = all_years[-1]
    year = datedict[y]
    context = {'year': year,
               'year_number': year_number,
               'all_years': all_years,
               'datedict': datedict,
               }
    render_template_into_file(env, 'day_list.html', TRANSCRIPTS_PATH + 'index.html', context)

    log.info("Generating HTML session pages...")
    if fast_run:
        COUNTER = 0
    date_data.reverse()
    for leg, sess, num, d, dpub, page_start, page_end in date_data:
        dateobj = dateparser.parse(d)
        context = {'session_date': dateobj,
                   'year_number': year_number,
                   'text': get_session_text(leg, sess, num),
                   'monthnames': MESES,
                   'pdf_url': 'xpto',
                   }
        target_dir = "%s%d/%02d/%02d" % (TRANSCRIPTS_PATH, dateobj.year, dateobj.month, dateobj.day)
        if not os.path.exists(os.path.join(OUTPUT_DIR, target_dir)):
            create_dir(os.path.join(OUTPUT_DIR, target_dir))
        filename = "%s/index.html" % target_dir
        render_template_into_file(env, 'day_detail.html', filename, context)
        log.debug(d)
        if fast_run:
            COUNTER += 1
            if COUNTER > 20:
                break


if __name__ == "__main__":
    generate_site()
