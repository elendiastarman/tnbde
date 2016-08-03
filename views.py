from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from django.template import Context, RequestContext, TemplateDoesNotExist
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie

import os
import sys
import time
import string
import random
from subprocess import call

# Create your views here.
##@ensure_csrf_cookie
def TNBDE_view(request, **kwargs):
    context = RequestContext(request)

    print(kwargs["code"] if "code" in kwargs else "(no code)")

    context["sql"] = "SELECT content FROM \"transcriptAnalyzer_message\" WHERE onebox = FALSE AND date = '2016-07-27';"
    context["js"] = ""
    context["error"] = False

    if "code" in kwargs:
        try:
            filepath = os.path.join("transcriptAnalyzer","queries",kwargs["code"])
            context["sql"] = open(filepath+"In.txt", 'r', encoding='utf-8').read()[31:]
            context["js"] = open(filepath+"JS.txt", 'r', encoding='utf-8').read()
        except FileNotFoundError as e:
            context["error"] = True

    return render(request, 'PPCG/TNBDE.html', context_instance=context)

@csrf_exempt
def runcode(request, **kwargs):
    context = RequestContext(request)

    filename = ''.join(random.choice(string.ascii_letters) for _ in range(10))
    filepath = os.path.join("transcriptAnalyzer","queries",filename)

    f = open(filepath + "In.txt", 'w', encoding='utf-8')
    f.write('SET statement_timeout TO 1000;\n' + request.POST['query'])
    f.close()

    f = open(filepath + "JS.txt", 'w', encoding='utf-8')
    f.write(request.POST['javascript'])
    f.close()

    if sys.platform == 'win32':
        pathtopsql = r"C:\Program Files\PostgreSQL\9.4\bin\psql"
    elif sys.platform == 'linux':
        pathtopsql = r""

    command = [pathtopsql, "--html", "-U", "TAAnon", "PPCG_transcript",
               "<",  filepath + "In.txt",
               ">",  filepath + "Out.txt",
               "2>", filepath + "Err.txt"]
    exitCode = call(command, shell=True)#, env={'PATH': os.getenv('PATH')})
    print("exitCode:",exitCode)
    time.sleep(1)

    result = open(filepath + "Out.txt", 'r', encoding='utf-8').read()
    result_err = open(filepath + "Err.txt", 'r', encoding='utf-8').read()

    return HttpResponse(filename + result[11:] if not result_err else result_err, content_type="text/utf8")
