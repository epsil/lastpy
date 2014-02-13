#!/usr/bin/python

"""
Sort one or more M3U playlists by Last.fm playcount.
Concatenate, interleave or shuffle the tracks.

Usage:

    last.py in1.m3u in2.m3u out.m3u

The -m option can be used to select the merging algorithm.
The -g option selects the grouping method and the -o option
selects the ordering. The -b option specifies the base directory.

    last.py in1.m3u in2.m3u > out.m3u
    last.py -m shuffle in1.m3u in2.m3u > out.m3u
    last.py -g dir in1.m3u in2.m3u > out.m3u
    last.py -o none in1.m3u in2.m3u > out.m3u
    last.py -b . in1.m3u in2.m3u > out.m3u

To install, fetch the mutagen and bs4 libraries:

    pip install mutagen
    pip install beautifulsoup4

Then chmod +x and symlink to /usr/local/bin/last.py.
"""

import fnmatch
import getopt
import multiprocessing
import os
import random
import re
import subprocess
import sys
import time
import urllib

# XML/HTML parsing
import bs4

# ID3 reading
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

API = ''    # insert key here

MERGE = ''  # merge function
GROUP = ''  # group function
ORDER = ''  # sort function
GFIRST = '' # group then sort
BASE = ''   # base directory
OUTPUT = '' # output file

def load(path):
    """Load a playlist from disk."""
    if os.path.isdir(path):
        xs = loaddirectory(path)
    else:
        dir = os.path.abspath(os.path.dirname(path))
        file = open(path, 'rU')
        try:
            xs = [os.path.normpath(os.path.join(dir, line.strip()))
                  for line in file if not re.match('^#', line)]
        finally:
            file.close()
    return xs

def loaddirectory(path):
    """Find all MP3 files in a directory."""
    files = []
    for root, dirnames, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, '*.[Mm][Pp]3'):
            path = os.path.join(root, filename)
            files.append(os.path.abspath(path))
    files.sort()
    return files

def tostring(xs):
    """Convert a playlist to a string."""
    return '\n'.join(xs)

def write(xs, file=None, base=''):
    """Write a playlist to file or standard output."""
    if base:
        xs = [os.path.relpath(x, base) for x in xs]
    else:
        xs = [os.path.abspath(x) for x in xs]
    str = tostring(xs)
    print(str)
    if file:
        f = open(file, 'w')
        try:
            f.write(str + '\n')
        finally:
            f.close()

def timeout(fn, *args, **kwargs):
    """Call a function with a timeout."""
    result = kwargs.get('fail', -1)
    retry = kwargs.get('retry', 5)
    time = kwargs.get('time', 30)
    pool = multiprocessing.Pool(1, maxtasksperchild=1)
    while retry > 0:
        try:
            result = pool.apply_async(fn, args)
            result = result.get(timeout=time)
            retry = 0
        except multiprocessing.TimeoutError:
            retry =- 1
        finally:
            pool.terminate()
    return result

def id3(path):
    """Return the metadata of an MP3 file."""
    def utf8(str):
        return unicode(str).encode('utf-8').strip()
    meta = {'artist': '', 'title': '', 'album': '', 'albumartist' : ''}
    try:
        tags = EasyID3(path)
        tags2 = ID3(path)
        meta['artist'] = tags.get('artist', [''])[0]
        meta['title'] = tags.get('title', [''])[0]
        meta['album'] = tags.get('album', [''])[0]
        meta['albumartist'] = tags2.get('TPE2', [''])[0]
        meta = {key: utf8(meta[key]) for key in meta}
        meta['artist'] = meta['artist'] or meta['albumartist']
        meta['albumartist'] = meta['albumartist'] or meta['artist']
    except:
        pass
    return meta

def subrange(xs):
    """Find the lowest contiguous decreasing subrange."""
    beg = 0
    end = 1 if xs else 0
    i = 0
    prev = None
    for x in xs:
        if prev:
            if i == end and x == prev - 1:
                end = i + 1
            elif x < prev:
                beg = i - 1 if x == prev - 1 else i
                end = i + 1
        i += 1
        prev = x
    return (beg, end)

class Memoize:
    """Memoization wrapper."""
    def __init__(self, fn):
        self.fn = fn
        self.memo = {}
    def __call__(self, *args):
        if not args in self.memo:
            self.memo[args] = self.fn(*args)
        return self.memo[args]

class RandomGenerator:
    """Fair random generator."""
    def __init__(self):
        self.outcomes = [] # list of outcomes
        self.history =  [] # list of previous outcomes
        random.seed() # seed the random number generator

    def choice(self, fair=True):
        """Get a fair outcome."""
        if not fair:
            return self.random()
        elif self.size() <= 2:
            return self.random()
        else:
            while len(self.history) > self.size() / 2:
                self.history.pop()
            x = self.random()
            while x in self.history:
                x = self.random()
            self.history.insert(0, x)
            return x

    def random(self):
        """Get a random outcome."""
        size = len(self.outcomes)
        if size == 0:
            return None
        else:
            return self.outcomes[random.randrange(0, size)]

    def size(self):
        """Number of outcomes."""
        return len(self.outcomes)

    def insert(self, x):
        """Add an outcome."""
        self.outcomes.append(x)

    def remove(self, x):
        """Remove an outcome."""
        if x in self.outcomes:
            self.outcomes.remove(x)
        if x in self.history:
            self.history.remove(x)

    def update(self, x, y):
        """Update an outcome."""
        if x in self.outcomes:
            self.outcomes[self.outcomes.index(x)] = y
        if x in self.history:
            self.history[self.history.index(x)] = y

def performmerge(xss, window, pick, rand=False, fair=True):
    """Merge tracks from playlists by interleaving or random choice."""
    rand = RandomGenerator() if rand == True else rand
    q = []
    result = []
    while q or xss:
        # remove empty tracks from q
        r = []
        for xs, c in q:
            if xs:
                r.append((xs, c))
            elif rand: rand.remove(xs)
        q = r
        # put playlist back in xss
        if pick > 0 and xss:
            r = []
            for xs, c in q:
                if c >= pick:
                    if rand: rand.remove(xs)
                    xss.append(xs)
                else:
                    r.append((xs, c))
            q = r
        # insert playlist into q
        while xss and (window <= 0 or len(q) < window):
            xs = xss.pop(0)
            if rand: rand.insert(xs)
            q.append((xs, 0))
        # add track to result
        if q and rand:
            xs = rand.choice(fair)
            x = xs.pop(0)
            result.append(x)
            q = [(lst, c + 1 if lst == xs else c) for lst, c in q]
        else:
            if fair:
                beg, end = subrange([c for xs, c in q])
                chosen = q[beg:end]
            else:
                chosen = q
            r = []
            for xs, c in q:
                if (xs, c) in chosen:
                    x = xs.pop(0)
                    result.append(x)
                    r.append((xs, c + 1))
                else:
                    r.append((xs, c))
            q = r
    return result

def performgroup(xs, key=None):
    """Group a playlist into several."""
    dict = [] # use a list to preserve order
    keyfn = key if key else lambda x: 0
    for x in deletedup(xs):
        key = keyfn(x)
        for k, xs in dict:
            if k == key:
                xs.append(x)
                break
        else:
            dict.append((key, [x]))
    return [xs for k, xs in dict]

def deletedup(xs):
    """Delete duplicates in a playlist."""
    result = []
    for x in xs:
        if x not in result:
            result.append(x)
    return result

def deletedups(xss):
    """Delete duplicates in playlists."""
    xss = map(deletedup, xss)
    i = 0
    for xs in xss[1:]:
        for x in xss[i]:
            if x in xs: xs.remove(x)
        i += 1
    return [xs for xs in xss if xs]

def sort(xs, fn):
    """Sort tracks by rating."""
    total = len(xs)
    num = 1
    result = []
    for x in xs:
        tags = id3(x)
        rating = timeout(fn, x)
        rating = rating if rating >= 0 else 0
        result.append((x, fn(x)))
        print('#%s/%s:\t%s\t%s - %s' %
              (str(num).zfill(len(str(total))),
               total, rating, tags['artist'], tags['title']))
        # don't make more than 5 requests per second
        # (averaged over a 5 minute period)
        if num % 100 == 0:
            time.sleep(10)
        num += 1
    result = sorted(result, key=lambda x: x[1], reverse=True)
    return [x for x, c in result]

# Scraping functions

# requires a valid API key, otherwise lastfmhtml() is used instead
def lastfmxml(artist, title, listeners=False, correct=True, api=''):
    """Fetch a track's Last.fm playcount."""
    if not artist or not title: return -1
    rating = 0
    api = API if not api else api
    correct = 1 if correct else 0
    url = 'http://ws.audioscrobbler.com/2.0/?'
    url += urllib.urlencode([('method',      'track.getInfo'),
                             ('api_key',     api),
                             ('artist',      artist),
                             ('track',       title),
                             ('autocorrect', correct)])
    try:
        file = urllib.urlopen(url)
        try:
            soup = bs4.BeautifulSoup(file)
            if listeners:
                node = soup.find('listeners')
            else:
                node = soup.find('playcount')
            if not node: return -1
            txt = node.get_text()
            if not txt: return -1
            rating = int(txt)
        finally:
            file.close()
    except IOError:
        return -1
    return rating

# fall-back: scrape the playcount off the track's webpage
def lastfmhtml(artist, title, listeners=False):
    """Scrape a track's Last.fm playcount."""
    if not artist or not title: return -1
    rating = 0
    url = ('http://www.last.fm/music/%s/_/%s' %
           (urllib.quote_plus(artist), urllib.quote_plus(title)))
    try:
        file = urllib.urlopen(url)
        try:
            soup = bs4.BeautifulSoup(file)
            if listeners:
                node = soup.find('li', 'listeners')
            else:
                node = soup.find('li', 'scrobbles')
            if not node: return -1
            txt = node.get_text()
            if not txt: return -1
            match = re.search('[0-9,]+', txt)
            if not match: return -1
            txt = match.group().replace(',', '')
            if not txt: return -1
            rating = int(txt)
        finally:
            file.close()
    except IOError:
        return -1
    return rating

# Cache functions
lastfmxml = Memoize(lastfmxml)
lastfmhtml = Memoize(lastfmhtml)

def lastfmrating(track, listeners=False):
    """Return the Last.fm rating for a track."""
    tags = id3(track)
    rating = lastfmxml if API else lastfmhtml
    return rating(tags['artist'], tags['title'], listeners)

def lastfmplaycountrating(track):
    """Return Last.fm playcount."""
    return lastfmrating(track, True)

def lastfmlistenersrating(track):
    """Return Last.fm listeners."""
    return lastfmrating(track, True)

def lastfmproductrating(track):
    """Return Last.fm playcount times Last.fm listeners."""
    playcount = lastfmrating(track)
    listeners = lastfmrating(track, True)
    return playcount * listeners

def lastfmdivisionrating(track):
    """Return Last.fm playcount per Last.fm listeners."""
    playcount = lastfmrating(track)
    listeners = lastfmrating(track, True)
    return float(playcount) / float(listeners)

# Merge functions

def join(xss):
    """Chain playlists together."""
    return reduce(lambda x, y: x + y, xss, [])

def interleave(xss):
    """Interleave playlists by alternating between them."""
    return performmerge(xss, 0, 0, False, False)

def interleaveshuffle(xss):
    """Interleave playlists by randomly alternating between them."""
    return performmerge(xss, 0, 0, True, False)

def mergewindow(m, n, xss):
    """Interleave n tracks from m playlists."""
    return performmerge(xss, m, n, False, False)

def slidingwindow(m, n, xss):
    """Interleave n tracks from m playlists."""
    return performmerge(xss, m, n, False, True)

def shufflewindow(m, n, xss):
    """Randomly interleave n tracks from m playlists."""
    return performmerge(xss, m, n, True, False)

def tumble5x5(xss):
    """Merge five artists at a time."""
    return mergewindow(5, 5, xss)

def slide5x5(xss):
    """Slide five artists at a time."""
    return slidingwindow(5, 5, xss)

def shuffle5x5(xss):
    """Shuffle five artists at a time."""
    return shufflewindow(5, 5, xss)

def union(xss):
    """
    Interleave the union of two playlists.
    Elements unique to XS are picked over elements unique to YS,
    which are picked over common elements. Common elements are
    picked from XS and removed from YS. The general case is a left fold,
    i.e., union(union(union(xs, ys), zs) ...).

    Pseudo-code:

    -- unique x
    merge (x:xs) ys =
    x:merge xs ys

    -- unique y
    merge xs y:ys =
    x:merge xs ys

    -- common element
    merge (x:xs) (ys1 ++ [x] ++ ys2) =
    x:merge xs (ys1 ++ ys2)
    """
    def union2(xs, ys):
        xs2 = deletedup(xs)
        ys2 = deletedup(ys)
        result = []
        while xs2 and ys2:
            if xs2[0] not in ys:
                result.append(xs2.pop(0))
            elif ys2[0] not in xs:
                result.append(ys2.pop(0))
            else:
                x = xs2.pop(0)
                while x in ys2: ys2.remove(x)
                result.append(x)
        return result + xs2 + ys2
    return reduce(union2, xss, [])

def intersection(xss):
    """Interleave the intersection of playlists."""
    def intersection2(xs, ys):
        return [x for x in deletedup(xs) if x in ys]
    return reduce(intersection2, xss) if xss else []

def difference(xss):
    """Calculate the difference between two playlists."""
    def diff(xs, ys):
        return [x for x in deletedup(xs) if x not in ys]
    return reduce(diff, xss) if xss else []

def symmetricdifference(xss):
    """Interleave the symmetric difference of playlists."""
    def diff(xs, ys):
        xs2 = deletedup(xs)
        ys2 = deletedup(ys)
        result = []
        while xs2 and ys2:
            if xs2[0] not in ys:
                result.append(xs2.pop(0))
            elif ys2[0] not in xs:
                result.append(ys2.pop(0))
            else:
                x = xs2.pop(0)
                while x in ys2: ys2.remove(x)
        return result + xs2 + ys2
    return reduce(diff, xss, [])

def overlay(xss):
    """
    Interleave two playlists by overlaying unique elements.
    Elements from YS are only picked if they are unique.
    Non-unique YS elements are ignored, and an element
    from XS is picked instead. Thus, the unique elements of YS
    are "overlaid" onto XS. The general case is a left fold,
    i.e., overlay(overlay(overlay(xs, ys), zs) ...).

    Pseudo-code:

    -- unique y
    merge xs y:ys =
    x:merge xs ys

    -- common element
    merge (x:xs) (x:xs)
    x:merge xs ys
    """
    def overlay2(xs, ys):
        xs2 = deletedup(xs)
        ys2 = deletedup(ys)
        result = []
        while xs2 and ys2:
            if xs2[0] not in ys:
                result.append(xs2.pop(0))
            elif ys2[0] not in xs:
                result.append(ys2.pop(0))
            else:
                ys2.pop(0)
                result.append(xs2.pop(0))
        return result + xs2 + ys2
    return reduce(overlay2, xss, [])

# Group functions

def groupartist(xs):
    """Group a playlist on artist."""
    def artist(x):
        return id3(x)['artist']
    return performgroup(xs, artist)

def groupdir(xs):
    """Group a playlist on directory."""
    prefix = os.path.commonprefix(xs)
    def dir(x):
        regexp = '^%s([^/]+)' % re.escape(prefix)
        match = re.match(regexp, x)
        return match.group(1) if match else ''
    return performgroup(xs, dir)

def groupdir2(xs):
    """Group a playlist on subdirectory."""
    prefix = os.path.commonprefix(xs)
    def dir(x):
        regexp = '^%s([^/]+/[^/]+)' % re.escape(prefix)
        match = re.match(regexp, x)
        return match.group(1) if match else ''
    return performgroup(xs, dir)

# Sort functions

def lastfmplaycount(xs):
    """Sort tracks by Last.fm playcount."""
    return sort(xs, lastfmplaycountrating)

def lastfmlisteners(xs):
    """Sort tracks by Last.fm listeners."""
    return sort(xs, lastfmlistenersrating)

def lastfmproduct(xs):
    """Sort tracks by Last.fm playcount times Last.fm listeners."""
    return sort(xs, lastfmproductrating)

def lastfmdivision(xs):
    """Sort tracks by Last.fm playcount per Last.fm listeners."""
    return sort(xs, lastfmdivisionrating)

def shuffle(xs):
    """Shuffle a playlist."""
    random.shuffle(xs)
    return xs

def reverse(xs):
    """Reverse a playlist."""
    xs.reverse()
    return xs

# Presets

def norm(xss):
    """"Normalize" a mixed playlist by merging five artists at a time."""
    return slide5x5(group(xss))

def normprefix(xss):
    """"Normalize" a mixed playlist by merging five playlists at a time."""
    return slide5x5(groupdir(xss))

def normalize(xss):
    """Sort tracks by Last.fm playcount and normalize the playlist."""
    return norm([lastfmplaycount(xss)])

def normalizeprefix(xss):
    """Sort tracks by Last.fm playcount and normalize the playlist."""
    return normprefix([lastfmplaycount(xss)])

# Aliases

mergings = { 'append' : join,
             'join' : join,
             'none' : join,

             'interleave' : interleave,

             'shuffle-interleave' : interleaveshuffle,
             'interleave-shuffle' : interleaveshuffle,
             'merge-shuffle' : interleaveshuffle,

             '5x5merge' : tumble5x5,
             'merge5x5' : tumble5x5,
             'tumble' : tumble5x5,
             'tumbling' : tumble5x5,

             '5x5' : slide5x5,
             '5x5slide' : slide5x5,
             'slide5x5' : slide5x5,
             'slide' : slide5x5,
             'sliding' : slide5x5,
             'merge' : slide5x5,

             '5x5shuffle' : shuffle5x5,
             'shuffle5x5' : shuffle5x5,
             'shuffle' : shuffle5x5,

             'union' : union,
             'merge-union' : union,
             'unique-merge' : union,
             'unique-interleave' : union,
             'interleave-unique' : union,
             'merge-unique' : union,

             'intersection' : intersection,
             'merge-intersection' : intersection,
             'intersect' : intersection,

             'symmetric-difference' : symmetricdifference,

             'difference' : difference,

             'overlay' : overlay,
             'overlay-merge' : overlay,
             'overlay-interleave' : overlay,
             'interleave-overlay' : overlay,
             'merge-overlay' : overlay }

groupings = { 'artist' : groupartist,

              'prefix' : groupdir,
              'folder' : groupdir,
              'directory' : groupdir,
              'dir' : groupdir,

              'prefix2' : groupdir2,
              'folder2' : groupdir2,
              'directory2' : groupdir2,
              'subdirectory' : groupdir2,
              'sub' : groupdir2,
              'dir2' : groupdir2,

              'none' : performgroup }

orderings = { 'lastfm' : lastfmplaycount,
              'last.fm' : lastfmplaycount,
              'last-fm' : lastfmplaycount,
              'playcount' : lastfmplaycount,
              'plays' : lastfmplaycount,

              'listeners' : lastfmlisteners,
              'listens' : lastfmlisteners,

              'product' : lastfmproduct,
              'times' : lastfmproduct,

              'division' : lastfmdivision,
              'per' : lastfmdivision,

              'random' : shuffle,
              'randomize' : shuffle,
              'shuffle' : shuffle,

              'reverse' : reverse,

              'id' : deletedup,
              'identity' : deletedup,
              'none' : deletedup }

# Main function

def main():
    global API, MERGE, GROUP, ORDER, GFIRST, BASE, OUTPUT
    global mergings, groupings, orderings

    merge = join
    group = performgroup
    order = lastfmplaycount

    opts, args = getopt.getopt(sys.argv[1:],
                               'a:b:m:g:o:',
                               ['api=',
                                'base=',
                                'merge=',
                                'group=',
                                'order='])

    for o, v in opts:
        if o in ('-a', '--api'):
            API = v
        if o in ('-b', '--base'):
            BASE = v
        if o in ('-m', '--merge'):
            MERGE = v.lower().strip()
            merge = mergings[MERGE]
        elif o in ('-g', '--group'):
            GROUP = v.lower().strip()
            group = groupings[GROUP]
        elif o in ('-o', '--order'):
            ORDER = v.lower().strip()
            order = orderings[ORDER]
            if GROUP: GFIRST = True

    if len(args) > 1:
        OUTPUT = args.pop()

    if MERGE and not GROUP:
        group = groupartist
    if GROUP and not MERGE:
        merge = slide5x5

    xss = map(load, args)

    if GFIRST:
        result = merge(map(order, join(map(group, xss))))
    else:
        result = merge(join(map(group, map(order, xss))))

    write(result, OUTPUT, BASE)

if __name__ == '__main__':
    main()
