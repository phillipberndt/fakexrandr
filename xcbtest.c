/* compile with

	gcc -oxcbtest xcbtest.c -lxcb -lxcb-randr -lX11 -lXrandr

*/

#include <xcb/xcb.h>
#include <xcb/randr.h>
#include <X11/extensions/Xrandr.h>
#include <X11/Xlibint.h>
#include <stdio.h>

int main() {
	xcb_connection_t *connection = xcb_connect(NULL, NULL);
	const xcb_setup_t *setup = xcb_get_setup (connection);
	xcb_screen_iterator_t iter = xcb_setup_roots_iterator (setup);
	xcb_screen_t *screen = iter.data;
	xcb_randr_get_screen_resources_current_cookie_t screen_res_c = xcb_randr_get_screen_resources_current(connection, screen->root);
	xcb_randr_get_screen_resources_current_reply_t *screen_res_r = xcb_randr_get_screen_resources_current_reply(connection, screen_res_c, NULL);

	Display *dpl = XOpenDisplay(":0");
	XRRScreenResources *res = XRRGetScreenResourcesCurrent(dpl, XDefaultRootWindow(dpl));

	printf("num outputs from xlib: %d\n", res->noutput);
	printf("num outputs from xcb:  %d\n", screen_res_r->num_outputs);
}
