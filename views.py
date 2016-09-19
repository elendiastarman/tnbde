from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from django.template import Context, RequestContext, TemplateDoesNotExist
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

import os
import sys
import html
import json
import time
import string
import random
import psycopg2
from subprocess import call

# Create your views here.
def TNBDE_view(request, **kwargs):
    context = {}#RequestContext(request)

    context["sql"] = """SELECT *

FROM "transcriptAnalyzer_message"

ORDER BY mid DESC

LIMIT 10;"""
    context["js"] = ""
    context["error"] = False

    if "code" in kwargs:
        try:
            pathpref = "/home/elendia/webapps/ppcg/PPCG/" if sys.platform == 'linux' else ""
            filepath = os.path.join(pathpref+"transcriptAnalyzer","queries",kwargs["code"])
            context["sql"] = open(filepath+"In.txt", 'r', encoding='utf-8').read()[32:]
            context["js"] = open(filepath+"JS.txt", 'r', encoding='utf-8').read()
        except FileNotFoundError as e:
            context["error"] = True

    if "fetch" in kwargs:
        return HttpResponse(json.dumps(context), content_type="text/json")
    else:
        return render(request, 'transcriptAnalyzer/TNBDE.html', context=context)

def TNBDE_usefulqueries_view(request, **kwargs):
    return render(request, 'transcriptAnalyzer/TNBDE_usefulqueries.html')

def TNBDE_oldpermalink(request, **kwargs):
    return HttpResponseRedirect(reverse('tnbde-permalink', args=(kwargs['code'],)))

@csrf_exempt
def runcode(request, **kwargs):
    context = RequestContext(request)

    filename = ''.join(random.choice(string.ascii_letters) for _ in range(10))
    pathpref = "/home/elendia/webapps/ppcg/PPCG/" if sys.platform == 'linux' else ""
    filepath = os.path.join(pathpref+"transcriptAnalyzer","queries",filename)

    f = open(filepath + "In.txt", 'w', encoding='utf-8')
    querystring = 'SET statement_timeout TO 10000;\n' + request.POST['query']
    f.write(querystring)
    f.close()

    f = open(filepath + "JS.txt", 'w', encoding='utf-8')
    f.write(request.POST['javascript'])
    f.close()

    data = {}
    data['filename'] = filename
    data['error'] = ""
    data['results_html'] = ""
    data['results_json'] = ""

    con = psycopg2.connect(database="ppcg_transcript",
                           user="taanon",
                           password="foobar",
                           host="127.0.0.1",
                           port="5432" if sys.platform == "win32" else "20526")
    cur = con.cursor()
    error = ""

    try:
        cur.execute(querystring)
    except (psycopg2.ProgrammingError, psycopg2.extensions.QueryCanceledError, psycopg2.DataError) as e:
        con.rollback()
        error = str(e)

    if error:
        data["error"] = error
    else:
        results = cur.fetchall()
        headers = [column.name for column in cur.description]
        htmlstr = "<table border='1' class='sortable' id='query-table'><tr>%s</tr>" % ''.join('<th>%s</th>' % header for header in headers)
        jsonlist = []

        for row in results:
            htmlstr += "<tr>"

            for i,val in enumerate(row):
                thingy = ""
                if headers[i] == "mid":
                    midurl = "http://chat.stackexchange.com/transcript/message/%s#%s" % (val, val)
                    htmlstr += "<td><a href=\"%s\">%s</a></td>" % (midurl, val)
                elif headers[i] == "uid":
                    uidurl = "http://chat.stackexchange.com/users/%s" % val
                    htmlstr += "<td><a href=\"%s\">%s</a></td>" % (uidurl, val)
                elif headers[i] == "content_rendered":
                    htmlstr += "<td>%s</td>" % val
                else:
                    htmlstr += "<td>%s</td>" % html.escape(str(val))

            htmlstr += "</tr>"
            
            jsonlist.append({key:str(val) for key,val in zip(headers, row)})

        htmlstr += "</table>"

        data["results_html"] = htmlstr
        data["results_json"] = json.dumps(jsonlist)

    con.close()

    return HttpResponse(json.dumps(data), content_type="text/json")
