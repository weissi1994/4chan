#!/usr/bin/python
import urllib2, argparse, logging
import sys, os, re, time
import httplib
import fileinput
import telepot
from daemonize import Daemonize
from BeautifulSoup import BeautifulSoup
from converter import Converter, ffmpeg


BASE_URL = "https://boards.4chan.org/"
TG_TOKEN = "XXXX_REPLACE_WITH_YOUR_OWN_XXXX"
TG_CHAT_ID = -XXX_REPLACE_WITH_YOUR_OWN_XXX

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%I:%M:%S %p')
log = logging.getLogger('4chan')
fh = logging.FileHandler("/var/log/4chan.log", "a+")
fh.setLevel(logging.INFO)
log.addHandler(fh)
keep_fds = [fh.stream.fileno()]
workpath = os.path.dirname(os.path.realpath(__file__))
args = None

def load(url):
    req = urllib2.Request(url, headers={'User-Agent': '4chan Browser'})
    return urllib2.urlopen(req).read()

def main():
    global args
    parser = argparse.ArgumentParser(description='4chan')
    parser.add_argument('board', nargs=1, help='board name to download images from')
    args = parser.parse_args()
    find_threads(args.board[0])

def find_threads(board):
    i = 1
    while True:
        url = BASE_URL + board
        if (i != 1):
            url = url + '/' + str(i)
        try:
            soup = BeautifulSoup(load(url))
            for link in soup.findAll('a', attrs={'class': 'replylink'}):
                log.info('Browsing    ' + board + '/' + link.get("href"))
                download_thread(BASE_URL + board + '/' + link.get("href"))
            i += 1
            if (i > 10):
                i = 1
        except urllib2.HTTPError, err:
            time.sleep(10)
            try:
                load(url)
            except urllib2.HTTPError, err:
                log.warning('%s 404\'d', url)
                break
            continue
        except (urllib2.URLError, httplib.BadStatusLine, httplib.IncompleteRead):
            log.warning('Something went wrong')

        log.info('Processed   ' + board + " Page #"+str(i))

def conv_vid(path):
    c = Converter()
    conv = c.convert(path, path.replace(".webm", ".mp4"), {
        'format': 'mp4',
        'audio': {
            'codec': 'mp3'
        },
        'video': {
            'codec': 'h264'
    }})

    for timecode in conv:
        log.debug(("Converting (%d" % timecode)+"%) ...\r")
    return path.replace(".webm", ".mp4")

def download_thread(thread_link):
    board = thread_link.split('/')[3]
    thread = thread_link.split('/')[5].split('#')[0]

    directory = os.path.join(workpath, 'downloads', board, thread)
    if not os.path.exists(directory):
        os.makedirs(directory)

    try:
        regex = '(\/\/i(?:s|)\d*\.(?:4cdn|4chan)\.org\/\w+\/(\d+\.(?:jpg|png|gif|webm)))'
        for file_url, img in list(set(re.findall(regex, load(thread_link)))):
            img_path = os.path.join(directory, img)
            if not os.path.exists(img_path):
                log.info('Downloading ' + board + '/' + thread + '/' + img)
                data = load('https:' + file_url)
                file_url = img_path
                with open(img_path, 'w') as f:
                    f.write(data)

                bot = telepot.Bot(TG_TOKEN)
                log.debug('Sending to Group: ' + file_url)
                if (file_url.split('.')[-1] == "webm"):
                    try:
                        bot.sendVideo(TG_CHAT_ID, (img.replace(".webm", ".mp4"), open(conv_vid(img_path))), caption="["+board+"] "+file_url.split('/')[-1]+"\n\t"+thread_link)
                    except UnicodeDecodeError, uerr:
                        log.warning('Error      converting webm: ' + file_url)
                        break
                    except ffmpeg.FFMpegConvertError, err:
                        log.warning('Error      converting webm: ' + file_url)
                        break
                elif (file_url.split('.')[-1] == "gif"):
                    bot.sendVideo(TG_CHAT_ID, (img, open(img_path)), caption="["+board+"] "+file_url.split('/')[-1]+"\n\t"+thread_link)
                else:
                    bot.sendPhoto(TG_CHAT_ID, (img, open(img_path)), caption="["+board+"] "+file_url.split('/')[-1]+"\n\t"+thread_link)
            else:
                break
            time.sleep(10)
    except urllib2.HTTPError, err:
        log.warning('Error      processing URL: ' + thread_link)# + "\n" + err.read())
        time.sleep(20)
        try:
            load(thread_link)
        except urllib2.HTTPError, err:
            log.info('%s 404\'d', thread_link)
    except (urllib2.URLError, httplib.BadStatusLine, httplib.IncompleteRead):
        log.warning('Something went wrong')

    log.debug('Done with Thread: ' + thread_link.replace(BASE_URL, ""))


if __name__ == '__main__':
    pid = "/var/run/4chan_"+sys.argv[1]+".pid"
    try:
        d = Daemonize(app="4chan_"+sys.argv[1], pid=pid, action=main, foreground=False, keep_fds=keep_fds, logger=log)
        d.start()
        # main()
    except KeyboardInterrupt:
        pass
