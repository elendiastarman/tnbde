import urllib.request as ur
from urllib.error import HTTPError
from psycopg2 import DatabaseError as p_DatabaseError
from psycopg2 import OperationalError as p_OperationalError
from psycopg2 import InterfaceError as p_InterfaceError
from django.db.utils import DatabaseError as d_DatabaseError
from django.db.utils import OperationalError as d_OperationalError
from django.db.utils import InterfaceError as d_InterfaceError
import html.parser as hp
from django.core.exceptions import ObjectDoesNotExist
from threading import Thread
from stem import Signal
from stem.control import Controller

import re
import http
import time
import random
import hashlib
import datetime
import requests
import subprocess

from transcriptAnalyzer.models import *

wait_lock = [0]
session = requests.session()
session.proxies = {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}


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


# signal TOR for a new connection
def renew_connection():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="password")
        controller.signal(Signal.NEWNYM)


def retry_wrapper(func, name, mid, log=False):
    def wrapped_func():
        max_tries = 5
        for trie in range(max_tries):
            try:
                func()
                return
            except ur.URLError:
                if log:
                    print("URLError for {}({}); sleeping for 1 second".format(name, mid))
                time.sleep(1)
            except http.client.RemoteDisconnected:
                if log:
                    print("RemoteDisconnected for {}({}); sleeping for 1 second".format(name, mid))
                time.sleep(1)
        else:
            raise ValueError("Unable to execute function.")

    return wrapped_func


def read_url(url, max_tries=0):
    fails = 0
    me = random.randint(1, 10**8)

    while not max_tries or fails < max_tries:
        if wait_lock[0]:
            if wait_lock[0] == me:
                wait_lock[0] = 0
            else:
                time.sleep(fails * 30)
                continue

        response = session.get(url)
        if response.status_code == 200:
            return response.text
        elif response.status_code == 429:  # too many requests error
            if not wait_lock[0]:
                wait_lock[0] = me
                print("Got a 429 error; sleeping for {} seconds.".format(fails * 30))
            time.sleep(fails * 30)
        else:
            raise ValueError("Response status was not 200 or 429")

        fails += 1


def redo_wrapper(func, log=False):
    max_tries = 5
    for i in range(max_tries):
        try:
            return func()
            break
        except (p_DatabaseError, d_DatabaseError, p_OperationalError, d_OperationalError, p_InterfaceError, d_InterfaceError):
            if log:
                print("Database error occurred; sleeping for {} seconds".format(i * 15))
            time.sleep(i * 15)
    else:
        raise ValueError("Could not exeute database operation")


def parse_convos(room_num=240, year=2016, month=3, day=23, hour_start=0, hour_end=4, debug=0, log=0, snapshot_only=False):
    url = "http://chat.stackexchange.com/transcript/{}/{}/{}/{}/{}-{}".format(room_num, year, month, day, hour_start, hour_end)
    date = datetime.date(year, month, day)

    if debug & 2:
        print(url)

    if debug & 4:
        print("Getting transcript text for {}...".format(date))
    transcript_text = read_url(url)
    if debug & 4:
        print("Transcript text fetched.")

    if re.search('<div class="system-message">.*?no messages today.*?</div>', transcript_text, flags=re.DOTALL):
        if debug & 4:
            print("No messages found.")
        return

    #: Check for/against snapshot
    create_snapshot = False
    snapshot = None
    if hour_start == 0 and hour_end == 24:  # get the snapshot
        try:
            snapshot = redo_wrapper(lambda: Snapshot.objects.get(date=date), log=debug & 64)
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

        if snapshot_only:
            if create_snapshot:
                snapshot = Snapshot(date=date)

            snapshot.sha1 = compare_sha1
            redo_wrapper(lambda: snapshot.save(), log=debug & 64)

            if debug & 4:
                print("Snapshot created!")

            return

    transcript = Parser(debug=debug & 1)
    transcript.feed(transcript_text)

    if len(transcript.messages) == 0:
        return

    transcript_mids = sorted(list(transcript.messages.keys()))

    # Clear out cached responses to queries
    redo_wrapper(lambda: Query.objects.exclude(response='').update(response=''), log=debug & 64)

    # users
    transcript_uids = set(m['uid'] for m in transcript.messages.values())
    users_in_db = redo_wrapper(lambda: User.objects.filter(uid__in=transcript_uids), log=debug & 64)
    uids_in_db = redo_wrapper(lambda: set(u.uid for u in users_in_db), log=debug & 64)

    for new_uid in transcript_uids - uids_in_db:
        redo_wrapper(lambda: User(uid=new_uid, latest_msg=0, latest_name='').save(), log=debug & 64)

    users_in_db = redo_wrapper(lambda: User.objects.filter(uid__in=transcript_uids), log=debug & 64)

    if debug & 4:
        print("User objects are done!")

    # usernames
    for mid, msg in transcript.messages.items():
        user = redo_wrapper(lambda: users_in_db.get(uid=msg['uid']), log=debug & 64)

        if not redo_wrapper(lambda: Username.objects.filter(user=user.id, name=msg['name']).exists(), log=debug & 64):
            redo_wrapper(lambda: Username(user=user, name=msg['name']).save(), log=debug & 64)
            user.latest_name = msg['name']
            user.latest_msg = mid
            redo_wrapper(lambda: user.save(), log=debug & 64)
        elif mid > user.latest_msg:
            user.latest_name = msg['name']
            user.latest_msg = mid
            redo_wrapper(lambda: user.save(), log=debug & 64)

    if debug & 4:
        print("Username objects are done!")

    hist = lambda n: lambda: histories.setdefault(n, read_url('https://chat.stackexchange.com/messages/{}/history'.format(n)))
    cont = lambda n: lambda: contents.setdefault(n, read_url('https://chat.stackexchange.com/message/{}'.format(n)))
    mark = lambda n: lambda: markdowns.setdefault(n, read_url('https://chat.stackexchange.com/messages/{}/{}'.format(room_num, n)))
    threads = []

    for mid in transcript_mids:
        threads += [Thread(target=retry_wrapper(hist(mid), 'history', mid, debug & 32)),
                    Thread(target=retry_wrapper(cont(mid), 'content', mid, debug & 32)),
                    Thread(target=retry_wrapper(mark(mid), 'markdown', mid, debug & 32))]

    if debug & 4:
        print("Starting the threads... ({} of them)".format(len(threads)))

    db_counter = 0
    db_chunk_size = 100

    while db_counter * 3 < len(threads):
        renew_connection()
        if debug & 8:
            print("New IP: {}".format(session.get('http://httpbin.org/ip').text))

        if debug & 8:
            print("Running DB chunk {}-{} (out of {})".format(db_counter, db_counter + db_chunk_size, len(threads) // 3))

        histories = {}
        contents = {}
        markdowns = {}
        transcript_msgs = {}

        thread_chunk = threads[3 * db_counter:3 * (db_counter + db_chunk_size)]
        chunk_mids = transcript_mids[db_counter:db_counter + db_chunk_size]

        db_counter += db_chunk_size

        thread_counter = 0
        thread_chunk_size = 30
        threads_to_run = []
        while thread_counter < len(thread_chunk):
            if debug & 16:
                print("Running threads {}-{}...".format(thread_counter, thread_counter + thread_chunk_size), end='')  # noqa

            threads_to_run = thread_chunk[thread_counter:thread_counter + thread_chunk_size]
            thread_counter += thread_chunk_size

            for t in threads_to_run:
                t.start()

            for t in threads_to_run:
                t.join()

            if debug & 16:
                print("  Done!")

        if debug & 8:
            print("Threads are done!")

        ##############

        # build messages from transcript + history + content + markdown
        for mid in chunk_mids:
            # transcript
            msg = transcript.messages[mid].copy()

            # miscellaneous
            msg['mid'] = mid
            msg['user'] = redo_wrapper(lambda: users_in_db.get(uid=msg['uid']), log=debug & 64)
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

            if chr(0) in msg['content'] or chr(0) in msg['markdown']:
                msg['content'] = msg['content'].replace(chr(0), '').replace('\x00', '')
                msg['markdown'] = msg['markdown'].replace(chr(0), '').replace('\x00', '')
                if debug & 16:
                    print("Bad message! mid: {}".format(msg['mid']))
                    print(msg)

        msgs_in_db = redo_wrapper(lambda: Message.objects.filter(mid__gte=chunk_mids[0], mid__lte=chunk_mids[-1]), log=debug & 64)
        mids_in_db = redo_wrapper(lambda: [m.mid for m in msgs_in_db], log=debug & 64)

        message_num = 0
        messages_to_create = []
        for mid in chunk_mids:
            # message = transcript.messages[mid]

            if mid in mids_in_db:
                mids_in_db.remove(mid)

            if debug & 2:
                print("message_num, mid: {}, {}" .format(message_num, mid))

            message_num += 1

            if mid not in mids_in_db:
                messages_to_create.append(Message(**transcript_msgs[mid]))
            else:
                redo_wrapper(lambda: msgs_in_db.filter(mid=mid).update(**transcript_msgs[mid]), log=debug & 64)

        if debug & 8:
            print("Message stuff done!")

        # these were not in the transcript so should be deleted from the database
        redo_wrapper(lambda: Message.objects.filter(mid__in=mids_in_db).delete(), log=debug & 64)

        redo_wrapper(lambda: Message.objects.bulk_create(messages_to_create), log=debug & 64)

        if debug & 8:
            print("Message table updated!")

    if debug & 4:
        print("All messages done!")

    if create_snapshot or snapshot:
        # create or update snapshot
        if create_snapshot:
            snapshot = Snapshot(date=date)

        snapshot.sha1 = compare_sha1
        redo_wrapper(lambda: snapshot.save(), log=debug & 64)

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


def parse_days_with_processes(start, end=datetime.datetime.now(), debug=0):
    while start <= end:
        # template = '/usr/local/bin/python3 /home/elendia/webapps/ppcg/PPCG/manage.py shell -c "from transcriptAnalyzer.transcriptAnalyzer_database import *; parse_convos(240, {}, {}, {}, {{}}, {{}}, debug={})"'.format(start.year, start.month, start.day, debug)
        template = 'python manage.py shell -c "from transcriptAnalyzer.transcriptAnalyzer_database import *; parse_convos(240, {}, {}, {}, {{}}, {{}}, debug={})"'.format(start.year, start.month, start.day, debug)
        command = ''
        mode = 'day'
        st = time.time()

        print("Starting subprocess with command `{}`".format(template.format(0, 24)))

        return_code = 1
        runs = 0
        max_day_fails = 3
        max_hour_fails = 20
        hour = 0

        while return_code:
            runs += 1

            if runs - hour > max_hour_fails + max_day_fails:
                with open('tnbde_fails.txt', 'a') as f:
                    f.write('command "{}" failed'.format(command))
                    return

            elif runs > max_day_fails:
                try:
                    redo_wrapper(lambda: Snapshot.objects.get(date=start), log=debug & 64)
                    break
                except ObjectDoesNotExist:
                    mode = 'hour'
                    print("Transitioning to hour mode.")

            if mode == 'day':
                command = template.format(0, 24)
            elif mode == 'hour':
                command = template.format(hour, hour + 1)
                print("  Parsing hour {}...".format(hour))

            return_code = subprocess.run(command, shell=True).returncode

            if return_code and mode == 'day':
                time.sleep(runs)
                print("Starting subprocess again; iteration {}".format(runs))
            elif not return_code and mode == 'hour':
                if hour < 23:
                    hour += 1
                    return_code = 1  # reset for next loop
                else:
                    tries = 5
                    for i in range(tries):
                        try:
                            parse_convos(240, start.year, start.month, start.day, 0, 24, debug=debug, snapshot_only=True)
                            break
                        except (p_DatabaseError, d_DatabaseError, p_OperationalError, d_OperationalError, p_InterfaceError, d_InterfaceError):
                            if debug & 64:
                                print("Failed to create snapshot due to database error; sleeping for {} seconds".format(10 + i * 10))
                            time.sleep(10 + i * 10)
                    else:
                        raise ValueError("Unable to create snapshot.")

        print("Elapsed time: {}".format(time.time() - st))
        print(start)
        start += datetime.timedelta(1)
