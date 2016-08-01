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

    return render(request, 'PPCG/TNBDE.html', context_instance=context)

@csrf_exempt
def runcode(request, **kwargs):
    context = RequestContext(request)

    filename = ''.join(random.choice(string.ascii_letters) for _ in range(10))
    filein = filename+'In.txt'
    fileout = filename+'Out.txt'
    fileerr = filename+'Err.txt'
    filepathin = os.path.join("transcriptAnalyzer","queries",filein)
    filepathout = os.path.join("transcriptAnalyzer","queries",fileout)
    filepatherr = os.path.join("transcriptAnalyzer","queries",fileerr)

    f = open(filepathin, 'w', encoding='utf-8')
    f.write('SET statement_timeout TO 1000;\n' + request.POST['query'])
    f.close()

    if sys.platform == 'win32':
        pathtopsql = r"C:\Program Files\PostgreSQL\9.4\bin\psql"
    elif sys.platform == 'linux':
        pathtopsql = r""

    command = [pathtopsql, "--html", "-U", "TAAnon", "PPCG_transcript", "<", filepathin, ">", filepathout, "2>", filepatherr]
    exitCode = call(command, shell=True)#, env={'PATH': os.getenv('PATH')})
    print("exitCode:",exitCode)
    time.sleep(1)

    result = open(filepathout, 'r', encoding='utf-8').read()
    result_err = open(filepatherr, 'r', encoding='utf-8').read()

    return HttpResponse(result[11:] if not result_err else result_err, content_type="text/utf8")
