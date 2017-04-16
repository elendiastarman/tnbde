from django.db import models


# Create your models here.
class User(models.Model):
    uid = models.IntegerField()
    latest_name = models.CharField(max_length=200)
    latest_msg = models.IntegerField()


class Username(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField(max_length=200)


class Message(models.Model):
    user = models.ForeignKey(User)
    mid = models.IntegerField()  # message id
    rid = models.IntegerField(null=True, blank=True)  # reply id

    room = models.IntegerField()
    date = models.DateField()
    time = models.TimeField()

    content = models.TextField()
    markdown = models.TextField()
    name = models.CharField(max_length=200)
    stars = models.IntegerField(default=0)
    onebox = models.BooleanField(default=False)
    onebox_type = models.CharField(max_length=30)
    was_edited = models.BooleanField(default=False)


class Query(models.Model):
    sql = models.TextField()
    response = models.TextField(null=True, blank=True)
    sha1 = models.CharField(max_length=40)


class Inquiry(models.Model):
    shortcode = models.CharField(max_length=10)
    query = models.ForeignKey(Query)
    js = models.TextField()
    sha1 = models.CharField(max_length=40)


class Snapshot(models.Model):
    date = models.DateField()
    sha1 = models.CharField(max_length=40)
