all: libXrandr.so

config.h:
	./configure

libXrandr.so: libXrandr.c config.h
	gcc -fPIC -shared -o libXrandr.so libXrandr.c
	ln -s libXrandr.so libXrandr.so.2 || true

install: libXrandr.so config.h
	TARGET_DIR=`sed -nre 's/#define FAKEXRANDR_INSTALL_DIR "([^"]+)"/\1/p' config.h`; \
	echo $$TARGET_DIR; \
	[ -d $$TARGET_DIR ] || exit 1; \
	install libXrandr.so $$TARGET_DIR; \
	ln -s libXrandr.so $$TARGET_DIR/libXrandr.so.2 || true; \
	ldconfig

clean:
	rm -f libXrandr.so libXrandr.so.2 config.h
