from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt

from transcriptAnalyzer.models import Query, Inquiry

import re
import sys
import html
import json
import string
import random
import hashlib
import psycopg2
import traceback


# Create your views here.
def TNBDE_view(request, **kwargs):
    context = {}

    context['sql'] = """SELECT *\n\nFROM "transcriptAnalyzer_message"\n\nORDER BY mid DESC\n\nLIMIT 10;"""
    context['js'] = ''
    context['error'] = ''

    inquiry = None
    code = kwargs.get('code', None)
    if code:
        try:
            inquiry = Inquiry.objects.get(shortcode=code)
            context['js'] = inquiry.js
        except ObjectDoesNotExist:
            context['error'] = "That code doesn't exist."

    if inquiry:
        try:
            query = Query.objects.get(id=inquiry.query.id)
            context['sql'] = query.sql[31:]
        except ObjectDoesNotExist:
            context['error'] = "Something borked really bad. Find El'endia and give him this link."

    if 'fetch' in kwargs:
        return HttpResponse(json.dumps(context), content_type='text/json')
    else:
        return render(request, 'transcriptAnalyzer/TNBDE.html', context=context)


def TNBDE_usefulqueries_view(request, **kwargs):
    return render(request, 'transcriptAnalyzer/TNBDE_usefulqueries.html')


def TNBDE_oldpermalink(request, **kwargs):
    return HttpResponseRedirect(reverse('tnbde-permalink', args=(kwargs['code'],)))


def output_clean_error(exc_info):
    error = '\n'.join(traceback.format_exception(*exc_info))

    error = re.sub('File "/.*?(?=/.*?\.py")', 'File "', error)

    return error


@csrf_exempt
def runcode(request, **kwargs):
    try:
        return _runcode(request, **kwargs)
    except:
        error = output_clean_error(sys.exc_info())

        print(error, file=sys.stderr)  # noqa  # (because flake8 in Sublime is dumb)

        return HttpResponse(json.dumps({'error': error}), content_type="text/json")


def _runcode(request, **kwargs):
    querystring = 'SET statement_timeout TO 10000;\n' + request.POST['query']

    sha1 = hashlib.sha1(bytes(querystring, encoding='utf-8')).hexdigest()
    try:
        query = Query.objects.get(sha1=sha1)
    except ObjectDoesNotExist:
        query = Query(sha1=sha1, sql=querystring)

    js_sha1 = hashlib.sha1(bytes(request.POST['javascript'], encoding='utf-8')).hexdigest()
    try:
        inquiry = Inquiry.objects.get(query=query.id, sha1=js_sha1)
        shortcode = inquiry.shortcode
    except ObjectDoesNotExist:
        shortcode = ''.join(random.choice(string.ascii_letters) for _ in range(10))
        inquiry = Inquiry(sha1=js_sha1, shortcode=shortcode, js=request.POST['javascript'])

    if query.response:
        response = query.response

    else:
        data = {'error': "", 'results_html': "", 'results_json': ""}

        con = psycopg2.connect(database="ppcg_transcript",
                               user="taanon",
                               password="foobar",
                               host="127.0.0.1",
                               port="5432" if sys.platform in ["win32", "darwin"] else "30192")
        cur = con.cursor()
        error = ""

        try:
            cur.execute(querystring)
            results = cur.fetchall()
        except (psycopg2.ProgrammingError, psycopg2.extensions.QueryCanceledError, psycopg2.DataError):
            con.rollback()
            error = output_clean_error(sys.exc_info())
        except (psycopg2.DatabaseError, psycopg2.InterfaceError):
            error = output_clean_error(sys.exc_info())

        if error:
            data["error"] = error
        else:
            headers = [column.name for column in cur.description]
            htmlstr = "<table border='1' class='sortable' id='query-table'><tr>{}</tr>".format(''.join('<th>{}</th>'.format(header) for header in headers))
            jsonlist = []

            for row in results:
                htmlstr += "<tr>"

                for i, val in enumerate(row):
                    if headers[i] == "mid":
                        midurl = "http://chat.stackexchange.com/transcript/message/{}#{}".format(val, val)
                        htmlstr += "<td><a href=\"{}\">{}</a></td>".format(midurl, val)
                    elif headers[i] == "uid":
                        uidurl = "http://chat.stackexchange.com/users/{}".format(val)
                        htmlstr += "<td><a href=\"{}\">{}</a></td>".format(uidurl, val)
                    elif headers[i] == "content_rendered":
                        htmlstr += "<td>{}</td>".format(val)
                    else:
                        htmlstr += "<td>{}</td>".format(html.escape(str(val)))

                htmlstr += "</tr>"

                jsonlist.append({key: str(val) for key, val in zip(headers, row)})

            htmlstr += "</table>"

            data["results_html"] = htmlstr
            data["results_json"] = json.dumps(jsonlist)

        con.close()

        response = json.dumps(data)
        query.response = response

    query.save()

    inquiry.query = query
    inquiry.save()

    response = "{}, \"shortcode\": \"{}\"}}".format(response[:-1], shortcode)
    return HttpResponse(response, content_type="text/json")
