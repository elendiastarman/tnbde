from django.conf.urls import url, include
from django.views.decorators.csrf import csrf_exempt

from transcriptAnalyzer.views import *

urlpatterns = [
##    url(r'^$', TNBDE_view),
    url(r'^runcode$', runcode),
    url(r'^usefulqueries$', TNBDE_usefulqueries_view, name='usefulqueries'),
    url(r'^tnbde/fetch/(?P<code>\w*)$', lambda *args,**kwargs: TNBDE_view(*args, fetch=True, **kwargs), name="tnbde-permalink"),
    url(r'^tnbde/', TNBDE_view),
    url(r'^(?P<code>\w*)$', TNBDE_view),
]
