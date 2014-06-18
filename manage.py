#!/usr/bin/env python
# vim:fdm=marker:fileencoding=utf8
from gi.repository import Gtk, Gdk
import ctypes
import os
import struct
import sys

"""
    This script provides a GUI for fakexrandr configurations



    The configuration is stored in a binary format for efficient reading.

    <file contents> := <store> <file contents>
                     | <store>

    <store>         := <configuration length: 4 bytes unsigned native byte order length of the configuration> <configuration>

    <configuration> := <name of the configuration: 128 characters, zero padded> <edid for configuration: 256 characters> <width: 4 bytes unsigned native byte order> <height: see width> <splits>

    <splits>        := (("H"|"V") <position of the split: see width> <splits> <splits>)
                     | "N"

                        H means horizontal split (position is a y coordinate), V is a vertical split (position is an x coordinate),
                        N means no further splits

    All units are pixels.

    The configuration is stored in ~/.config/fakexrandr.bin.

"""

# TODO The screens are loaded from the first available xrandr library right now, which might be fakexrandr..

" Code to open Xlib via ctypes {{{ "
try:
    libX11 = ctypes.CDLL("libX11.so")
    libXrandr = ctypes.CDLL("libXrandr.so")
except:
    print >> sys.stderr, "Failed to load libX11.so and/or libXrandr.so. Are you running this from linux\n", \
        "and using cpython (or another python with the ctypes extension)?\n"
    sys.exit(1)

libX11.XOpenDisplay.restype = ctypes.c_voidp
display = libX11.XOpenDisplay("")
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
libXrandr.XRRGetCrtcInfo.restype = ctypes.POINTER(XRRCrtcInfo)
libXrandr.XRRListOutputProperties.restype = ctypes.POINTER(ctypes.c_voidp)
libX11.XGetAtomName.restype = ctypes.c_char_p
libX11.XInternAtom.restype = ctypes.c_long

def query_xrandr():
    root_window = libX11.XDefaultRootWindow(display)
    screen_resources = libXrandr.XRRGetScreenResources(display, root_window)

    to_dict = lambda what: dict((x, getattr(out.contents, x)) for x in dir(what.contents) if x[0] != "_")

    edidAtom = libX11.XInternAtom(display, "EDID", 1)

    crtcs = {}
    for i in range(screen_resources.contents.ncrtc):
        out = libXrandr.XRRGetCrtcInfo(display, screen_resources, screen_resources.contents.crtcs[i])
        crtcs[screen_resources.contents.crtcs[i]] = to_dict(out)
        libXrandr.XRRFreeCrtcInfo(out)

    outputs = {}
    for i in range(screen_resources.contents.noutput):
        out = libXrandr.XRRGetOutputInfo(display, screen_resources, screen_resources.contents.outputs[i])

        actual_type = ctypes.c_long()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.c_void_p()
        libXrandr.XRRGetOutputProperty(display, screen_resources.contents.outputs[i], edidAtom,
                                       0, 100, False, False, 0, ctypes.byref(actual_type),
                                       ctypes.byref(actual_format), ctypes.byref(nitems),
                                       ctypes.byref(bytes_after), ctypes.byref(prop))

        if nitems.value > 0:
            outputs[out.contents.name] = to_dict(out)
            outputs[out.contents.name]["edid"] = "".join(( "%02x" % (ctypes.cast(prop.value + i, ctypes.POINTER(ctypes.c_ubyte)).contents.value) for i in range(nitems.value) ))
            outputs[out.contents.name]["crtc"] = crtcs[outputs[out.contents.name]["crtc"]]

        libXrandr.XRRFreeOutputInfo(out)


    libXrandr.XRRFreeScreenResources(screen_resources)

    return outputs
" }}} "

" X Resource database access {{{ "
# TODO
# Storing values here is a pain -- I should either remove this code alltogether and
# switch to a configuration file or invoke the xrdb utility

class XrmValue(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint),
                ("addr", ctypes.c_char_p)]

libX11.XrmGetStringDatabase.restype = ctypes.c_voidp
libX11.XResourceManagerString.restype = ctypes.POINTER(ctypes.c_voidp)

class Xrdb(object):
    _database = False

    def __init__(self):
        if not Xrdb._database:
            libX11.XrmInitialize();
            Xrdb._database = ctypes.c_voidp();
            Xrdb._database.value = libX11.XrmGetStringDatabase(libX11.XResourceManagerString(display));

    def __getitem__(self, name):
        val = XrmValue()
        retval = libX11.XrmGetResource(self._database.value, name, "", ctypes.c_char_p("                   "), ctypes.byref(val))
        if retval != 1:
            raise KeyError
        return val.addr

    def __setitem__(self, name, value):
        state = libX11.XrmPutStringResource(ctypes.byref(self._database), name, str(value))
        if state != 0:
            raise RuntimeError("Failed to store value to XResource database")
        print libX11.XrmSetDatabase(display, self._database)
        # TODO
        # This doesn't store any changes yet

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value
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
    def splits_str(self):
        def _build(arr):
            if not arr:
                return "N"
            return "".join([struct.pack("=cI", arr[0], arr[1]), _build(arr[2]), _build(arr[3])])
        return _build(self.splits)

    @splits_str.setter
    def splits_str(self, istr):
        def _build(istr):
            stype = istr[0]
            if stype == "N":
                return [ ], istr[1:]
            pos, = struct.unpack("I", istr[1:5])
            left, istr = _build(istr[5:])
            right, istr = _build(istr)
            return [ stype, pos, left, right ], istr
        self.splits = _build(istr)[0]

    def get_split_for_point(self, x, y, split=None):
        if split is None:
            split = self.splits
        if not split:
            return [ split ]
        if (y if split[0] == "H" else x) < split[1]:
            return self.get_split_for_point(x, y, split[2]) + [ split ]
        else:
            if split[0] == "H":
                y -= split[1]
            else:
                x -= split[1]
            return self.get_split_for_point(x, y, split[3]) + [ split ]

    @property
    def formatted_name(self):
        return "{c.name}@{c.width}x{c.height}".format(c=self)

    def __eq__(self, other):
        return other.edid == self.edid

    def __str__(self):
        return "".join([struct.pack("128s256sII", self.name, self.edid, self.width, self.height), self.splits_str])

    @classmethod
    def new_from_str(cls, string):
        obj = cls.__new__(cls)
        obj.name, obj.edid, obj.width, obj.height = struct.unpack("128s256sII", string[:128+256+4*2])
        obj.name = obj.name[:obj.name.index("\x00")]
        obj.splits_str = string[128+256+4*2:]
        obj.height = float(obj.height)
        obj.width = float(obj.width)
        return obj

def base_coordinates(splits):
    x = 0
    y = 0
    while len(splits) > 1:
        if splits[1][2] is not splits[0]:
            assert(splits[1][3] is splits[0])
            if splits[1][0] == "H":
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
            if split[0] == "H":
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
            self.set_info("(%d, %d)" % (event.x / 300. * self._configuration.width, event.y / 300. * self._aspect_ratio * self._configuration.height))
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
                    self._mouse_handler_modify_split[0] += [ "H", event.y / 300. * self._aspect_ratio * self._configuration.height - base[1], [], [] ]
                    self._mouse_handler_decision = 1
                elif self._mouse_handler_decision == 2 or (self._mouse_handler_decision != 1 and ydiff > 50):
                    base = base_coordinates(self._mouse_handler_modify_split)
                    self._mouse_handler_modify_split[0] += [ "V", event.x / 300. * self._configuration.width - base[0], [], [] ]
                    self._mouse_handler_decision = 2
            self.queue_draw()

    def canvas_mouse_button_handler(self, state, widget, event):
        if state == 1:
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
                    if target_split[which][0] == "V" and target_split[which][3] is target_split[which - 1]:
                        break
                    which += 1
                self._mouse_handler_alter_in = target_split[which:]
                self._mouse_handler_decision = 3 if button == 1 else 5
            elif len(target_split) > 1 and pos_within_target[1] < 50:
                # (Re)Move top edge
                which = 1
                while True:
                    if target_split[which][0] == "H" and target_split[which][3] is target_split[which - 1]:
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
                replacer = self._mouse_handler_alter_in[0][2]
                while len(self._mouse_handler_alter_in[0]):
                    self._mouse_handler_alter_in[0].pop()
                self._mouse_handler_alter_in[0] += replacer
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
        edid = self._configuration.edid[:10] + "..." + self._configuration.edid[-10:]
        self._info_label.set_markup("<b>{c.name}@{c.width}x{c.height}</b>\nEDID: {shortened_edid}\n\n{text}".format(c=self._configuration, shortened_edid=edid, text=text))


class MainWindow(Gtk.Window):
    def load_displays(self):
        self._displays = query_xrandr()
        self.displays_combo_store.clear()
        self._displays_order = []
        for name, output in self._displays.items():
            verbose_name = "{name}@{crtc[width]}x{crtc[height]} (edid={edidS}...{edidE})".format(name=name, crtc=output["crtc"], edidS=output["edid"][:10], edidE=output["edid"][-10:])
            self.displays_combo_store.append((name, verbose_name))
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
        configurations = []
        for config in self._configurations:
            sconfig = str(config)
            configurations.append(struct.pack("=I", len(sconfig)))
            configurations.append(sconfig)
        return "".join(configurations)

    def load(self, data):
        while data:
            length, = struct.unpack("=I", data[:4])
            self.add_configuration(Configuration.new_from_str(data[4:4+length]))
            data = data[4+length:]

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
                    with open(self.configuration_file_path, "w") as output:
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

        self.configuration_file_path = os.path.expanduser("~/.config/fakexrandr.bin")
        if os.access(self.configuration_file_path, os.R_OK):
            try:
                configuration_data = open(self.configuration_file_path).read()
                self._initial_configuration_data = configuration_data
                self.load(configuration_data)
            except:
                error = Gtk.MessageDialog(self, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE, "Failed to load configuration from ~/.config/fakexrandr.bin")
                error.connect("response", lambda *a: error.destroy())
                error.show()

" }}} "

if __name__ == '__main__':
    wnd = MainWindow()
    wnd.show_all()
    Gtk.main()

# TODO
# · Store values in Xrdb
# · Store values to configuration file (?!)
# · Serialize/Deserialize on load
#
# Thoughts:
# · Let the first application open a socket and serve the configuration to
#   others
# · Do this using fork() and exec() a small daemon that exits with X11
# · Use a standardized socket path for this, with the DISPLAY variable
#   somewhere in the name
#
#  CON: Works only locally, not through SSH.
