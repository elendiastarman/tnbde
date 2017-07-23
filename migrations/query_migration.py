import os
import time
import hashlib
from django.core.exceptions import ObjectDoesNotExist
from psycopg2 import DatabaseError as p_DatabaseError
from psycopg2 import OperationalError as p_OperationalError
from django.db.utils import DatabaseError as d_DatabaseError
from django.db.utils import OperationalError as d_OperationalError

from transcriptAnalyzer.models import *


def redo_wrapper(func, log=False):
    max_tries = 5
    for i in range(max_tries):
        try:
            return func()
            break
        except (p_DatabaseError, d_DatabaseError, p_OperationalError, d_OperationalError):
            if log:
                print("Database error occurred; sleeping for {} seconds".format(i * 15))
            time.sleep(i * 15)
    else:
        raise ValueError("Could not exeute database operation")


priority_shortcodes = [
  'krDvwXuwUM',
  'YXfvqIeotl',
  'IGJJVvHRnI',
  'VZOdgYpojL',
  'BsijBiYAmF',
  'omCMaCUlkb',
  'QxUDOTEwvS',
  'KJuwvvMMOW',
  'qaSoaIhVXH',
  'irDQgIBVPw',
  'ehGgvJlWtW',
  'KoQwNeJUCN',
  'QcDPJyLNpN',
  'tzLCUlCiFt',
  'NwFTGiVIbr',
  'bLwXopKIEF',
  'kKkdDWEOYf',
  'MHmNFBaRkd',
  'HAGmVhkRQW',
  'DzZhMIuleN',
  'GgqKtuDwML',
  'DkhJAtNFbD',
  'ubqCwbUPKL',
  'DwDiyHBpwq',
  'WqySdwSyvg',
  'ryMCSLHfVg',
  'ZMRKntOfDP',
  'PYCwHUXkFp',
  'kSuwAbCncb',
  'IwoKefzgmj',
  'HaORUEXfmM',
  'ZUPBauRTnO',
  'pmCNRinyrc',
  'ooFNGqZLvm',
  'GJKslGHNhf',
  'mtkmqSzFCA',
]

seen_codes = [inquiry.shortcode for inquiry in Inquiry.objects.all()]

print(os.getcwd())

for filename in os.listdir(os.path.join(os.getcwd(), 'queries')):
  print(filename)
  break

  shortcode = filename[:10]
  if shortcode not in seen_codes:
    with open("{}JS.txt".format(shortcode)) as js_file:
      js = js_file.read()
      js_sha1 = hashlib.sha1(bytes(js, encoding='utf-8')).hexdigest()

      try:
        inquiry = Inquiry.objects.get(sha1=js_sha1)

        if inquiry.shortcode != shortcode and shortcode in priority_shortcodes:
          inquiry.shortcode = shortcode
          inquiry.save()
          continue

      except ObjectDoesNotExist:
        inquiry = Inquiry(js=js, sha1=js_sha1)

        with open("{}In.txt".format(shortcode)) as sql_file:
          sql = sql_file.read()
          sql_sha1 = hashlib.sha1(bytes(sql, encoding='utf-8')).hexdigest()

          try:
            query = Query.objects.get(sha1=sql_sha1)
          except ObjectDoesNotExist:
            query = Query(sql=sql, sha1=sql_sha1)
            query.save()

        inquiry.query = query
        inquiry.save()
