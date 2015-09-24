#!/usr/bin/env python
# vim:fdm=marker:fileencoding=utf8
"""
    This script provides a GUI/CLI for fakexrandr configurations



    The configuration is stored in a binary format for efficient reading.

    <file contents> := <store> <file contents>
                     | <store>

    <store>         := <configuration length: 4 bytes unsigned native byte order length of the configuration> <configuration>

    <configuration> := <name of the configuration: 128 characters, zero padded> <edid for configuration: 768 characters> <width: 4 bytes unsigned native byte order> <height: see width> <splits>

    <splits>        := (("H"|"V") <position of the split: see width> <splits> <splits>)
                     | "N"

                        H means horizontal split (position is a y coordinate), V is a vertical split (position is an x coordinate),
                        N means no further splits

    All units are pixels.

    The configuration is stored in ~/.config/fakexrandr.bin.
"""

from __future__ import print_function
import shlex

import ctypes
import os
import struct
import sys

try:
    from gi.repository import Gtk, Gdk
    HAS_GTK=True
except ImportError:
    HAS_GTK=False

CONFIGURATION_FILE_PATH = os.path.expanduser("~/.config/fakexrandr.bin")

" Code to open Xlib via ctypes {{{ "
try:
    libX11 = ctypes.CDLL("libX11.so")
    # Prefer Xrandr from one of the default directories over a fake version
    for directory in ("/usr/lib/x86_64-linux-gnu/", "/usr/lib", "/lib/x86_64-linux-gnu/", "/lib", "/usr/lib/i386-linux-gnu/", "/lib/i386-linux-gnu/"):
        Xrandr_path = os.path.join(directory, "libXrandr.so")
        if os.path.isfile(Xrandr_path):
            libXrandr = ctypes.CDLL(Xrandr_path)
            break
    else:
        libXrandr = ctypes.CDLL("libXrandr.so")
        if hasattr(libXrandr, "_is_fake_xrandr"):
            print >> sys.stderr, "Warning: Failed to use the real XrandR library; falling back to the fake one."
    libX11.XOpenDisplay.restype = ctypes.c_voidp
    display = libX11.XOpenDisplay("")
    if not display:
        raise RuntimeError("Failed to open X11 display")
    HAS_X11_DISPLAY=True
except:
    HAS_X11_DISPLAY=False
    display = None
    libX11 = None

def require_x11():
    if not HAS_X11_DISPLAY:
        print("The GUI requires ctypes to be able to open libX11.so and an X Display", file=sys.stderr)
        if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
            print("The DISPLAY environment variable is not set!", file=sys.stderr)
        sys.exit(1)

" }}}"

" Code to query for outputs and crtcs via the Randr extension {{{ "
class XRRScreenResources(ctypes.Structure):
    _fields_ = [("timestamp", ctypes.c_ulong),
                ("configTimestamp", ctypes.c_ulong),
                ("ncrtc", ctypes.c_int),
                ("crtcs", ctypes.POINTER(ctypes.c_long)),
                ("noutput", ctypes.c_int),
                ("outputs", ctypes.POINTER(ctypes.c_long)),
                ("nmode", ctypes.c_int),
                ("modes", ctypes.POINTER(ctypes.c_long))]
if HAS_X11_DISPLAY:
    libXrandr.XRRGetScreenResources.restype = ctypes.POINTER(XRRScreenResources)

class XRROutputInfo(ctypes.Structure):
    _fields_ = [("timestamp", ctypes.c_ulong),
                ("crtc", ctypes.c_ulong),
                ("name", ctypes.c_char_p),
                ("nameLen", ctypes.c_int),
                ("mm_width", ctypes.c_ulong),
                ("mm_height", ctypes.c_ulong),
                ("connection", ctypes.c_ushort),
                ("subpixel_order", ctypes.c_ushort),
                ("ncrtc", ctypes.c_int),
                ("crtcs", ctypes.POINTER(ctypes.c_long)),
                ("nclone", ctypes.c_int),
                ("clones", ctypes.POINTER(ctypes.c_long)),
                ("nmode", ctypes.c_int),
                ("npreferec", ctypes.c_int),
                ("modes", ctypes.POINTER(ctypes.c_long))
               ]
if HAS_X11_DISPLAY:
    libXrandr.XRRGetOutputInfo.restype = ctypes.POINTER(XRROutputInfo)

class XRRCrtcInfo(ctypes.Structure):
    _fields_ = [("timestamp", ctypes.c_ulong),
                ("x", ctypes.c_int),
                ("y", ctypes.c_int),
                ("width", ctypes.c_uint),
                ("height", ctypes.c_uint),
                ("mode", ctypes.c_long),
                ("rotation", ctypes.c_ushort),
                ("noutput", ctypes.c_int),
                ("outputs", ctypes.POINTER(ctypes.c_long)),
                ("rotations", ctypes.c_ushort),
                ("npossible", ctypes.c_int),
                ("possible", ctypes.POINTER(ctypes.c_long))]

if HAS_X11_DISPLAY:
    libXrandr.XRRGetCrtcInfo.restype = ctypes.POINTER(XRRCrtcInfo)
    libXrandr.XRRListOutputProperties.restype = ctypes.POINTER(ctypes.c_voidp)
    libX11.XGetAtomName.restype = ctypes.c_char_p
    libX11.XInternAtom.restype = ctypes.c_long

def query_xrandr():
    root_window = libX11.XDefaultRootWindow(display)
    screen_resources = libXrandr.XRRGetScreenResources(display, root_window)

    to_dict = lambda what: dict((x, getattr(out.contents, x)) for x in dir(what.contents) if x[0] != "_")

    edidAtom = libX11.XInternAtom(display, b"EDID", 1)

    crtcs = {}
    for i in range(screen_resources.contents.ncrtc):
        out = libXrandr.XRRGetCrtcInfo(display, screen_resources, screen_resources.contents.crtcs[i])
        crtcs[screen_resources.contents.crtcs[i]] = to_dict(out)
        libXrandr.XRRFreeCrtcInfo(out)

    outputs = {}
    for i in range(screen_resources.contents.noutput):
        out = libXrandr.XRRGetOutputInfo(display, screen_resources, screen_resources.contents.outputs[i])

        if out.contents.crtc == 0:
            continue

        actual_type = ctypes.c_long()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.c_void_p()
        libXrandr.XRRGetOutputProperty(display, screen_resources.contents.outputs[i], edidAtom,
                                       0, 384, False, False, 0, ctypes.byref(actual_type),
                                       ctypes.byref(actual_format), ctypes.byref(nitems),
                                       ctypes.byref(bytes_after), ctypes.byref(prop))

        if nitems.value > 0:
            outputs[out.contents.name] = to_dict(out)
            outputs[out.contents.name]["edid"] = ("".join(( "%02x" % (ctypes.cast(prop.value + i, ctypes.POINTER(ctypes.c_ubyte)).contents.value) for i in range(nitems.value) ))).encode("ascii")
            outputs[out.contents.name]["crtc"] = crtcs[outputs[out.contents.name]["crtc"]]

        libXrandr.XRRFreeOutputInfo(out)


    libXrandr.XRRFreeScreenResources(screen_resources)

    return outputs
" }}} "

" GUI {{{ "
class Configuration(object):
    def __init__(self, name, edid, width, height):
        self.edid = edid
        self.width = width
        self.height = height
        self.name = name
        # Split syntax:
        # split: [HV] <split position> {split} {split} | N
        self.splits = [ ]

    @property
    def ascii_name(self):
        return self.name.decode("ascii")

    @property
    def splits_str(self):
        def _build(arr):
            if not arr:
                return b"N"
            return b"".join([struct.pack("=cI", arr[0], int(arr[1])), _build(arr[2]), _build(arr[3])])
        return _build(self.splits)

    @splits_str.setter
    def splits_str(self, istr):
        def _build(istr):
            stype = istr[:1]
            if stype == b"N":
                return [ ], istr[1:]
            pos, = struct.unpack("I", istr[1:5])
            left, istr = _build(istr[5:])
            right, istr = _build(istr)
            return [ stype, pos, left, right ], istr
        self.splits = _build(istr)[0]

    @property
    def human_readable_splits_str(self):
        def _build(arr):
            if not arr:
                return "N"
            return "\n".join(["%c %d" % (arr[0].decode("ascii"), int(arr[1])),
                              " %s" % ("\n ".join(_build(arr[2]).split("\n"))),
                              " %s" % ("\n ".join(_build(arr[3]).split("\n")))])
        return _build(self.splits)

    @human_readable_splits_str.setter
    def human_readable_splits_str(self, istr):
        tokens = istr.encode().split()
        def _build():
            stype = tokens.pop(0)
            if stype == b"N":
                return []
            if stype not in (b"H", b"V"):
                raise ValueError("Unknown split type: %c" % stype)
            pos = tokens.pop(0)
            left = _build()
            right = _build()
            return [ stype, pos, left, right ]
        self.splits = _build()

    @property
    def splits_count(self):
        def _build(arr):
            if not arr:
                return 1
            return _build(arr[2]) + _build(arr[3])
        return _build(self.splits)

    def get_split_for_point(self, x, y, split=None):
        if split is None:
            split = self.splits
        if not split:
            return [ split ]
        if (y if split[0] == b"H" else x) < split[1]:
            return self.get_split_for_point(x, y, split[2]) + [ split ]
        else:
            if split[0] == b"H":
                y -= split[1]
            else:
                x -= split[1]
            return self.get_split_for_point(x, y, split[3]) + [ split ]

    @property
    def formatted_name(self):
        return "{c.name}@{c.width}x{c.height}".format(c=self)

    def __eq__(self, other):
        return other.edid == self.edid and self.width == other.width and self.height == other.height

    def __str__(self):
        assert len(self.edid) <= 768
        assert len(self.name) <= 128
        return b"".join([struct.pack("128s768sIII", self.name, self.edid, int(self.width), int(self.height), self.splits_count), self.splits_str])
    __bytes__ = __str__

    @classmethod
    def new_from_str(cls, string):
        obj = cls.__new__(cls)
        obj.name, obj.edid, obj.width, obj.height, _ = struct.unpack("128s768sIII", string[:128+768+4*3])
        if b"\x00" in obj.edid:
            obj.edid = obj.edid[:obj.edid.index(b"\x00")]
        obj.name = obj.name[:obj.name.index(b"\x00")]
        obj.splits_str = string[128+768+4*3:]
        obj.height = float(obj.height)
        obj.width = float(obj.width)
        return obj

    @classmethod
    def new_from_shdict(cls, variables):
        obj = cls.__new__(cls)
        obj.name = variables["NAME"].encode()
        obj.edid = variables["EDID"].encode()
        obj.height = float(variables["HEIGHT"])
        obj.width = float(variables["WIDTH"])
        obj.human_readable_splits_str = variables["SPLITS"]
        return obj

def base_coordinates(splits):
    x = 0
    y = 0
    while len(splits) > 1:
        if splits[1][2] is not splits[0]:
            assert(splits[1][3] is splits[0])
            if splits[1][0] == b"H":
                y += splits[1][1]
            else:
                x += splits[1][1]
        splits = splits[1:]
    return x, y

def rounded_rectangle(cr, x, y, w, h, r=20):
    # This is just one of the samples from
    # http://www.cairographics.org/cookbook/roundedrectangles/
    #   A****BQ
    #  H      C
    #  *      *
    #  G      D
    #   F****E

    cr.move_to(x+r,y)                      # Move to A
    cr.line_to(x+w-r,y)                    # Straight line to B
    cr.curve_to(x+w,y,x+w,y,x+w,y+r)       # Curve to C, Control points are both at Q
    cr.line_to(x+w,y+h-r)                  # Move to D
    cr.curve_to(x+w,y+h,x+w,y+h,x+w-r,y+h) # Curve to E
    cr.line_to(x+r,y+h)                    # Line to F
    cr.curve_to(x,y+h,x,y+h,x,y+h-r)       # Curve to G
    cr.line_to(x,y+r)                      # Line to H
    cr.curve_to(x,y,x,y,x+r,y)             # Curve to A

class ConfigurationWidget(Gtk.HBox):
    colors = [ (int(x[:2], 16)/255., int(x[2:4], 16)/255., int(x[4:], 16)/255.) for x in """
              5e412f fcebb6 78c0a8 f07818 f0a830 b1eb00 53bbf4 ff85cb ff432e ffac00
            """.split() ]

    def draw_canvas(self, widget, context):
        rounded_rectangle(context, 0, 0, 300, 300./self._aspect_ratio, 20)
        context.set_source_rgb(*ConfigurationWidget.colors[0])
        context.fill_preserve()
        context.set_source_rgb(0, 0, 0)
        context.stroke_preserve()
        context.clip()

        def _draw_split(self, context, split, color_index=0):
            if color_index == len(ConfigurationWidget.colors) - 1:
                color_index = 0
            if not split:
                context.rectangle(0, 0, 300., 300. / self._aspect_ratio)
                context.set_source_rgb(*ConfigurationWidget.colors[color_index])
                context.fill_preserve()
                context.set_source_rgb(0, 0, 0)
                context.stroke()
                return color_index
            context.save()
            if split[0] == b"H":
                context.save()
                color_index = _draw_split(self, context, split[2], color_index)
                context.restore()
                context.save()
                context.translate(0, split[1] / self._configuration.height * 300. / self._aspect_ratio)
                color_index = _draw_split(self, context, split[3], color_index + 1)
                context.restore()
            else:
                context.save()
                color_index = _draw_split(self, context, split[2], color_index)
                context.restore()
                context.save()
                context.translate(split[1] / self._configuration.width * 300., 0.)
                color_index = _draw_split(self, context, split[3], color_index + 1)
                context.restore()
            context.restore()
            return color_index
        _draw_split(self, context, self._configuration.splits)

        rounded_rectangle(context, 0, 0, 300, 300/self._aspect_ratio, 20)
        context.set_source_rgb(0, 0, 0)
        context.stroke()

    def add_remove_observer(self, callback):
        self._remove_observer_callbacks.append(callback)

    def remove_handler(self, widget):
        for callback in self._remove_observer_callbacks:
            callback()
        self.destroy()

    def canvas_mouse_handler(self, widget, event):
        if self._mouse_handler_mouse_down_at:
            if abs(event.x - 150.) < 10:
                event.x = 150.
            if abs(event.y - 150. / self._aspect_ratio) < 10:
                event.y = 150. / self._aspect_ratio
            self.set_info("(%04dpx, %04dpx) = (%02d%%, %02d%%)" % (event.x / 300. * self._configuration.width, event.y / 300. * self._aspect_ratio * self._configuration.height,
                                                           event.x / 3., event.y / 3. * self._aspect_ratio))
            if self._mouse_handler_decision == 3:
                self._mouse_handler_alter_in[0][1] = event.x / 300. * self._configuration.width - base_coordinates(self._mouse_handler_alter_in)[0]
            elif self._mouse_handler_decision == 4:
                self._mouse_handler_alter_in[0][1] = event.y / 300. * self._aspect_ratio * self._configuration.height - base_coordinates(self._mouse_handler_alter_in)[1]
            else:
                xdiff = abs(event.x - self._mouse_handler_mouse_down_at[0])
                ydiff = abs(event.y - self._mouse_handler_mouse_down_at[1])
                while len(self._mouse_handler_modify_split[0]) > 0:
                    self._mouse_handler_modify_split[0].pop()
                if self._mouse_handler_decision == 1 or (self._mouse_handler_decision != 2 and xdiff > ydiff and xdiff > 50):
                    base = base_coordinates(self._mouse_handler_modify_split)
                    self._mouse_handler_modify_split[0] += [ b"H", event.y / 300. * self._aspect_ratio * self._configuration.height - base[1], [], [] ]
                    self._mouse_handler_decision = 1
                elif self._mouse_handler_decision == 2 or (self._mouse_handler_decision != 1 and ydiff > 50):
                    base = base_coordinates(self._mouse_handler_modify_split)
                    self._mouse_handler_modify_split[0] += [ b"V", event.x / 300. * self._configuration.width - base[0], [], [] ]
                    self._mouse_handler_decision = 2
            self.queue_draw()

    def canvas_mouse_button_handler(self, state, widget, event):
        if state == 1:
            self._mouse_handler_decision = -1.
            self._mouse_handler_mouse_down_at = (event.x, event.y)
            mouse_x = self._mouse_handler_mouse_down_at[0] / 300. * self._configuration.width
            mouse_y = self._mouse_handler_mouse_down_at[1] / 300. * self._aspect_ratio * self._configuration.height
            target_split = self._configuration.get_split_for_point(mouse_x, mouse_y)
            pos_within_target = base_coordinates(target_split)
            pos_within_target = [ mouse_x - pos_within_target[0], mouse_y - pos_within_target[1] ]

            button = event.get_button()[1]
            self._mouse_handler_modify_split = target_split
            if len(target_split) > 1:
                # Check if right or bottom edge is moved / removed
                alt_target_split = self._configuration.get_split_for_point(mouse_x + 20, mouse_y + 20)
                alt_pos_within_target = base_coordinates(alt_target_split)
                alt_pos_within_target = [ mouse_x + 20 - alt_pos_within_target[0], mouse_y + 20 - alt_pos_within_target[1] ]
                if alt_pos_within_target[0] < 50 or alt_pos_within_target[1] < 50:
                    target_split = alt_target_split
                    pos_within_target = alt_pos_within_target
            if len(target_split) > 1 and pos_within_target[0] < 50:
                # (Re)Move left edge
                which = 1
                while True:
                    if target_split[which][0] == b"V" and target_split[which][3] is target_split[which - 1]:
                        break
                    which += 1
                self._mouse_handler_alter_in = target_split[which:]
                self._mouse_handler_decision = 3 if button == 1 else 5
            elif len(target_split) > 1 and pos_within_target[1] < 50:
                # (Re)Move top edge
                which = 1
                while True:
                    if target_split[which][0] == b"H" and target_split[which][3] is target_split[which - 1]:
                        break
                    which += 1
                self._mouse_handler_alter_in = target_split[which:]
                self._mouse_handler_decision = 4 if button == 1 else 5
            elif button == 1:
                # New edge
                self._mouse_handler_stored_configuration_splits = self._configuration.splits_str
                self._mouse_handler_decision = 0
        else:
            xdiff = abs(event.x - self._mouse_handler_mouse_down_at[0])
            ydiff = abs(event.y - self._mouse_handler_mouse_down_at[1])

            if xdiff < 10 and ydiff < 10 and self._mouse_handler_decision == 5:
                # Remove edge
                try:
                    replacer = self._mouse_handler_alter_in[0][2]
                    while len(self._mouse_handler_alter_in[0]):
                        self._mouse_handler_alter_in[0].pop()
                    self._mouse_handler_alter_in[0] += replacer
                except IndexError:
                    pass
                self.queue_draw()
            self._mouse_handler_mouse_down_at = False
            self.set_info("")

    def __init__(self, configuration):
        self._configuration = configuration
        self._remove_observer_callbacks = []
        self._aspect_ratio = 1.*configuration.width/configuration.height
        self._mouse_handler_mouse_down_at = False
        super(ConfigurationWidget, self).__init__()

        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect("draw", self.draw_canvas)
        self.drawing_area.set_size_request(300, 300/self._aspect_ratio)
        self.drawing_area.set_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_HINT_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.drawing_area.connect("motion_notify_event", self.canvas_mouse_handler)
        self.drawing_area.connect("button_press_event", lambda *a: self.canvas_mouse_button_handler(1, *a))
        self.drawing_area.connect("button_release_event", lambda *a: self.canvas_mouse_button_handler(0, *a))

        self.pack_start(self.drawing_area, False, False, 10)

        vbox = Gtk.VBox()
        remove = Gtk.Button("Remove")
        remove.connect("clicked", self.remove_handler)
        vbox.pack_start(remove, False, False, 5)
        self.pack_end(vbox, False, False, 5)
        info = Gtk.Label()
        self._info_label = info
        self.set_info("")
        self.pack_end(info, True, True, 5)

    def set_info(self, text):
        edid = (self._configuration.edid[:10] + b"..." + self._configuration.edid[-10:]).decode("ascii")
        self._info_label.set_markup("<b>{c.ascii_name}@{c.width}x{c.height}</b>\nEDID: {shortened_edid}\n\n{text}".format(c=self._configuration, shortened_edid=edid, text=text))

def serialize_configurations(configurations):
    retval = []
    for config in configurations:
        sconfig = bytes(config)
        retval.append(struct.pack("=I", len(sconfig)))
        retval.append(sconfig)
    return b"".join(retval)

def unserialize_configurations(data):
    while data:
        length, = struct.unpack("=I", data[:4])
        yield Configuration.new_from_str(data[4:4+length])
        data = data[4+length:]

class MainWindow(Gtk.Window):
    def load_displays(self):
        self._displays = query_xrandr()
        self.displays_combo_store.clear()
        self._displays_order = []
        for name, output in self._displays.items():
            verbose_name = "{name}@{crtc[width]:d}x{crtc[height]:d} (edid={edidS}...{edidE})".format(name=name.decode("ascii"), crtc=output["crtc"], edidS=output["edid"].decode("ascii")[:10], edidE=output["edid"].decode("ascii")[-10:])
            self.displays_combo_store.append((name.decode("ascii"), verbose_name))
            self._displays_order.append(name)
        self.combo_box.set_active(0)

    def create_configuration(self, widget):
        index = self.combo_box.get_active()
        if index < 0:
            error = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, "Please select a valid output.")
            error.connect("response", lambda *a: error.destroy())
            error.show()
            return
        output = self._displays[self._displays_order[index]]
        configuration = Configuration(output["name"], output["edid"], output["crtc"]["width"], output["crtc"]["height"])
        self.add_configuration(configuration)

    def serialize(self):
        return serialize_configurations(self._configurations)

    def load(self, data):
        for config in unserialize_configurations(data):
            self.add_configuration(config)

    def add_configuration(self, configuration):
        try:
            oldConfiguration = self._configurations[self._configurations.index(configuration)]

            error = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, "A configuration for this monitor is already present as {name}".format(name=oldConfiguration.formatted_name))
            error.connect("response", lambda *a: error.destroy())
            error.show()
            return
        except ValueError:
            pass
        self._configurations.append(configuration)
        widget = ConfigurationWidget(configuration)
        @widget.add_remove_observer
        def remove_configuration():
            self._configurations.remove(configuration)
        widget.show_all()
        self.scroller_window.pack_start(widget, False, False, 5)

    def initialize_design(self):
        vbox = Gtk.VBox()
        hbox = Gtk.HBox()
        self.displays_combo_store = Gtk.ListStore(str, str)
        self.combo_box = Gtk.ComboBox.new_with_model_and_entry(self.displays_combo_store)
        self.combo_box.set_entry_text_column(1)
        self.scroller_window = Gtk.VBox()
        actual_scroller = Gtk.ScrolledWindow()
        actual_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        actual_scroller.add_with_viewport(self.scroller_window)
        hbox.pack_start(self.combo_box, True, True, 1)
        button = Gtk.Button("Create")
        button.set_tooltip_text("Create a configuration for the selected display")
        button.connect("clicked", self.create_configuration)
        hbox.pack_end(button, False, False, 1)
        vbox.pack_start(hbox, False, False, 1)
        vbox.pack_end(actual_scroller, True, True, 1)
        self.add(vbox)
        self.set_focus(button)


    def on_hide_window(self, widget):
        configuration = self.serialize()

        if configuration == self._initial_configuration_data:
            Gtk.main_quit()
            return

        dialog = False

        def _msgrsp(widget, response):
            if dialog:
                dialog.destroy()
            if Gtk.ResponseType.YES == response:
                try:
                    with open(CONFIGURATION_FILE_PATH, "wb") as output:
                        output.write(configuration)
                    Gtk.main_quit()
                except:
                    error = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, "Failed to save configuration to ~/.config/fakexrandr.bin")
                    error.connect("response", lambda *a: Gtk.main_quit())
                    error.show()
                    return
            Gtk.main_quit()

        if not self._initial_configuration_data:
            _msgrsp(False, Gtk.ResponseType.YES)
            return

        dialog = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, "Save new configuration?")
        dialog.connect("response", _msgrsp)
        dialog.show()

    def __init__(self):
        super(MainWindow, self).__init__()
        self._configurations = []
        self._initial_configuration_data = False
        self.connect("hide", self.on_hide_window)
        self.set_title("FakeXRandr configuration")
        self.initialize_design()
        self.load_displays()
        self.set_resizable(False)
        self.set_size_request(600, 600)

        if os.access(CONFIGURATION_FILE_PATH, os.R_OK):
            try:
                configuration_data = open(CONFIGURATION_FILE_PATH, "rb").read()
                self._initial_configuration_data = configuration_data
                self.load(configuration_data)
            except:
                error = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, "Failed to load configuration from ~/.config/fakexrandr.bin")
                error.connect("response", lambda *a: error.destroy())
                error.show()
" }}} "

def perform_action(action):
    if action == "gui":
        if not HAS_GTK:
            print("The GUI requires PyGObject.", file=sys.stderr)
            sys.exit(1)
        require_x11()

        wnd = MainWindow()
        wnd.show_all()
        Gtk.main()

    elif action == "dump-config":
        if os.access(CONFIGURATION_FILE_PATH, os.R_OK):
            try:
                for config in unserialize_configurations(open(CONFIGURATION_FILE_PATH, "rb").read()):
                    print("NAME=\"%s\"\nEDID=%s\nWIDTH=%d\nHEIGHT=%d" % (config.name.decode(), config.edid.decode(), config.width, config.height))
                    print("SPLITS=\"%s\"" % config.human_readable_splits_str)
                    print()
            except:
                print("Failed to load configurations from %s" % CONFIGURATION_FILE_PATH, file=sys.stderr)
                sys.exit(1)
        else:
            print("There does not exist a configuration in %s yet." % CONFIGURATION_FILE_PATH, file=sys.stderr)
            sys.exit(1)

    elif action == "show-available":
        require_x11()
        for name, output in query_xrandr().items():
            print("NAME=\"%s\"\nEDID=%s\nWIDTH=%d\nHEIGHT=%d\nSPLITS=\"N\"\n" % (name.decode(), output["edid"].decode(), output["crtc"]["width"], output["crtc"]["height"]))

    elif action == "clear-config":
        if os.access(CONFIGURATION_FILE_PATH, os.R_OK):
            os.unlink(CONFIGURATION_FILE_PATH)

    elif action == "set-config":
        if os.access(CONFIGURATION_FILE_PATH, os.R_OK):
            configurations = { "%s-%d-%d" % (x.edid, x.width, x.height): x for x in unserialize_configurations(open(CONFIGURATION_FILE_PATH, "rb").read()) }
        else:
            configurations = {}

        for configuration in sys.stdin.read().split("\n\n"):
            variables = dict(( x.split("=", 1) for x in shlex.split(configuration) ))
            if not variables:
                continue
            config = Configuration.new_from_shdict(variables)
            config_key = "%s-%d-%d" % (config.edid, config.width, config.height)
            if variables["SPLITS"] == "N":
                if config_key in configurations:
                    del configurations[config_key]
            else:
                configurations[config_key] = config

        configuration_data = serialize_configurations(configurations.values())
        with open(CONFIGURATION_FILE_PATH, "wb") as output:
            output.write(configuration_data)
    else:
        print("fakexrandr manage script\n"
              "Syntax: fakexrandr-manage <gui|dump-config|show-available|clear-config|\n"
              "                           set-config>\n\n"
              "Available commands:\n"
              "  gui\n    Run the GTK based gui\n"
              "  dump-config\n   Dump the configuration file in a parseable format to the console. Different\n"
              "   configurations are separated by an empty line.\n"
              "  show-available\n   Query XRandR and show outputs for which a configuration could be created.\n"
              "  clear-config\n   Remove all stored configurations\n"
              "  set-config\n   Load configurations from the standard input and merge them into the\n"
              "   configuration file\n"
              "\n"
              "Configuration format:\n"
              "  The CLI configuration format follows sh syntax and defines the variables NAME,\n"
              "  EDID, WIDTH, HEIGHT and SPLITS. SPLITS is a string describing how an output\n"
              "  shall be split. It starts by one of the letters H, V or N, describing the\n"
              "  kind of split. H means horizontal, V vertical and N no split. Separated by a\n"
              "  space follows the pixel position of the split. Again separated by a space\n"
              "  follow the two sub-configurations of the left/right or top/bottom halves. Any\n"
              "  additional white-space besides a single space is optional any only serves\n"
              "  better readibility. dump-config indents sub-configurations to this end.\n"
              "  If SPLITS equals N, a configuration is discarded upon saving it.\n"
              "\n")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
    elif HAS_GTK:
        action = "gui"
    else:
        action = "dump-config"

    perform_action(action)
