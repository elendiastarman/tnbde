from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist

# from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt

from transcriptAnalyzer.models import Query, Inquiry

# import os
import sys
import html
import json
# import time
# import string
# import random
import hashlib
import psycopg2
# from subprocess import call


# Create your views here.
def TNBDE_view(request, **kwargs):
    context = {}

    context['sql'] = """SELECT *\n\nFROM "transcriptAnalyzer_message"\n\nORDER BY mid DESC\n\nLIMIT 10;"""
    context['js'] = ''
    context['error'] = ''

    inquiry = None
    code = kwargs.get('code', None)
    if code:
        # try:
        #     pathpref = "/home/elendia/webapps/ppcg/PPCG/" if sys.platform == 'linux' else ""
        #     filepath = os.path.join(pathpref+"transcriptAnalyzer","queries",kwargs["code"])
        #     context["sql"] = open(filepath+"In.txt", 'r', encoding='utf-8').read()[31:]
        #     context["js"] = open(filepath+"JS.txt", 'r', encoding='utf-8').read()
        # except FileNotFoundError as e:
        #     context["error"] = True
        try:
            inquiry = Inquiry.get(shortcode=code)
            context['js'] = inquiry.js
        except ObjectDoesNotExist:
            context['error'] = "That code doesn't exist."

    if inquiry:
        try:
            query = Query.get(id=inquiry.query)
            context['sql'] = query.sql
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


@csrf_exempt
def runcode(request, **kwargs):
    # context = RequestContext(request)

    # filename = ''.join(random.choice(string.ascii_letters) for _ in range(10))
    # pathpref = "/home/elendia/webapps/ppcg/PPCG/" if sys.platform == 'linux' else ""
    # filepath = os.path.join(pathpref+"transcriptAnalyzer","queries",filename)

    # f = open(filepath + "In.txt", 'w', encoding='utf-8')
    # querystring = 'SET statement_timeout TO 10000;\n' + request.POST['query']
    # f.write(querystring)
    # f.close()

    # f = open(filepath + "JS.txt", 'w', encoding='utf-8')
    # f.write(request.POST['javascript'])
    # f.close()
    querystring = 'SET statement_timeout TO 10000;\n' + request.POST['query']

    sha1 = hashlib.sha1(bytes(querystring, encoding='utf-8'))
    try:
        query = Query.get(sha1=sha1)
        if query.response:
            return HttpResponse(query.response, content_type="text/json")
    except ObjectDoesNotExist:
        query = Query(sha1=sha1, sql=querystring)

    data = {'error': "", 'results_html': "", 'results_json': ""}

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
        htmlstr = "<table border='1' class='sortable' id='query-table'><tr>{}</tr>".format(''.join('<th>{}</th>' % header for header in headers))
        jsonlist = []

        for row in results:
            htmlstr += "<tr>"

            for i, val in enumerate(row):
                if headers[i] == "mid":
                    midurl = "http://chat.stackexchange.com/transcript/message/{}#{}".format(val, val)
                    htmlstr += "<td><a href=\"{}\">{}</a></td>".format(midurl, val)
                elif headers[i] == "uid":
                    uidurl = "http://chat.stackexchange.com/users/{}" % val
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

    return HttpResponse(response, content_type="text/json")
