import urllib.request as ur
import html.parser as hp
from django.core.exceptions import ObjectDoesNotExist
from threading import Thread

import re
import http
import time
import hashlib
import datetime

from transcriptAnalyzer.models import *


class Parser(hp.HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.state = ""
        self.names = {}
        self.messages = {}

        self.debug = kwargs.get('debug', 0)
        if self.debug:
            print("Debug on.")

    def handle_starttag(self, tag, attrs):
        if tag in ("div", "a"):
            if 1 and self.debug:
                print("tag, attrs:", tag, attrs)

            if len(attrs) == 0 or attrs[0][0] != "class":
                return

            if attrs[0][1].startswith("monologue"):
                uid = attrs[0][1].split('-', maxsplit=1)[1]
                self.curr_user = int(uid) if uid else None
                if uid not in self.names:
                    self.state = "need name"

            elif attrs[0][1] == "message":
                mid = int(attrs[1][1].split('-')[1])
                self.messages[mid] = {'uid': self.curr_user,
                                      'rid': None,
                                      'name': self.names[self.curr_user],
                                      'stars': 0}

                self.curr_mess = self.messages[mid]

            elif attrs[0][1] == "reply-info":
                rid = int(attrs[1][1].split('#')[1])
                self.curr_mess["rid"] = rid

            elif attrs[0][1] == "username" and self.state == "need name":
                self.state = "get name"

        elif tag == "span" and len(attrs) and attrs[0][0] == 'class' and 'stars' in attrs[0][1]:
            self.state = "has stars"

        elif self.state == "has stars" and tag == "span" and len(attrs) and attrs[0] == ('class', 'times'):
            self.state = "get stars"

    def handle_data(self, data):
        if self.state == "get name":
            self.state = ""
            if not self.curr_user:
                self.curr_user = int(data.strip()[4:])
            self.names[self.curr_user] = data.strip()

        elif self.state == "get stars":
            self.state = ""
            data = data.strip()
            self.curr_mess['stars'] = int(data) if data else 1


def retry_wrapper(func, name, mid, log=False):
    def wrapped_func():
        success = False
        while not success:
            try:
                func()
                success = True
            except ur.URLError:
                if log:
                    print("URLError for {}({})".format(name, mid))
                time.sleep(1)
            except http.client.RemoteDisconnected:
                if log:
                    print("RemoteDisconnected for {}({})".format(name, mid))
                time.sleep(1)

    return wrapped_func


# class Retriever:
#     def __init__(self, mid, name, func, log=False):
#         self.mid = mid
#         self.name = name
#         self.func = func(mid)
#         self.log = log

#     def __call__(self):
#         success = False
#         while not success:
#             try:
#                 self.func()
#                 success = True
#             except ur.URLError:
#                 if self.log:
#                     print("URLError for {}({})".format(self.name, self.mid))
#                 time.sleep(1)
#             except http.client.RemoteDisconnected:
#                 if self.log:
#                     print("RemoteDisconnected for {}({})".format(self.name, self.mid))
#                 time.sleep(1)


def parse_convos(room_num=240, year=2016, month=3, day=23, hour_start=0, hour_end=4, debug=0, log=0):
    url = "http://chat.stackexchange.com/transcript/{}/{}/{}/{}/{}-{}".format(room_num, year, month, day, hour_start, hour_end)
    date = datetime.date(year, month, day)

    if debug & 2:
        print(url)

    if debug & 4:
        print("Getting transcript text for {}...".format(date))
    transcript_text = ur.urlopen(url).read().decode('utf-8')
    if debug & 4:
        print("Transcript text fetched.")

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
        compare = re.split('<a href="/transcript', compare, maxsplit=1)[0]  # remove post-transcript text
        compare = re.sub('<div class="signature".*?<div class="messages"', '', compare, flags=re.DOTALL)  # remove signatures, which includes avatars

        compare_sha1 = hashlib.sha1(bytes(compare, encoding='utf-8')).hexdigest()
        # if snapshot:
        #     print("Snapshot sha1: {}".format(snapshot.sha1))
        # print("compare_sha1: {}".format(compare_sha1))

        if snapshot and snapshot.sha1 == compare_sha1:  # nothing changed; don't need to do anything
            if debug & 4:
                print(date, snapshot.sha1, compare_sha1)
            return

        # if snapshot and snapshot.sha1 != compare_sha1:
        #     print(date, snapshot.sha1, compare_sha1)
        #     return compare

    transcript = Parser(debug=debug & 1)
    transcript.feed(transcript_text)

    if len(transcript.messages) == 0:
        return

    histories = {}
    contents = {}
    markdowns = {}

    hist = lambda n: lambda: histories.setdefault(n, ur.urlopen('https://chat.stackexchange.com/messages/{}/history'.format(n)).read().decode('utf-8'))
    cont = lambda n: lambda: contents.setdefault(n, ur.urlopen('https://chat.stackexchange.com/message/{}'.format(n)).read().decode('utf-8'))
    mark = lambda n: lambda: markdowns.setdefault(n, ur.urlopen('https://chat.stackexchange.com/messages/{}/{}'.format(room_num, n)).read().decode('utf-8'))
    threads = []

    for mid in transcript.messages:
        threads += [Thread(target=retry_wrapper(hist(mid), 'history', mid, log & 1)),
                    Thread(target=retry_wrapper(cont(mid), 'content', mid, log & 1)),
                    Thread(target=retry_wrapper(mark(mid), 'markdown', mid, log & 1))]

    if debug & 4:
        print("Starting the threads... ({} of them)".format(len(threads)))
    counter = 0
    chunk_size = 30
    threads_to_run = []
    while counter < len(threads):
        if debug & 8:
            print("Running threads {}-{}...".format(counter, counter + chunk_size), end='')

        threads_to_run = threads[counter:counter + chunk_size]
        counter += chunk_size

        for t in threads_to_run:
            t.start()

        for t in threads_to_run:
            t.join()

        if debug & 8:
            print("  Done!")

    if debug & 4:
        print("Threads are done!")
    ##############

    # users
    transcript_uids = set(m['uid'] for m in transcript.messages.values())
    users_in_db = User.objects.filter(uid__in=transcript_uids)
    uids_in_db = set(u.uid for u in users_in_db)

    for new_uid in transcript_uids - uids_in_db:
        User(uid=new_uid, latest_msg=0, latest_name='').save()

    users_in_db = User.objects.filter(uid__in=transcript_uids)

    if debug & 4:
        print("User objects are done!")

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

    if debug & 4:
        print("Username objects are done!")

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

    if debug & 4:
        print("Message stuff done!")

    # these were not in the transcript so should be deleted from the database
    Message.objects.filter(mid__in=mids_in_db).delete()

    Message.objects.bulk_create(messages_to_create)

    if debug & 4:
        print("Message table updated!")

    if create_snapshot or snapshot:
        # create or update snapshot
        if create_snapshot:
            snapshot = Snapshot(date=date)
        snapshot.sha1 = compare_sha1
        snapshot.save()

    if debug & 4:
        print("Snapshot created!")


def parse_days(start, end=datetime.datetime.now(), debug=0):
    while start <= end:
        parse_convos(240, start.year, start.month, start.day, 0, 24, debug=debug)
        print(start)
        start += datetime.timedelta(1)


def parse_hours(start, end=datetime.datetime.now(), debug=0):
    while start <= end:
        parse_convos(240, start.year, start.month, start.day, start.hour, start.hour + 1, debug=debug)
        print(start)
        start += datetime.timedelta(1 / 24)
