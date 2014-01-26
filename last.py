#!/usr/bin/python

"""
Sort one or more M3U playlists by Last.fm playcount.
Concatenate, interleave or shuffle the tracks.

Usage:

    last.py in1.m3u in2.m3u > out.m3u

Or with the -o option:

    last.py -o out.m3u in1.m3u in2.m3u

The -m option can be used to select the merging algorithm.
The -g option selects the grouping method and the -s option
selects the sorting. The -b option specifies the base directory.

    last.py in1.m3u in2.m3u > out.m3u
    last.py -m shuffle in1.m3u in2.m3u > out.m3u
    last.py -g dir in1.m3u in2.m3u > out.m3u
    last.py -s none in1.m3u in2.m3u > out.m3u
    last.py -b . in1.m3u in2.m3u > out.m3u

To install, fetch the eyeD3 and bs4 libraries:

    pip install eyeD3-pip      # or: sudo apt-get install eyed3
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
import eyeD3 # ID3 reading
import bs4   # XML/HTML parsing

API = ''    # insert key here

MERGE = ''  # merge function
GROUP = ''  # group function
SORT = ''   # sort function
GSORT = ''  # group then sort
BASE = ''   # base directory
OUTPUT = '' # output file

def load(path):
    """Load a playlist from disk."""
    if os.path.isdir(path):
        xs = loaddirectory(path)
    else:
        dir = os.path.abspath(os.path.dirname(path))
        file = open(path, 'rU')
        xs = [os.path.normpath(os.path.join(dir, line.strip()))
              for line in file if not re.match('^#', line)]
        file.close
    return xs

def loaddirectory(path):
    """Find all MP3 files in a directory."""
    files = []
    for root, dirnames, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, '*.[Mm][Pp]3'):
            files.append(os.path.join(root, filename))
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
        f.write(str + '\n')
        f.close

def timeout(fn, *args, **kwargs):
    """Call a function with a timeout."""
    result = kwargs['fail'] if 'fail' in kwargs else -1
    retry = kwargs['retry'] if 'retry' in kwargs else 5
    time = kwargs['time'] if 'time' in kwargs else 30
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
    """Return the artist and track title of an MP3 file."""
    try:
        file = eyeD3.Mp3AudioFile(path)
        tag = file.getTag()
        artist = unicode(tag.getArtist()).encode('utf-8').strip()
        track = unicode(tag.getTitle()).encode('utf-8').strip()
    except:
        return '', ''
    else:
        return artist, track

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
    dict = []
    key = key if key else lambda x: [x]
    for x in deletedup(xs):
        k = key(x)
        if k in map(lambda x: x[0], dict):
            dict = [(k, xs + [x]) if k == k0 else (k0, xs)
                    for k0, xs in dict]
        else:
            dict.append((k, [x]))
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
        artist, track = id3(x)
        rating = timeout(fn, x)
        rating = rating if rating >= 0 else 0
        result.append((x, fn(x)))
        print('#%s/%s:\t%s\t%s - %s' %
              (str(num).zfill(len(str(total))),
               total, rating, artist, track))
        # don't make more than 5 requests per second
        # (averaged over a 5 minute period)
        if num % 100 == 0:
            time.sleep(10)
        num += 1
    result = sorted(result, key=lambda x: x[1], reverse=True)
    return [x for x, c in result]

# requires a valid API key, otherwise lastfmhtml() is used instead
def lastfmxml(artist, track, listeners=False, correct=True, api=''):
    """Fetch a track's Last.fm playcount."""
    if not artist or not track: return -1
    count = 0
    api = API if not api else api
    correct = 1 if correct else 0
    url = 'http://ws.audioscrobbler.com/2.0/?'
    url += urllib.urlencode([('method',      'track.getInfo'),
                             ('api_key',     api),
                             ('artist',      artist),
                             ('track',       track),
                             ('autocorrect', correct)])
    try:
        file = urllib.urlopen(url)
        try:
            soup = bs4.BeautifulSoup(file)
            if listeners:
                node = soup.find('listeners')
            else:
                node = soup.find('playcount')
            if node:
                txt = node.get_text()
                if txt:
                    count = int(txt)
        finally:
            file.close()
    except IOError:
        return -1
    return count

# fall-back: scrape the playcount off the track's webpage
def lastfmhtml(artist, track, listeners=False):
    """Scrape a track's Last.fm playcount."""
    if not artist or not track: return -1
    count = 0
    url = ('http://www.last.fm/music/%s/_/%s' %
           (urllib.quote_plus(artist), urllib.quote_plus(track)))
    try:
        file = urllib.urlopen(url)
        try:
            soup = bs4.BeautifulSoup(file)
            if listeners:
                node = soup.find('li', 'listeners')
            else:
                node = soup.find('li', 'scrobbles')
            if node:
                txt = node.get_text()
                if txt:
                    match = re.search('[0-9,]+', txt)
                    if match:
                        txt = match.group().replace(',', '')
                        if txt:
                            count = int(txt)
        finally:
            file.close()
    except IOError:
        return -1
    return count

def lastfmrating(track, listeners=False):
    """Return the Last.fm rating for a track."""
    artist, title = id3(track)
    rating = lastfmxml if API else lastfmhtml
    return rating(artist, title, listeners)

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

def merge5x5(xss):
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
    return reduce(intersection2, xss, [])

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

def difference(xss):
    """Calculate the difference between two playlists."""
    def diff(xs, ys):
        return [x for x in deletedup(xs) if x not in ys]
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
            if ys2[0] not in xs:
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
        return id3(x)[0]
    return performgroup(xs, artist)

def groupprefix(xs):
    """Group a playlist on string prefix."""
    pre = os.path.commonprefix(xs)
    def prefix(x):
        regexp = '^%s([^/]+)' % re.escape(pre)
        match = re.match(regexp, x)
        return match.group(1) if match else ''
    return performgroup(xs, prefix)

# Sort functions

def lastfmplaycount(xs):
    """Sort tracks by Last.fm playcount."""
    return sort(xs, lastfmrating)

def lastfmlisteners(xs):
    """Sort tracks by Last.fm playcount."""
    return sort(xs, lambda x: lastfmrating(x, True))

def shuffle(xs):
    """Shuffle a playlist."""
    random.shuffle(xs)
    return xs

# Presets

def norm(xss):
    """"Normalize" a mixed playlist by merging five artists at a time."""
    return slide5x5(group(xss))

def normprefix(xss):
    """"Normalize" a mixed playlist by merging five playlists at a time."""
    return slide5x5(groupprefix(xss))

def normalize(xss):
    """Sort tracks by Last.fm playcount and normalize the playlist."""
    return norm([lastfmplaycount(xss)])

def normalizeprefix(xss):
    """Sort tracks by Last.fm playcount and normalize the playlist."""
    return normprefix([lastfmplaycount(xss)])

# Aliases

merges = { 'append' : join,
           'join' : join,
           'none' : join,

           'interleave' : interleave,

           'shuffle-interleave' : interleaveshuffle,
           'interleave-shuffle' : interleaveshuffle,
           'merge-shuffle' : interleaveshuffle,

           '5x5merge' : merge5x5,
           'merge5x5' : merge5x5,
           'merge' : merge5x5,

           '5x5' : slide5x5,
           '5x5slide' : slide5x5,
           'slide5x5' : slide5x5,
           'slide' : slide5x5,
           'sliding' : slide5x5,

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

groups = { 'artist' : groupartist,

           'prefix' : groupprefix,
           'folder' : groupprefix,
           'directory' : groupprefix,
           'dir' : groupprefix,

           'none' : performgroup }

sorts = { 'lastfm' : lastfmplaycount,
          'last.fm' : lastfmplaycount,
          'last-fm' : lastfmplaycount,
          'playcount' : lastfmplaycount,
          'plays' : lastfmplaycount,

          'listeners' : lastfmlisteners,
          'listens' : lastfmlisteners,

          'random' : shuffle,
          'randomize' : shuffle,
          'shuffle' : shuffle,

          'id' : deletedup,
          'identity' : deletedup,
          'none' : deletedup }

# Main function

def main():
    global API, MERGE, GROUP, SORT, GSORT, BASE, OUTPUT
    global merges, groups, sorts

    merge = join
    group = performgroup
    sort = lastfmplaycount

    opts, args = getopt.getopt(sys.argv[1:], 'a:b:m:g:s:o:',
                               ['api=',
                                'base=',
                                'merge=',
                                'group=',
                                'sort=',
                                'output='])

    for o, v in opts:
        if o in ('-a', '--api'):
            API = v
        if o in ('-b', '--base'):
            BASE = v
        if o in ('-m', '--merge'):
            MERGE = v.lower().strip()
            merge = merges[MERGE]
        elif o in ('-g', '--group'):
            GROUP = v.lower().strip()
            group = groups[GROUP]
        elif o in ('-s', '--sort'):
            SORT = v.lower().strip()
            sort = sorts[SORT]
            if GROUP: GSORT = True
        elif o in ('-o', '--output'):
            OUTPUT = v

    if MERGE and not GROUP:
        group = groupartist
    if GROUP and not MERGE:
        merge = slide5x5
    if SORT and (sort != deletedup) and not (MERGE or GROUP):
        merge = slide5x5
        group = groupprefix

    xss = map(load, args)
    xss = deletedups(xss)

    if GSORT:
        result = merge(map(sort, join(map(group, xss))))
    else:
        result = merge(join(map(group, map(sort, xss))))

    write(result, OUTPUT, BASE)

if __name__ == '__main__':
    main()
