import urllib.request as ur
import html.parser as hp
from django.core.exceptions import ObjectDoesNotExist
from threading import Thread

import re
import hashlib
import datetime

from transcriptAnalyzer.models import *


class Parser(hp.HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__()
        # self.numTags = 0
        # self.numText = 0
        self.state = ""
        # self.timestamp = None
        # self.divNest = 0
        self.names = {}
        self.messages = {}

        # self.debug = kwargs['debug'] if 'debug' in kwargs else 0
        self.debug = kwargs.get('debug', 0)
        if self.debug:
            print("Debug on.")

    def handle_starttag(self, tag, attrs):
        # if self.state == "content":
        #     if tag != "div":
        #         self.curr_mess["content"] += "<{} {}}>".format(tag, ' '.join('{}="{}"' % attr for attr in attrs))
        #     else:
        #         self.curr_mess["onebox"] = attrs[0][1][10:]  # takes out 'onebox ob-'
        #         self.state = "onebox"

        # elif self.state == "onebox":
        #     if tag == "div": self.divNest += 1
        #     self.curr_mess["content"] += "<{} {}>".format(tag, ' '.join('{}="{}"'%attr for attr in attrs))

        if tag in ("div", "a"):
            if 1 and self.debug:
                print("tag, attrs:", tag, attrs)

            if len(attrs) == 0 or attrs[0][0] != "class":
                return

            if attrs[0][1].startswith("monologue"):
                # uid = attrs[0][1][15:].rstrip(" mine")
                uid = re.search('(\d+)', attrs[0][1]).group()
                self.curr_user = int(uid) if uid else None
                if uid not in self.names:
                    self.state = "need name"

            elif attrs[0][1] == "message":
                mid = int(attrs[1][1].split('-')[1])
                self.messages[mid] = {'uid': self.curr_user,
                                      'rid': None,
                                      'name': self.names[self.curr_user],
                                      # 'onebox': "",
                                      # 'content': "",
                                      # 'timestamp': None,
                                      # 'was_edited': None,}
                                      'stars': 0}

                self.curr_mess = self.messages[mid]

            elif attrs[0][1] == "reply-info":
                rid = int(attrs[1][1].split('#')[1])
                self.curr_mess["rid"] = rid

            elif attrs[0][1] == "username" and self.state == "need name":
                self.state = "get name"

            # elif attrs[0][1] == "content":
            #     self.state = "content"
            #     self.divNest = 0

            # elif attrs[0][1] == "timestamp":
            #     self.state = "get time"

        elif tag == "span" and len(attrs) and attrs[0][0] == 'class' and 'stars' in attrs[0][1]:
            self.state = "has stars"

        elif self.state == "has stars" and tag == "span" and len(attrs) and attrs[0] == ('class', 'times'):
            self.state = "get stars"

    # def handle_endtag(self, tag):
    #     if self.state == "content":
    #         if tag == "div":
    #             if self.divNest == 0:
    #                 self.state = ""
    #                 self.curr_mess["content"] = self.curr_mess["content"][:-40]
    #             else:
    #                 self.divNest -= 1

    #                 if self.divNest > 0:
    #                     self.curr_mess["content"] += "</div>"
    #         else:
    #             self.curr_mess["content"] += "</{}>"%tag

    #     elif self.state == "onebox":
    #         if tag == "div":
    #             if self.divNest == 0:
    #                 self.state = ""
    #             else:
    #                 self.divNest -= 1

    #             if self.divNest > 0:
    #                 self.curr_mess["content"] += "</div>"
    #         else:
    #             self.curr_mess["content"] += "</{}>"%tag

    def handle_data(self, data):
        # if self.state == "content":
        #     if 1 and self.debug: print("  data:",data)

        #     if self.curr_mess["content"]:
        #         self.curr_mess["content"] += data
        #     else:
        #         self.curr_mess["content"] = data[22:]

        # elif self.state == "onebox":
        #     self.curr_mess["content"] += data

        if self.state == "get name":
            self.state = ""
            if not self.curr_user:
                self.curr_user = int(data.strip()[4:])
            self.names[self.curr_user] = data.strip()

        # elif self.state == "get time":
        #     self.state = ""
        #     self.timestamp = data.strip()

        elif self.state == "get stars":
            self.state = ""
            data = data.strip()
            self.curr_mess['stars'] = int(data) if data else 1

# class orderedList(list):
#     def __init__(self, L):
#         self.items = list(sorted(L))

#     def __contains__(self, item):
#         low = 0
#         high = len(self.items)-1

#         if high == -1:
#             return False
#         elif high == 0:
#             return self.items[0] == item

#         while high - low > 1:
#             mid = (low+high)//2

#             if self.items[mid] == item:
#                 return True
#             elif self.items[mid] < item:
#                 low = mid
#             else:
#                 high = mid

#         return self.items[low] == item or self.items[high] == item


def parse_convos(room_num=240, year=2016, month=3, day=23, hour_start=0, hour_end=4, debug=0, log=0):
    url = "http://chat.stackexchange.com/transcript/{}/{}/{}/{}/{}-{}".format(room_num, year, month, day, hour_start, hour_end)
    date = datetime.date(year, month, day)

    if debug & 2:
        print(url)

    transcript_text = ur.urlopen(url).read().decode('utf-8')

    #: Check for/against snapshot
    create_snapshot = False
    snapshot = None
    if hour_start == 0 and hour_end == 24:  # get the snapshot
        try:
            snapshot = Snapshot.objects.get(date=date)
        except ObjectDoesNotExist:
            create_snapshot = True

    if create_snapshot or snapshot:
        # Conveniently, any angle brackets arising from user input are encoded as &lt; and &gt;, so we know these regex patterns will match actual HTML
        compare = re.split('<div id="transcript"', transcript_text, maxsplit=1)[1]  # remove pre-transcript text
        compare = re.split('<div class="pager"', compare, maxsplit=1)[0]  # remove post-transcript text
        compare = re.sub('<div class="signature".*?<div class="messages"', '', compare, flags=re.DOTALL)  # remove signatures, which includes avatars

        compare_sha1 = hashlib.sha1(bytes(compare, encoding='utf-8'))

        if snapshot and snapshot.sha1 == compare_sha1:  # nothing changed; don't need to do anything
            return

        # create or update snapshot
        if create_snapshot:
            snapshot = Snapshot(date=date)
        snapshot.sha1 = compare_sha1
        snapshot.save()

    transcript = Parser(debug=debug & 1)
    transcript.feed(transcript_text)

    histories = {}
    contents = {}
    markdowns = {}

    hist = lambda n: lambda: histories.setdefault(n, ur.urlopen('https://chat.stackexchange.com/messages/{}/history'.format(n)).read().decode('utf-8'))
    cont = lambda n: lambda: contents.setdefault(n, ur.urlopen('https://chat.stackexchange.com/message/{}'.format(n)).read().decode('utf-8'))
    mark = lambda n: lambda: markdowns.setdefault(n, ur.urlopen('https://chat.stackexchange.com/messages/{}/{}'.format(room_num, n)).read().decode('utf-8'))
    threads = []

    for mid in transcript.messages:
        threads += [Thread(target=hist(mid)), Thread(target=cont(mid)), Thread(target=mark(mid))]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    ##############

    # users
    transcript_uids = set(m['uid'] for m in transcript.messages.values())
    users_in_db = User.objects.filter(uid__in=transcript_uids)
    uids_in_db = set(u.uid for u in users_in_db)

    for new_uid in transcript_uids - uids_in_db:
        User(uid=new_uid, latest_msg=0, latest_name='').save()

    users_in_db = User.objects.filter(uid__in=transcript_uids)

    # usernames
    for mid, msg in transcript.messages.items():
        user = users_in_db.get(uid=msg['uid'])

        if not Username.objects.filter(user=user.id, name=msg['name']).exists():
            Username(user=user, name=msg['name']).save()
            user.latest_name = msg['name']
            user.latest_msg = mid
            user.save()
        elif mid > user.latest_msg:
            user.latest_name = msg['name']
            user.latest_msg = mid
            user.save()

    # messages
    transcript_mids = sorted(list(transcript.messages.keys()))

    # build from transcript + history + content + markdown
    transcript_msgs = {}
    for mid in transcript_mids:
        # transcript
        msg = transcript.messages[mid].copy()

        # miscellaneous
        msg['mid'] = mid
        msg['user'] = users_in_db.get(uid=msg['uid'])
        msg['date'] = date
        msg['room'] = room_num

        # history
        history = histories[mid]
        msg['was_edited'] = "<b>edited:</b>" in history or "<b>said:</b>" not in history
        # print(history)
        hour, minute, half = re.search('<div class="timestamp".*(\d{1,2}):(\d\d) (A|P)M', history).groups()
        hour = int(hour) % 12 + 12 * (half == "P")
        minute = int(minute)
        msg['time'] = datetime.time(hour, minute)

        # content
        msg['content'] = contents[mid]
        msg_onebox = re.search('<div class="onebox ob-(\w+)', contents[mid])
        msg['onebox'] = bool(msg_onebox)
        if msg_onebox:
            msg['onebox_type'] = msg_onebox.groups()[0]

        # markdown
        msg['markdown'] = markdowns[mid]

        # finalize
        msg.pop('uid')
        transcript_msgs[mid] = msg

    msgs_in_db = Message.objects.filter(mid__gte=transcript_mids[0], mid__lte=transcript_mids[-1])
    mids_in_db = [m.mid for m in msgs_in_db]

    message_num = 0
    messages_to_create = []
    for mid, message in transcript.messages.items():
        if mid in mids_in_db:
            mids_in_db.remove(mid)

        if debug & 2:
            print("message_num, mid: {}, {}" .format(message_num, mid))
        message_num += 1

        if mid not in mids_in_db:
            messages_to_create.append(Message(**transcript_msgs[mid]))
        else:
            msgs_in_db.filter(mid=mid).update(**transcript_msgs[mid])

        # uid = message['uid']
        # rid = message['rid']
        # name = message['name']
        # stars = message['stars']
        # onebox = message['onebox']
        # content = message['content']
        # timestamp = message['timestamp']

        # if uid not in users:
        #     # try:
        #     #     user = User.objects.get(uid=uid)
        #     # except ObjectDoesNotExist:
        #     if not User.objects.filter(uid=uid).exists():
        #         user = User(uid=uid)
        #         user.save()

        #     users[uid] = {'user': user, 'names': []}
        #     names = users[uid]['names']
        # else:
        #     user = users[uid]['user']
        #     names = users[uid]['names']

        # if name not in names:
        #     # try:
        #     #     username = Username.objects.get(user=user, name=name)
        #     # except ObjectDoesNotExist:
        #     if not Username.objects.filter(name=name, user=user).exists():
        #         username = Username(name=name, user=user)
        #         username.save()

        #     names.append(name)
        # else:
        #     pass

        # try:
        #     if mid not in mids_in_db:
        #         raise ObjectDoesNotExist

        #     message = Message.objects.get(mid=mid)

        #     if message.content != content or message.name != name or message.stars != stars:
        #         message.rid = rid
        #         message.name = name
        #         message.stars = stars
        #         message.content = content
        #         message.onebox = bool(onebox)
        #         message.onebox_type = onebox

        #         message.save()

        # except ObjectDoesNotExist:
        #     hourmin, half = timestamp.split(" ")
        #     hour, minute = hourmin.split(":")
        #     hour = int(hour) % 12 + 12 * (half == "PM")
        #     minute = int(minute)
        #     time = datetime.time(hour, minute)

        #     message = Message(mid=mid, user=user, room=room_num, date=date, time=time)
        #     message.rid = rid
        #     message.name = name
        #     message.stars = stars
        #     message.content = content
        #     message.onebox = bool(onebox)
        #     message.onebox_type = onebox

        #     messages_to_create.append(message)

    # these were not in the transcript so should be deleted from the database
    Message.objects.filter(mid__in=mids_in_db).delete()

    Message.objects.bulk_create(messages_to_create)


def parse_days(start, end=datetime.datetime.now()):
    while start <= end:
        parse_convos(240, start.year, start.month, start.day, 0, 24)
        print(start)
        start += datetime.timedelta(1)


def parse_hours(start, end=datetime.datetime.now()):
    while start <= end:
        parse_convos(240, start.year, start.month, start.day, start.hour, start.hour + 1)
        print(start)
        start += datetime.timedelta(1 / 24)
