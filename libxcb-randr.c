/*
	FakeXRandR
	Copyright (c) 2015, Phillip Berndt

	This is a replacement library for libxcb-randr.so. It replaces configurable
	outputs with multiple sub-outputs.
*/

#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <stdio.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>

#include "fakexrandr.h"

/*
	The skeleton file is created by ./make_skeleton.py

	It contains wrappers around all xcb_randr_ functions which are not
	explicitly defined in this C file, replacing all references to crtcs and
	outputs which are fake with the real ones.
*/
#include "skeleton-xcb.h"

static void _init() __attribute__((constructor));
static void _init() {
	void *xrandr_lib = dlopen(REAL_XCB_RANDR_LIB, RTLD_LAZY | RTLD_GLOBAL);

	/*
		The following macro is defined by the skeleton header. It initializes
		static variables called _xcb_randr_ with references to the real
		xcb_randr_ functions.
	*/
	FUNCTION_POINTER_INITIALIZATIONS;
}

/*
	Overridden library functions to add the fake output
*/

xcb_randr_get_screen_resources_cookie_t xcb_randr_get_screen_resources(xcb_connection_t *c, xcb_window_t window) {
	printf("Get screen resources\n");
	return _xcb_randr_get_screen_resources(c, window);
}

xcb_randr_get_screen_resources_cookie_t xcb_randr_get_screen_resources_unchecked(xcb_connection_t *c, xcb_window_t window) {
	printf("Get screen resources unchecked\n");
	return _xcb_randr_get_screen_resources_unchecked(c, window);
}

xcb_randr_get_screen_resources_reply_t *xcb_randr_get_screen_resources_reply(xcb_connection_t *c,
		xcb_randr_get_screen_resources_cookie_t cookie, xcb_generic_error_t **e) {

	printf("Get screen resources reply\n");
	return _xcb_randr_get_screen_resources_reply(c, cookie, e);
}



xcb_randr_get_output_info_cookie_t xcb_randr_get_output_info(xcb_connection_t *c,
		xcb_randr_output_t output, xcb_timestamp_t config_timestamp) {
	printf("Get output info\n");
	return _xcb_randr_get_output_info(c, output, config_timestamp);
}

xcb_randr_get_output_info_cookie_t xcb_randr_get_output_info_unchecked(xcb_connection_t *c,
		xcb_randr_output_t output,
		xcb_timestamp_t config_timestamp) {

	printf("Get output info unchecked\n");
	return _xcb_randr_get_output_info_unchecked(c, output, config_timestamp);
}

xcb_randr_get_output_info_reply_t * xcb_randr_get_output_info_reply(xcb_connection_t *c,
		xcb_randr_get_output_info_cookie_t cookie, xcb_generic_error_t **e ) {

	printf("Get output info reply\n");
	return _xcb_randr_get_output_info_reply(c, cookie, e);
}

xcb_randr_get_crtc_info_cookie_t xcb_randr_get_crtc_info(xcb_connection_t *c, xcb_randr_crtc_t crtc, xcb_timestamp_t config_timestamp ) {

	printf("Get crtc info\n");
	return _xcb_randr_get_crtc_info(c, crtc, config_timestamp);
}

xcb_randr_get_crtc_info_cookie_t xcb_randr_get_crtc_info_unchecked(xcb_connection_t *c, xcb_randr_crtc_t crtc, xcb_timestamp_t config_timestamp ) {
	printf("Get crtc info unchecked\n");
	return _xcb_randr_get_crtc_info_unchecked(c, crtc, config_timestamp);
}

xcb_randr_get_crtc_info_reply_t * xcb_randr_get_crtc_info_reply(xcb_connection_t *c, xcb_randr_get_crtc_info_cookie_t cookie, xcb_generic_error_t **e ) {
	printf("Get crtc info reply\n");
	return _xcb_randr_get_crtc_info_reply(c, cookie, e);
}
