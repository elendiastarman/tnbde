import urllib.request as ur
import html.parser as hp
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

import datetime

from transcriptAnalyzer.models import *

class parser(hp.HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.numTags = 0
        self.numText = 0
        self.state = ""
        self.timestamp = None
        self.names = {}
        self.messages = {}
        
        self.debug = kwargs['debug'] if 'debug' in kwargs else 0
        if self.debug: print("Debug on.")

    def handle_starttag(self, tag, attrs):
        if self.state == "content":
            if tag != "div":
                self.currMess["content"] += "<%s>"%tag
            else:
                self.currMess["onebox"] = attrs[0][1][10:] #takes out 'onebox ob-'
                self.state = "onebox"

        elif self.state == "onebox":
            self.currMess["content"] += "<{0} {1}>".format(tag, ' '.join('%s="%s"'%attr for attr in attrs))

        elif tag in ("div","a"):
            self.numTags += 1

            if 1 and self.debug:
                print("tag:",tag)
                print("attrs:",attrs)

            if len(attrs) == 0 or attrs[0][0] != "class": return

            if attrs[0][1].startswith("monologue"):
                uid = int(attrs[0][1][15:].rstrip(" mine"))
                self.currUser = uid
                if uid not in self.names:
                    self.state = "need name"
                
            elif attrs[0][1] == "message":
                mid = int(attrs[1][1].split('-')[1])
                self.messages[mid] = {'uid':self.currUser,
                                      'rid':None,
                                      'name':self.names[self.currUser],
                                      'onebox':"",
                                      'content':"",
                                      'timestamp':self.timestamp}
                
                self.currMess = self.messages[mid]

            elif attrs[0][1] == "reply-info":
                rid = int(attrs[1][1].split('#')[1])
                self.currMess["rid"] = rid

            elif attrs[0][1] == "username" and self.state == "need name":
                self.state = "get name"

            elif attrs[0][1] == "content":
                self.state = "content"

            elif attrs[0][1] == "timestamp":
                self.state = "get time"

    def handle_endtag(self, tag):
        if self.state == "content":
            if tag == "div":
                self.state = ""
                self.currMess["content"] = self.currMess["content"][:-40]
            else:
                self.currMess["content"] += "</%s>"%tag

        elif self.state == "onebox":
            if tag == "div":
                self.state = ""
            else:
                self.currMess["content"] += "</%s>"%tag

    def handle_data(self, data):
        if self.state == "content":
            if 1 and self.debug: print("  data:",data)
            
            self.numText += 1
            if self.currMess["content"]:
                self.currMess["content"] += data
            else:
                self.currMess["content"] = data[22:]

        elif self.state == "onebox":
            self.currMess["content"] += data

        elif self.state == "get name":
            self.state = ""
            self.names[self.currUser] = data.strip()

        elif self.state == "get time":
            self.state = ""
            self.timestamp = data.strip()

def parseConvos(roomNum=240, year=2016, month=3, day=23, hourStart=0, hourEnd=4, debug=0):
    urlTemp = "http://chat.stackexchange.com/transcript/"+"{}/"*4+"{}-{}"
    url = urlTemp.format(*[roomNum, year, month, day, hourStart, hourEnd])

    print(url)

    text = ur.urlopen(url).read().decode('utf-8')

    p = parser(debug=debug)
    p.feed(text)

    users = {}
    messNum = 0
    messagesToCreate = []

    for mid, message in p.messages.items():
        print("messNum, mid: %s, %s" % (messNum, mid))
        messNum += 1
##        print(mid, message)
        
        uid = message['uid']
        rid = message['rid']
        name = message['name']
        onebox = message['onebox']
        content = message['content']
        timestamp = message['timestamp']

        if uid not in users:
            try:
                user = User.objects.get(uid=uid)
            except ObjectDoesNotExist:
                user = User(uid=uid)
                user.save()
            
            users[uid] = {'user':user, 'names':[]}
            names = users[uid]['names']
        else:
            user = users[uid]['user']
            names = users[uid]['names']
        
        if name not in names:
            try:
                username = Username.objects.get(user=user, name=name)
            except ObjectDoesNotExist:
                username = Username(name=name, user=user)
                username.save()
            
            names.append(name)
        else:
            pass

        try:
            message = Message.objects.get(mid=mid)
            
            if message.content != content:
                message.rid = rid
                message.content = content
                message.onebox = bool(onebox)
                message.oneboxType = onebox

                message.save()

        except ObjectDoesNotExist:
            date = datetime.date(year, month, day)
            
            hourmin, half = timestamp.split(" ")
            hour, minute = hourmin.split(":")
            hour = int(hour)%12 + 12*(half=="PM")
            minute = int(minute)
            time = datetime.time(hour, minute)
            
            message = Message(mid=mid, user=user, room=roomNum, date=date, time=time)
            message.rid = rid
            message.content = content
            message.onebox = bool(onebox)
            message.oneboxType = onebox
            
            messagesToCreate.append(message)

    Message.objects.bulk_create(messagesToCreate)
