libXrandr.so: libXrandr.c
	gcc -fPIC -shared -o libXrandr.so libXrandr.c -lX11
	ln -s libXrandr.so libXrandr.so.2 || true

install: libXrandr.so
	install libXrandr.so /usr/local/lib
	ln -s libXrandr.so /usr/local/lib/libXrandr.so.2 || true
	ldconfig
