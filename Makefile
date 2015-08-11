PREFIX=/usr
CFLAGS=-O2

all: libXrandr.so.2 libXinerama.so.1

config.h: configure
	./configure

skeleton.h: make_skeleton.py
	./make_skeleton.py > $@ || { rm -f skeleton.h; exit 1; }

libXrandr.so: libXrandr.c config.h skeleton.h
	$(CC) $(CFLAGS) -fPIC -shared -o $@ $< -ldl

libXinerama.so.1 libXrandr.so.2: libXrandr.so
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
	rm -f libXrandr.so libXrandr.so.2 libXinerama.so.1 config.h skeleton.h
