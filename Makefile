PREFIX=/usr
CFLAGS=-O2

ifeq ($(shell pkg-config --errors-to-stdout --print-errors xcb-randr),)
	XCB_TARGET=libxcb-randr.so.0
endif

all: libXrandr.so.2 libXinerama.so.1 $(XCB_TARGET)

config.h: configure
	./configure

skeleton-xrandr.h: make_skeleton.py
	./make_skeleton.py X11/extensions/Xrandr.h XRR libXrandr.c RRCrtc,RROutput > $@ || { rm -f $@; exit 1; }

skeleton-xcb.h: make_skeleton.py
	./make_skeleton.py xcb/randr.h xcb_randr_ libxcb-randr.c xcb_randr_output_t,xcb_randr_crtc_t > $@ || { rm -f $@; exit 1; }

libXrandr.so: libXrandr.c config.h skeleton-xrandr.h
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $< -ldl

libxcb-randr.so: libxcb-randr.c config.h skeleton-xcb.h
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $< -ldl

libXinerama.so.1 libXrandr.so.2: libXrandr.so
	[ -e $@ ] || ln -s $< $@

libxcb-randr.so.0: libxcb-randr.so
	[ -e $@ ] || ln -s $< $@


install: libXrandr.so
	TARGET_DIR=`sed -nre 's/#define FAKEXRANDR_INSTALL_DIR "([^"]+)"/\1/p' config.h`; \
	[ -d $$TARGET_DIR ] || exit 1; \
	install libXrandr.so $$TARGET_DIR; \
	ln -s libXrandr.so $$TARGET_DIR/libXrandr.so.2 || true; \
	ln -s libXrandr.so $$TARGET_DIR/libXinerama.so.1 || true; \
	ldconfig
	install fakexrandr-manage.py $(PREFIX)/bin/fakexrandr-manage

uninstall: config.h
	TARGET_DIR=`sed -nre 's/#define FAKEXRANDR_INSTALL_DIR "([^"]+)"/\1/p' config.h`; \
	[ -d $$TARGET_DIR ] || exit 1; \
	strings $$TARGET_DIR/libXrandr.so | grep -q _is_fake_xrandr || exit 1; \
	rm -f $$TARGET_DIR/libXrandr.so $$TARGET_DIR/libXrandr.so.2 $$TARGET_DIR/libXinerama.so.1 $(PREFIX)/bin/fakexrandr-manage; \
	ldconfig

clean:
	rm -f libXrandr.so libxcb-randr.so libXrandr.so.2 libXinerama.so.1 $(XCB_TARGET) config.h skeleton-xcb.h skeleton-xrandr.h
