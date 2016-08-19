from django.conf.urls import url, include
from django.views.decorators.csrf import csrf_exempt

from transcriptAnalyzer.views import *

urlpatterns = [
    url(r'^$', TNBDE_view),
    url(r'^runcode$', runcode),
    url(r'^usefulqueries$', TNBDE_usefulqueries_view),
    url(r'^(?P<code>\w*)$', TNBDE_view),
]
