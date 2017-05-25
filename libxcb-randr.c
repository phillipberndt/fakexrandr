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

#include <xcb/xcb.h>
#include <xcb/randr.h>

#include "fakexrandr.h"

/*
	The skeleton file is created by ./make_skeleton.py

	It contains wrappers around all xcb_randr_ functions which are not
	explicitly defined in this C file, replacing all references to crtcs and
	outputs which are fake with the real ones.
*/
#include "skeleton-xcb.h"

/*
	We use an augmented version of the screen resources to store all our
	information: We preallocate all XRROutputInfo and XRRCrtcInfo structures
	for the fake screens upon a request for screen resources and only return
	pointers in the functions that return them.
*/
struct FakeInfo {
	uint32_t xid; // typeof xcb_randr_crtc_t, xcb_randr_output_t, xcb_randr_mode_t
	uint32_t parent_xid;
	void * info;
	struct FakeInfo * next;
};

/*
struct FakeScreenResources {
	// This is crafted to look like a XRRScreenResources to an unaware user
	XRRScreenResources res;

	// This points to the original screen resources. We don't free them to
	// be able to use the original strings/lists without having to copy them.
	XRRScreenResources *parent_res;

	// These lists point to the fake OutputInfo/CrtcInfo/Mode structures
	struct FakeInfo *fake_crtcs;
	struct FakeInfo *fake_outputs;
	struct FakeInfo *fake_modes;
};
*/

/*
	Configuration management

	The configuration file format is documented in the management script. These
	functions load the configuration file and fill the FakeInfo lists with
	information on the fake outputs.
*/

static char * _config_foreach_split(char * config, unsigned int * n, unsigned int x, unsigned int y, unsigned int width,
        unsigned int height, xcb_randr_get_screen_resources_current_reply_t * screen_resources,
        xcb_randr_output_t output, xcb_randr_get_output_info_reply_t * output_info,
        xcb_randr_get_crtc_info_reply_t * crtc_info, xcb_randr_crtc_t *** fake_crtcs,
        xcb_randr_output_t *** fake_outputs, xcb_randr_mode_info_t *** fake_mode_infos) {

	if (config[0] == 'N') {
		// Define a new output info
		**fake_outputs = malloc(sizeof(struct FakeInfo) + sizeof(xcb_randr_output_info_t) + output_info->nameLen + sizeof("~NNN ") + sizeof(RRCrtc) + sizeof(RROutput) * output_info->nclone + (1 + output_info->nmode) * sizeof(RRMode));
		(**fake_outputs)->xid = (output & ~XID_SPLIT_MASK) | ((++(*n)) << XID_SPLIT_SHIFT);
		(**fake_outputs)->parent_xid = output;
		XRROutputInfo *fake_info = (**fake_outputs)->info = (void*)**fake_outputs + sizeof(struct FakeInfo);
		fake_info->timestamp = output_info->timestamp;
		fake_info->name = (void*)fake_info + sizeof(XRROutputInfo);
		fake_info->nameLen = sprintf(fake_info->name, "%s~%d", output_info->name, (*n));
		fake_info->mm_width = output_info->mm_width * width / crtc_info->width;
		fake_info->mm_height = output_info->mm_height * height / crtc_info->height;
		fake_info->connection = output_info->connection;
		fake_info->subpixel_order = output_info->subpixel_order;
		fake_info->ncrtc = 1;
		fake_info->crtcs = (void*)fake_info->name + output_info->nameLen + sizeof("~NNN ");
		fake_info->nclone = output_info->nclone;
		fake_info->clones = (void*)fake_info->crtcs + sizeof(RRCrtc);
		int i;
		for(i=0; i<fake_info->nclone; i++) {
			fake_info->clones[i] = (output_info->clones[i] & ~XID_SPLIT_MASK) | ((*n) << XID_SPLIT_SHIFT);
		}
		fake_info->nmode = 1 + output_info->nmode;
		fake_info->npreferred = 0;
		fake_info->modes = (void*)fake_info->clones + fake_info->nclone * sizeof(RROutput);
		fake_info->crtc = *fake_info->crtcs = *fake_info->modes = (output_info->crtc & ~XID_SPLIT_MASK) | ((*n) << XID_SPLIT_SHIFT);
		memcpy(fake_info->modes + 1, output_info->modes, sizeof(RRMode) * output_info->nmode);

		*fake_outputs = &(**fake_outputs)->next;
		**fake_outputs = NULL;

		// Define a new CRTC info
		**fake_crtcs = malloc(sizeof(struct FakeInfo) + sizeof(XRRCrtcInfo) + sizeof(RROutput));
		(**fake_crtcs)->xid = (output_info->crtc & ~XID_SPLIT_MASK) | ((*n) << XID_SPLIT_SHIFT);
		(**fake_crtcs)->parent_xid = output_info->crtc;
		XRRCrtcInfo *fake_crtc_info = (**fake_crtcs)->info = ((void*)**fake_crtcs) + sizeof(struct FakeInfo);
		*fake_crtc_info = *crtc_info;
		fake_crtc_info->x = crtc_info->x + x;
		fake_crtc_info->y = crtc_info->y + y;
		fake_crtc_info->width = width;
		fake_crtc_info->height = height;
		fake_crtc_info->mode = *(fake_info->modes);
		fake_crtc_info->noutput = 1;
		fake_crtc_info->outputs = (void*)fake_crtc_info + sizeof(XRRCrtcInfo);
		*(fake_crtc_info->outputs) = (output & ~XID_SPLIT_MASK) | (((*n)) << XID_SPLIT_SHIFT);
		fake_crtc_info->npossible = 1;
		fake_crtc_info->possible = fake_crtc_info->outputs;

		*fake_crtcs = &(**fake_crtcs)->next;
		**fake_crtcs = NULL;

		// Define a new fake mode
		**fake_modes = calloc(1, sizeof(struct FakeInfo) + sizeof(XRRModeInfo) + sizeof("XXXXxXXXX"));
		(**fake_modes)->xid = (output_info->crtc & ~XID_SPLIT_MASK) | ((*n) << XID_SPLIT_SHIFT);
		(**fake_modes)->parent_xid = 0;
		XRRModeInfo *fake_mode_info = (**fake_modes)->info = (void*)**fake_modes + sizeof(struct FakeInfo);
		for(i=0; i<resources->nmode; i++) {
			if(resources->modes[i].id == crtc_info->mode) {
				*fake_mode_info = resources->modes[i];
				break;
			}
		}
		fake_mode_info->id = (**fake_modes)->xid;
		fake_mode_info->width = width;
		fake_mode_info->height = height;
		fake_mode_info->name = (void*)fake_mode_info + sizeof(XRRModeInfo);
		fake_mode_info->nameLength = sprintf(fake_mode_info->name, "%dx%d", width, height);

		*fake_modes = &(**fake_modes)->next;
		**fake_modes = NULL;
        */

		return config + 1;
	}
	unsigned int split_pos = *(unsigned int *)&config[1];
	if(config[0] == 'H') {
		config = _config_foreach_split(config + 1 + 4, n, x, y, width, split_pos, screen_resources, output, output_info, crtc_info);
		return _config_foreach_split(config, n, x, y + split_pos, width, height - split_pos, screen_resources, output, output_info, crtc_info);
	}
	else {
		assert(config[0] == 'V');

		config = _config_foreach_split(config + 1 + 4, n, x, y, split_pos, height, screen_resources, output, output_info, crtc_info);
		return _config_foreach_split(config, n, x + split_pos, y, width - split_pos, height, screen_resources, output, output_info, crtc_info);
	}
}

// (nms): this is now specific to the `RRGetScreenResourcesCurrent` request, not both it and `RRGetScreenResources`
static int config_handle_output(xcb_connection_t * c, xcb_randr_get_screen_resources_current_reply_t * screen_resources,
        xcb_randr_output_t output, char * target_edid, xcb_randr_crtc_t *** fake_crtcs,
        xcb_randr_output_t *** fake_outputs, xcb_randr_mode_info_t *** fake_mode_infos) {
    char * config;
    for (config = config_file; (int)(config - config_file) <= (int)config_file_size; ) {
        // Walk through the configuration file and search for the target_edid
        unsigned int size = *(unsigned int *)config;
        char * name = &config[4];
        char * edid = &config[4 + 128];
        unsigned int width = *(unsigned int *)&config[4 + 128 + 768];
        unsigned int height = *(unsigned int *)&config[4 + 128 + 768 + 4];
        unsigned int count = *(unsigned int *)&config[4 + 128 + 768 + 4 + 4];

        if (strncmp(edid, target_edid, 768) == 0) {
            xcb_randr_get_output_info_cookie_t output_info_cookie = xcb_randr_get_output_info(c, output,
                    screen_resources->config_timestamp);
            xcb_randr_get_output_info_reply_t * output_info = xcb_randr_get_output_info_reply(c, output_info_cookie,
                    NULL); // TODO(nms): error handling

            xcb_randr_get_crtc_info_cookie_t crtc_info_cookie = xcb_randr_get_crtc_info(c, output_info->crtc,
                    screen_resources->config_timestamp);
            xcb_randr_get_crtc_info_reply_t * crtc_info = xcb_randr_get_crtc_info_reply(c, crtc_info_cookie, NULL);
                    // TODO(nms): error handling

            if (crtc_info->width == (int)width && crtc_info->height == (int)height) {
                // If it is found and the size matches, add fake outputs/crtcs to the list
                int n = 0;
                _config_foreach_split(config + 4 + 128 + 768 + 4 + 4 + 4, &n, 0, 0, width, height, screen_resources, output, output_info, crtc_info, fake_crtcs, fake_outputs, fake_mode_infos);
                return 1;
            }

            free(output_info);
            free(crtc_info);
        }

        config += 4 + size;
    }

    return 0;
}

/*
	Helper function to return a hex-coded EDID string for a given output

	edid must point to a sufficiently large (768 bytes) buffer.
*/

static int get_output_edid(xcb_connection_t * c, xcb_randr_output_t output, char * edid) {
    xcb_intern_atom_cookie_t edid_atom_cookie = xcb_intern_atom(c, 1, 4, "EDID"); // 4 == strlen("EDID")
    xcb_intern_atom_reply_t * edid_atom = xcb_intern_atom_reply(c, edid_atom_cookie, NULL); // TODO(nms): error handling

	xcb_randr_get_output_property_cookie_t edid_prop_cookie = xcb_randr_get_output_property(c, output, edid_atom->atom, 0, 0, 384, 0, 0);
    xcb_randr_get_output_property_reply_t * edid_prop = xcb_randr_get_output_property_reply(c, edid_prop_cookie, NULL); // TODO(nms): error handling

    // EDID property is 8 bits (format = 8), according to protocol spec, num_items and xcb's length methods work equally
	if (edid_prop->num_items > 0) {
        int8_t * prop = xcb_randr_get_output_property_data(edid_prop);
        
		int i;
		for (i = 0; i < xcb_randr_get_output_property_data_length(edid_prop); i++) {
			edid[2*i] = ((prop[i] >> 4) & 0xf) + '0';
			if (edid[2*i] > '9') {
				edid[2*i] += 'a' - '0' - 10;
			}

			edid[2*i+1] = (prop[i] & 0xf) + '0';
			if (edid[2*i+1] > '9') {
				edid[2*i+1] += 'a' - '0' - 10;
			}
		}
		edid[xcb_randr_get_output_property_data_length(edid_prop)*2] = 0; // (nms): overflow? what's going on with the edid buffer?

		free(edid_prop);
	}

    free(edid_atom);

    // (nms): why multiply by 2?  why num_items based return value at all?
	return edid_prop->num_items * 2;
}

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

xcb_randr_get_screen_resources_current_reply_t * xcb_randr_get_screen_resources_current_reply(xcb_connection_t * c,
		xcb_randr_get_screen_resources_current_cookie_t cookie, xcb_generic_error_t ** e) {

    xcb_randr_get_screen_resources_current_reply_t * screen_resources =
        _xcb_randr_get_screen_resources_current_reply(c, cookie, e);

	if (open_configuration()) {
        return screen_resources;
    }


    xcb_generic_iterator_t prev = xcb_randr_get_screen_resources_current_crtcs_end(screen_resources);
    printf("prev.data: %p\nprev.index: %d\npad: %d", prev.data, prev.index, XCB_TYPE_PAD(xcb_randr_output_t, prev.index) + 0);
    //(xcb_randr_output_t *) ((char *) prev.data + XCB_TYPE_PAD(xcb_randr_output_t, prev.index) + 0);


    // augment reply as necessary from configuration
    
	xcb_randr_output_t * fake_outputs = NULL;
	xcb_randr_crtc_t * fake_crtcs = NULL;
	xcb_randr_mode_info_t * fake_mode_infos = NULL;

	xcb_randr_output_t ** fake_outputs_end = &fake_outputs;
	xcb_randr_crtc_t ** fake_crtcs_end = &fake_crtcs;
	xcb_randr_mode_info_t ** fake_mode_infos_end = &fake_mode_infos;

    xcb_randr_output_t * outputs = xcb_randr_get_screen_resources_current_outputs(screen_resources);

    // use fn for length, rather than reply->num_outputs, just to be safe
    int i;
    for (i = 0; i < xcb_randr_get_screen_resources_current_outputs_length(screen_resources); ++i) {
        xcb_randr_output_t * output = &outputs[i];
        char output_edid[768];
        if (get_output_edid(c, *output, output_edid) > 0) {
            config_handle_output(c, screen_resources, *output, output_edid, &fake_crtcs_end, &fake_outputs_end,
                    &fake_mode_infos_end);
        }
    }

	return screen_resources;
}

xcb_randr_get_screen_resources_reply_t *xcb_randr_get_screen_resources_reply(xcb_connection_t *c,
        xcb_randr_get_screen_resources_cookie_t cookie, xcb_generic_error_t **e) {

	printf("Get screen resources reply\n");
	return _xcb_randr_get_screen_resources_reply(c, cookie, e);
}

xcb_randr_get_output_info_reply_t * xcb_randr_get_output_info_reply(xcb_connection_t *c,
		xcb_randr_get_output_info_cookie_t cookie, xcb_generic_error_t **e ) {

	printf("Get output info reply\n");
	return _xcb_randr_get_output_info_reply(c, cookie, e);
}

xcb_randr_get_crtc_info_reply_t * xcb_randr_get_crtc_info_reply(xcb_connection_t *c, xcb_randr_get_crtc_info_cookie_t cookie, xcb_generic_error_t **e ) {
	printf("Get crtc info reply\n");
	return _xcb_randr_get_crtc_info_reply(c, cookie, e);
}
