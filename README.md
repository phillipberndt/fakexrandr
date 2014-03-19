FakeXRandR
==========

This is a counterpart to fakexinerama, but for XRandR. It hooks into libXrandr
and replaces a certain, configurable monitor configuration with two virtual
monitors, each of half the original's size.

Licensing
---------

You may use, redistribute and modify this program under the terms of the GNU
General Public License (GPL) Version 3, in the version available under the URL
http://www.gnu.org/licenses/gpl.html#.

Use cases
---------

You'll want to use this library if you have a multi-head setup, but a crappy
video driver which tells RandR that there is only one big monitor, resulting in
wrong window placement by window managers. Matrox Tripple Head 2 Go et al. are
other candidates, where there really is only one big monitor, but you'd want to
split it anyway.

With slight modifications, this library is also suited for developers willing to
test multi-head behaviour without multiple monitors. Keep in mind that this library
right now can not do more than split the monitor vertically in half.

Installation
------------

There now is a configure script which should do most of the work for you. Simply
run `make`, it calls `./configure` automatically for you. The script tries to autodetermine
the appropriate resolution and real/fake library locations from xrandr. `make install`
as root installs the library. Pay attention to any warnings/errors from the configure
script. To compile the library, you will need the XRandR and X11 development packages
for your distribution.

If you need fakexrandr for another use case, I trust that you are able to figure out
how to write your own `config.h` file. Here's some details for manual building:

The library will split the first screen it finds which has the resolution you
supply in `config.h` vertically in two. You might have to adjust the path to the
real libXrandr.so file. Place the resulting library file and symlink in a library
directory of higer priority, as `/usr/local/lib`. Check `ldconfig -v` for a list of
of suitable directories. Run `ldconfig` to update the ld cache. If it's working, `xrandr`
should show you a third screen, with a name ending in an underscore.

Enjoy :-)


To do
-----

* Make this run-time configurable, allow more than one split, allow horizontal and not-in-half splits

See also
--------

 * https://gist.github.com/phillipberndt/7688785
   For my version of Fake xinerama, based on Kris Maglione's version
