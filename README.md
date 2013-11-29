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

Adjust the `#DEFINE` lines at the top of libXrandr.c to your configuration. The
library will split the first screen it finds which has the resolution you
supply there vertically in two. You might also have to adjust the path to the
real libXrandr.so file.

Then compile using `make`. You will need the XRandR and X11 development packages
for your distribution. Place the resulting library file and symlink in a library
directory of higer priority, as `/usr/local/lib`. Run `ldconfig` to update the
ld cache.

Enjoy :-)


To do
-----

Not all XRandR calls are implemented yet, but only those that are needed for
GTK applications to work and those needed to run the `xrandr` tool. Feel free
to extend this!

See also
--------

 * https://gist.github.com/phillipberndt/7688785
   For my version of Fake xinerama, based on Kris Maglione's version
