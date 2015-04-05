FakeXRandR
==========

This is a tool to cheat an X11 server to believe that there are more monitors
than there actually are. It hooks into libXRandR and libXinerama and replaces
certain, configurable monitor configurations with virtual monitors. A tool that
comes with this package can be used to configure how monitors are split.

This tool used to only work with XRandR, but I found it useful to add Xinerama
emulation. It can be readily removed if it isn't needed though.

Licensing
---------

You may use, redistribute and modify this program under the terms of the GNU
General Public License (GPL) Version 3, in the version available under the URL
http://www.gnu.org/licenses/gpl.html#.

Authors
-------

* Phillip Berndt
* Geoffrey 'gnif' McRae
* Gerry Demaret

Use cases
---------

You'll want to use this library if you have a multi-head setup, but a crappy
video driver which tells RandR that there is only one big monitor, resulting in
wrong window placement by window managers. Matrox Tripple Head 2 Go et al. are
other candidates, where there really is only one big monitor, but you'd want to
split it anyway.

Installation
------------

In most cases, simply run `make`, then install using `make install`. This will determine
where the library should be installed and where the originals reside. Pay
attention to any warnings/errors from the configure script. To compile the
library, you will need the XRandR and X11 development packages for your
distribution.

After installation, use the `manage.py` tool to create a configuration (in
`~/.config/fakexrandr.bin`).

For **Arch Linux**, there is a [PKGBUILD](https://aur.archlinux.org/packages/fakexrandr-git/)
([git](https://github.com/pschmitt/aur-fakexrandr-git)) by
[Philipp Schmitt](https://github.com/pschmitt).

Manual installation
-------------------

If you need FakeXRandR for another use case or the automated building does not
work for you, here are some details:

The `configure` script creates a `config.h` header with the
path to the system's real `libXrandr.so` file and a path which preceeds that of
the real library in the ld search path, where the FakeXRandR should be placed.
You can use `ldconfig -v` to get a list of suitable directories, if `configure`
should fail to determine one.

The `libXrandr.c` file only contains a initialization function which loads the
symbols from the real library and implementations of the functions that we
actually override and which require more than replacement of XIDs for fake
screens with real the one's. All other functions are automatically generated
by `make_skeleton.py` from the default Xrandr header file.

FAQ
---

* **How can I see if it's working?**<br/>
  Run `ldd xrandr`. `libXrandr.so` should show up in `/usr/local/lib`. Then,
  start `xrandr`. Any split screens should show up multiple times, with `~1`,
  `~2`, etc. appended to their names.  After you restarted your X11 session,
  fullscreening applications using Xrandr (e.g. GTK apps) should fullscreen to
  the virtual screen, not the physical one.
* **Changing settings of the fake screen doesn't have any effect?!**<br/>
  XRandR is only used to *communicate* information on the resolution and output
  settings between X11 server, graphics driver and applications. It is up to
  the graphics driver to actually *apply* any settings. Since FakeXRandR
  only hooks into the X11 ↔ application communication, attempts to change
  settings for fake screens won't have any effect.
* **My two screens are mirrored. Does this library help?**<br/>
  No. See the FAQ in the Gist for FakeXinerama (see "See also" section).

See also
--------

 * https://gist.github.com/phillipberndt/7688785
   For my version of Fake xinerama, based on Kris Maglione's version
