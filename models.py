from django.db import models

# Create your models here.
class User(models.Model):
    uid = models.IntegerField()

class Username(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField(max_length=200)

class Message(models.Model):
    user = models.ForeignKey(User)
    mid = models.IntegerField() #message id
    rid = models.IntegerField(null=True,blank=True) #reply id

    room = models.IntegerField()
    date = models.DateField()
    time = models.TimeField(null=True,blank=True)

    content = models.TextField()
    name = models.CharField(max_length=200, null=True,blank=True)
    stars = models.IntegerField(default=0)
    onebox = models.BooleanField(default=False)
    oneboxType = models.CharField(max_length=30)
