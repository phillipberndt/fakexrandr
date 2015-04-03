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

Authors
-------

* Phillip Berndt
* Geoffrey 'gnif' McRae

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

In most cases, simply run `make`, then install using `make install`. This will
create a configuration which splits a monitor with the largest possible
resolution that `xrandr` outputs at compile time into two virtual monitors. Pay
attention to any warnings/errors from the configure script. To compile the
library, you will need the XRandR and X11 development packages for your
distribution. To split the monitor into more than two screens, edit the `EXTRA_SCREENS`
variable in the created `config.h` file.

For **Arch Linux**, there is a [PKGBUILD](https://aur.archlinux.org/packages/fakexrandr-git/)
([git](https://github.com/pschmitt/aur-fakexrandr-git)) by
[Philipp Schmitt](https://github.com/pschmitt).

Manual installation
-------------------

If you need FakeXRandR for another use case or the automated building does not
work for you, here are some details:

The `configure` script runs `xrandr` and creates a `config.h` header with the
resolution of the monitor to split, the path to the system's real `libXrandr.so`
file and a path which preceeds that of the real library in the ld search path,
where the FakeXRandR should be placed. You can use `ldconfig -v` to get a list
of suitable directories, if `configure` should fail to determine one.

The `libXrandr.c` file only contains a initialization function which loads the
symbols from the real library and implementations of the functions that we
actually override and which require more than replacement of XIDs for fake
screens with real the one's. All other functions are automatically generated
by `make_skeleton.py` from the default Xrandr header file.

FAQ
---

* **How can I see if it's working?**<br/>
  Run `ldd xrandr`. `libXrandr.so` should show up in `/usr/local/lib`. Then,
  start `xrandr`. The screen which is set to the resolution supplied in
  `config.h` should show up twice, with the last character in the name of the
  duplicate replaced by a number. After you restarted your X11 session,
  fullscreening applications should fullscreen to the virtual screen, not the
  physical one.
* **Changing settings of the fake screen doesn't have any effect?!**<br/>
  XRandR is only used to *communicate* information on the resolution and output
  settings between X11 server, graphics driver and applications. It is up to
  the graphics driver to actually *apply* any settings. Since FakeXRandR
  only hooks into the X11 ↔ application communication, attempts to change
  settings for fake screens won't have any effect.
* **My two screens are mirrored. Does this library help?**<br/>
  No. See the FAQ in the Gist for FakeXinerama (see "See also" section).

To do
-----

* Make this run-time configurable, allow more than one split, allow horizontal and not-in-half splits

See also
--------

 * https://gist.github.com/phillipberndt/7688785
   For my version of Fake xinerama, based on Kris Maglione's version
