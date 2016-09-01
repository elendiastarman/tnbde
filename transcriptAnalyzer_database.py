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
        self.divNest = 0
        self.names = {}
        self.messages = {}
        
        self.debug = kwargs['debug'] if 'debug' in kwargs else 0
        if self.debug: print("Debug on.")

    def handle_starttag(self, tag, attrs):
        if self.state == "content":
            if tag != "div":
                self.currMess["content"] += "<%s %s>" % (tag, ' '.join('%s="%s"' % attr for attr in attrs))
            else:
                self.currMess["onebox"] = attrs[0][1][10:] #takes out 'onebox ob-'
                self.state = "onebox"

        elif self.state == "onebox":
            if tag == "div": self.divNest += 1
            self.currMess["content"] += "<{0} {1}>".format(tag, ' '.join('%s="%s"'%attr for attr in attrs))

        elif tag in ("div","a"):
            if 1 and self.debug:
                print("tag, attrs:",tag,attrs)

            if len(attrs) == 0 or attrs[0][0] != "class": return

            if attrs[0][1].startswith("monologue"):
                uid = attrs[0][1][15:].rstrip(" mine")
                self.currUser = int(uid) if uid else None
                if uid not in self.names:
                    self.state = "need name"
                
            elif attrs[0][1] == "message":
                mid = int(attrs[1][1].split('-')[1])
                self.messages[mid] = {'uid':self.currUser,
                                      'rid':None,
                                      'name':self.names[self.currUser],
                                      'stars':0,
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
                self.divNest = 0

            elif attrs[0][1] == "timestamp":
                self.state = "get time"

        elif tag == "span" and len(attrs) and attrs[0][0] == 'class' and 'stars' in attrs[0][1]:
            self.state = "has stars"

        elif self.state == "has stars" and tag == "span" and len(attrs) and attrs[0] == ('class','times'):
            self.state = "get stars"

    def handle_endtag(self, tag):
        if self.state == "content":
            if tag == "div":
                if self.divNest == 0:
                    self.state = ""
                    self.currMess["content"] = self.currMess["content"][:-40]
                else:
                    self.divNest -= 1

                    if self.divNest > 0:
                        self.currMess["content"] += "</div>"
            else:
                self.currMess["content"] += "</%s>"%tag

        elif self.state == "onebox":
            if tag == "div":
                if self.divNest == 0:
                    self.state = ""
                else:
                    self.divNest -= 1

                if self.divNest > 0:
                    self.currMess["content"] += "</div>"
            else:
                self.currMess["content"] += "</%s>"%tag

    def handle_data(self, data):
        if self.state == "content":
            if 1 and self.debug: print("  data:",data)
            
            if self.currMess["content"]:
                self.currMess["content"] += data
            else:
                self.currMess["content"] = data[22:]

        elif self.state == "onebox":
            self.currMess["content"] += data

        elif self.state == "get name":
            self.state = ""
            if not self.currUser: self.currUser = int(data.strip()[4:])
            self.names[self.currUser] = data.strip()

        elif self.state == "get time":
            self.state = ""
            self.timestamp = data.strip()

        elif self.state == "get stars":
            self.state = ""
            data = data.strip()
            self.currMess['stars'] = int(data) if data else 1

class orderedList(list):
    def __init__(self, L):
        self.items = list(sorted(L))
    
    def __contains__(self, item):
        low = 0
        high = len(self.items)-1

        if high == -1:
            return False
        elif high == 0:
            return self.items[0] == item
        
        while high - low > 1:
            mid = (low+high)//2

            if self.items[mid] == item:
                return True
            elif self.items[mid] < item:
                low = mid
            else:
                high = mid

        return self.items[low] == item or self.items[high] == item

def parseConvos(roomNum=240, year=2016, month=3, day=23, hourStart=0, hourEnd=4, debug=0, log=0):
    urlTemp = "http://chat.stackexchange.com/transcript/"+"{}/"*4+"{}-{}"
    url = urlTemp.format(*[roomNum, year, month, day, hourStart, hourEnd])

    if debug & 2: print(url)

    text = ur.urlopen(url).read().decode('utf-8')

    p = parser(debug=debug & 1)
    p.feed(text)

    users = {}
    messNum = 0
    messagesToCreate = []

    msgsInDB = Message.objects.filter(mid__in=p.messages.keys())
    midsInDB = [m.mid for m in msgsInDB]

    for mid, message in p.messages.items():
        if debug & 2: print("messNum, mid: %s, %s" % (messNum, mid))
        messNum += 1
        
        uid = message['uid']
        rid = message['rid']
        name = message['name']
        stars = message['stars']
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
            if mid not in midsInDB: raise ObjectDoesNotExist
            
            message = Message.objects.get(mid=mid)
            
            if message.content != content or message.name != name or message.stars != stars:
                message.rid = rid
                message.name = name
                message.stars = stars
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
            message.name = name
            message.stars = stars
            message.content = content
            message.onebox = bool(onebox)
            message.oneboxType = onebox
            
            messagesToCreate.append(message)

    Message.objects.bulk_create(messagesToCreate)

def parseDays(start, end=datetime.datetime.now()):
    while start <= end:
        parseConvos(240, start.year, start.month, start.day, start.hour, start.hour+1)
        print(start)
        start += datetime.timedelta(1/24)
