last.py
=======

Sort MP3 files by Last.fm total plays (scrobbles by all listeners).

Installation
------------

`last.py` requires the `eventlet`, `eyeD3` and `bs4` libraries:

    pip install eventlet  # or: sudo apt-get install python-eventlet
    pip install eyeD3-pip # or: sudo apt-get install eyed3
    pip install beautifulsoup4

Then make the script executable and copy it to a suitable location in
`PATH`, for example `/usr/local/bin/last.py`:

    chmod +x last.py
    sudo cp last.py /usr/local/bin

On Windows, the script can be invoked with `python last.py`.

Usage
-----

To sort a folder or a playlist by playcount:

    last.py folder
    last.py playlist.m3u

The output is a new playlist, which can written to a file with the `>`
operator or the `-o` option:

    last.py playlist.m3u > sorted.m3u
    last.py -o sorted.m3u playlist.m3u

This generally works well for sorting tracks by the same artist. When
sorting various artists, however, the raw Last.fm ratings tend to
produce a playlist too uneven and clustered for casual listening. Use
the `-m` option to sort each artist separately and then interleave
their tracks:

    last.py -m merge playlist.m3u

This picks the top five tracks from the top five artists, followed by
the top five tracks from the second top five artists, and so on. For a
more randomized output, use the `shuffle` merging method:

    last.py -m shuffle playlist.m3u

By default, the merging is based on grouping tracks by their `Artist`
ID3 tag. A different grouping can be specified with the `-g` option:

    last.py -m shuffle -g dir playlist.m3u

This groups the files by folder. To only invoke the merging part of
the script (maybe when processing a presorted list), use the `-s`
option to disable Last.fm sorting altogether:

    last.py -m shuffle -s none playlist.m3u

Miscellaneous
-------------

To leverage the Last.fm XML [API](http://www.last.fm/api), a free API
key must be pasted into the beginning of the script:

    API = ''    # insert key here

Otherwise, the script will scrape the playcount off the webpage of
each track, which is much slower.

Since the script fetches each track's playcount separately, processing
a large playlist may take some time. Last.fm's
[terms of service](http://www.last.fm/api/tos) limit the number of
requests to 5 per second (averaged over a 5 minute period), so the
script takes regular breaks to avoid overloading the server.

Of course, all MP3 files must be correctly tagged for sorting to work.
In some cases, Last.fm may auto-correct misspelled titles.
