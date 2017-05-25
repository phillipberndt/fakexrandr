/*
	FakeXRandR
	Copyright (c) 2015, Phillip Berndt

	This is a replacement library for libXrandr.so and, optionally,
	libXinerama.so. It replaces configurable outputs with multiple
	sub-outputs.
*/

#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <X11/extensions/Xrandr.h>
#include <X11/extensions/Xinerama.h>
#include <X11/Xlib.h>
#include <X11/Xlibint.h>
#include <stdlib.h>
#include <stdbool.h>
#include <assert.h>
#include <string.h>

#include "fakexrandr.h"

/*
	The skeleton file is created by ./make_skeleton.py

	It contains wrappers around all Xrandr functions which are not
	explicitly defined in this C file, replacing all references to
	crtcs and outputs which are fake with the real ones.
*/
#include "skeleton-xrandr.h"

/*
	We use an augmented version of the screen resources to store all our
	information: We preallocate all XRROutputInfo and XRRCrtcInfo structures
	for the fake screens upon a request for screen resources and only return
	pointers in the functions that return them.
*/
struct FakeInfo {
	XID xid;
	XID parent_xid;
	void *info;
	struct FakeInfo *next;
};

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

/*
	Configuration management

	The configuration file format is documented in the management script. These
	functions load the configuration file and fill the FakeInfo lists with
	information on the fake outputs.
*/

static char *_config_foreach_split(char *config, unsigned int *n, unsigned int x, unsigned int y, unsigned int width, unsigned int height, XRRScreenResources *resources, RROutput output, XRROutputInfo *output_info,
		XRRCrtcInfo *crtc_info, struct FakeInfo ***fake_crtcs, struct FakeInfo ***fake_outputs, struct FakeInfo ***fake_modes) {

	if(config[0] == 'N') {
		// Define a new output info
		**fake_outputs = Xmalloc(sizeof(struct FakeInfo) + sizeof(XRROutputInfo) + output_info->nameLen + sizeof("~NNN ") + sizeof(RRCrtc) + sizeof(RROutput) * output_info->nclone + (1 + output_info->nmode) * sizeof(RRMode));
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
		**fake_crtcs = Xmalloc(sizeof(struct FakeInfo) + sizeof(XRRCrtcInfo) + sizeof(RROutput));
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
		**fake_modes = Xcalloc(1, sizeof(struct FakeInfo) + sizeof(XRRModeInfo) + sizeof("XXXXxXXXX"));
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

		return config + 1;
	}
	unsigned int split_pos = *(unsigned int *)&config[1];
	if(config[0] == 'H') {
		config = _config_foreach_split(config + 1 + 4, n, x, y, width, split_pos, resources, output, output_info, crtc_info, fake_crtcs, fake_outputs, fake_modes);
		return _config_foreach_split(config, n, x, y + split_pos, width, height - split_pos, resources, output, output_info, crtc_info, fake_crtcs, fake_outputs, fake_modes);
	}
	else {
		assert(config[0] == 'V');

		config = _config_foreach_split(config + 1 + 4, n, x, y, split_pos, height, resources, output, output_info, crtc_info, fake_crtcs, fake_outputs, fake_modes);
		return _config_foreach_split(config, n, x + split_pos, y, width - split_pos, height, resources, output, output_info, crtc_info, fake_crtcs, fake_outputs, fake_modes);
	}
}

static int config_handle_output(Display *dpy, XRRScreenResources *resources, RROutput output, char *target_edid, struct FakeInfo ***fake_crtcs, struct FakeInfo ***fake_outputs, struct FakeInfo ***fake_modes) {
	char *config;
	for(config = config_file; (int)(config - config_file) <= (int)config_file_size; ) {
		// Walk through the configuration file and search for the target_edid
		unsigned int size = *(unsigned int *)config;
		// char *name = &config[4];
		char *edid = &config[4 + 128];
		unsigned int width = *(unsigned int *)&config[4 + 128 + 768];
		unsigned int height = *(unsigned int *)&config[4 + 128 + 768 + 4];
		// unsigned int count = *(unsigned int *)&config[4 + 128 + 768 + 4 + 4];

		if(strncmp(edid, target_edid, 768) == 0) {
			XRROutputInfo *output_info = _XRRGetOutputInfo(dpy, resources, output);
			if(!output_info || output_info->crtc == 0) {
				return 0;
			}

			XRRCrtcInfo *output_crtc = _XRRGetCrtcInfo(dpy, resources, output_info->crtc);
			if(!output_crtc) {
				return 0;
			}

			if(output_crtc->width == (unsigned)width && output_crtc->height == (unsigned)height) {
				// If it is found and the size matches, add fake outputs/crtcs to the list
				unsigned n = 0;
				_config_foreach_split(config + 4 + 128 + 768 + 4 + 4 + 4, &n, 0, 0, width, height, resources, output, output_info, output_crtc, fake_crtcs, fake_outputs, fake_modes);
				return 1;
			}
		}

		config += 4 + size;
	}

	return 0;
}

/*
	Helper function to return a hex-coded EDID string for a given output

	edid must point to a sufficiently large (768 bytes) buffer.
*/
static int get_output_edid(Display *dpy, RROutput output, char *edid) {
	Atom actual_type;
	int actual_format;
	unsigned long nitems;
	unsigned long bytes_after;
	unsigned char *prop;

	_XRRGetOutputProperty(dpy, output, XInternAtom(dpy, "EDID", 1), 0, 384,
			0, 0, 0, &actual_type, &actual_format, &nitems, &bytes_after, &prop);

	if(nitems > 0) {
		unsigned i;
		for(i=0; i<nitems; i++) {
			edid[2*i] = ((prop[i] >> 4) & 0xf) + '0';
			if(edid[2*i] > '9') {
				edid[2*i] += 'a' - '0' - 10;
			}

			edid[2*i+1] = (prop[i] & 0xf) + '0';
			if(edid[2*i+1] > '9') {
				edid[2*i+1] += 'a' - '0' - 10;
			}
		}
		edid[nitems*2] = 0;

		XFree(prop);
	}

	return nitems * 2;
}

/*
	Helper functions for the FakeInfo list structure
*/
static int list_length(struct FakeInfo *list) {
	int i = 0;
	while(list) {
		list = list->next;
		i += 1;
	}
	return i;
}

static void free_list(struct FakeInfo *list) {
	while(list) {
		struct FakeInfo *last = list;
		list = list->next;
		Xfree(last);
	}
}

static struct FakeInfo *xid_in_list(struct FakeInfo *list, XID xid) {
	while(list) {
		if(list->xid == xid || list->parent_xid == xid) return list;
		list = list->next;
	}
	return NULL;
}

/*
	The following function augments the original XRRScreenResources with the
	fake outputs
*/
static struct FakeScreenResources *augment_resources(Display *dpy, XRRScreenResources *res) {
	struct FakeInfo *outputs = NULL;
	struct FakeInfo *crtcs = NULL;
	struct FakeInfo *modes = NULL;

	struct FakeInfo **outputs_end = &outputs;
	struct FakeInfo **crtcs_end = &crtcs;
	struct FakeInfo **modes_end = &modes;

	// Fill the FakeInfo structures
	if(open_configuration()) {
		struct FakeScreenResources *retval = Xcalloc(1, sizeof(struct FakeScreenResources));
		retval->res = *res;
		retval->parent_res = res;
		return retval;
	}

	int i;
	for(i=0; i<res->noutput; i++) {
		char output_edid[768];
		if(get_output_edid(dpy, res->outputs[i], output_edid) > 0) {
			config_handle_output(dpy, res, res->outputs[i], output_edid, &crtcs_end, &outputs_end, &modes_end);
		}
	}

	int ncrtc = res->ncrtc + list_length(crtcs);
	int noutput = res->noutput + list_length(outputs);
	int nmodes = res->nmode + list_length(modes);

	// Create a new XRRScreenResources with the fake information in place
	struct FakeScreenResources *retval = Xmalloc(sizeof(struct FakeScreenResources) + ncrtc * sizeof(RRCrtc) + noutput * sizeof(RROutput) + nmodes * sizeof(XRRModeInfo));

	retval->res = *res;
	retval->parent_res = res;
	retval->fake_crtcs = crtcs;
	retval->fake_outputs = outputs;

	// We copy all the original CRTCs and add our fake ones
	retval->res.ncrtc = ncrtc;
	retval->res.crtcs = (void*)retval + sizeof(struct FakeScreenResources);
	memcpy(retval->res.crtcs, res->crtcs, sizeof(RRCrtc) * res->ncrtc);
	RRCrtc *next_crtc = (void*)retval->res.crtcs + sizeof(RRCrtc) * res->ncrtc;
	struct FakeInfo *tcrtc;
	for(tcrtc = crtcs; tcrtc; tcrtc = tcrtc->next) {
		*next_crtc = tcrtc->xid;
		next_crtc++;
	}

	// We copy the outputs that were not overridden and add our fake ones
	retval->res.noutput = 0;
	retval->res.outputs = (void*)retval->res.crtcs + sizeof(RRCrtc) * ncrtc;
	RROutput *next_output = retval->res.outputs;
	for(i=0; i<res->noutput; i++) {
		if(xid_in_list(outputs, res->outputs[i])) {
			struct FakeInfo *toutput;
			for(toutput=outputs; toutput; toutput = toutput->next) {
				if((toutput->xid & ~XID_SPLIT_MASK) == res->outputs[i]) {
					*next_output = toutput->xid;
					next_output++;
					retval->res.noutput++;
				}
			}
		}
		else {
			*next_output = res->outputs[i];
			next_output++;
			retval->res.noutput++;
		}
	}

	// We copy all the original modes and add our fake ones
	retval->res.nmode = nmodes;
	retval->res.modes = (void*)retval->res.outputs + sizeof(RROutput) * noutput;
	memcpy(retval->res.modes, res->modes, res->nmode * sizeof(XRRModeInfo));
	XRRModeInfo *next_mode = (void*)retval->res.modes + res->nmode * (sizeof(XRRModeInfo));
	struct FakeInfo *tmode;
	for(tmode = modes; tmode; tmode = tmode->next) {
		*next_mode = *(XRRModeInfo *)tmode->info;
		next_mode++;
	}
	retval->fake_modes = modes;

	return retval;
}

static void _init() __attribute__((constructor));
static void _init() {
	void *xrandr_lib = dlopen(REAL_XRANDR_LIB, RTLD_LAZY | RTLD_GLOBAL);

	/*
		The following macro is defined by the skeleton header. It initializes
		static variables called _XRRfn with references to the real XRRfn
		functions.
	*/
	FUNCTION_POINTER_INITIALIZATIONS;
}

/*
	Overridden library functions to add the fake output
*/

XRRScreenResources *XRRGetScreenResources(Display *dpy, Window window) {
	// Create a screen resources copy augmented with fake outputs & crtcs
	XRRScreenResources *res = _XRRGetScreenResources(dpy, window);
	struct FakeScreenResources *retval = augment_resources(dpy, res);
	return (XRRScreenResources *)retval;
}

void XRRFreeScreenResources(XRRScreenResources *resources) {
	struct FakeScreenResources *res = (void *)resources;

	_XRRFreeScreenResources(res->parent_res);
	free_list(res->fake_crtcs);
	free_list(res->fake_outputs);
	free_list(res->fake_modes);
	Xfree(resources);
}

XRRScreenResources *XRRGetScreenResourcesCurrent(Display *dpy, Window window) {
	XRRScreenResources *res = _XRRGetScreenResourcesCurrent(dpy, window);
	struct FakeScreenResources *retval = augment_resources(dpy, res);
	return (XRRScreenResources *)retval;
}

XRROutputInfo *XRRGetOutputInfo(Display *dpy, XRRScreenResources *resources, RROutput output) {
	struct FakeInfo *fake = xid_in_list(((struct FakeScreenResources *)resources)->fake_outputs, output);
	if(fake) {
		// We have to *clone* this here to mitigate issues due to the Gnome folks misusing the API, see
		// gnome bugzilla #755934
		XRROutputInfo *retval = Xmalloc(sizeof(XRROutputInfo));
		memcpy(retval, fake->info, sizeof(XRROutputInfo));
		return retval;
	}

	XRROutputInfo *retval = _XRRGetOutputInfo(dpy, resources, output & ~XID_SPLIT_MASK);
	return retval;
}

void XRRFreeOutputInfo(XRROutputInfo *outputInfo) {
	// Note: If I can ever remove the cloning of the XRROutputInfo above, this won't work anymore!
	_XRRFreeOutputInfo(outputInfo);
}

XRRCrtcInfo *XRRGetCrtcInfo(Display *dpy, XRRScreenResources *resources, RRCrtc crtc) {
	struct FakeInfo *fake = xid_in_list(((struct FakeScreenResources *)resources)->fake_crtcs, crtc);
	if(fake) {
		// We have to *clone* this here to mitigate issues due to the Gnome folks misusing the API, see
		// gnome bugzilla #755934
		XRRCrtcInfo *retval = Xmalloc(sizeof(XRRCrtcInfo));
		memcpy(retval, fake->info, sizeof(XRRCrtcInfo));
		return retval;
	}

	XRRCrtcInfo *retval = _XRRGetCrtcInfo(dpy, resources, crtc & ~XID_SPLIT_MASK);
	return retval;
}

void XRRFreeCrtcInfo(XRRCrtcInfo *crtcInfo) {
	// Note: If I can ever remove the cloning of the XRROutputInfo above, this won't work anymore!
	_XRRFreeCrtcInfo(crtcInfo);
}

int XRRSetCrtcConfig(Display *dpy, XRRScreenResources *resources, RRCrtc crtc, Time timestamp, int x, int y, RRMode mode, Rotation rotation, RROutput *outputs, int noutputs) {
	if(crtc & XID_SPLIT_MASK) {
		return 0;
	}
	int i;
	for(i=0; i<noutputs; i++) {
		if(outputs[i] & XID_SPLIT_MASK) {
			return 0;
		}
	}

	return _XRRSetCrtcConfig(dpy, resources, crtc, timestamp, x, y, mode, rotation, outputs, noutputs);
}

/*
	Fake Xinerama

	This is little overhead with all the work we already did above..
*/
#ifndef NO_FAKE_XINERAMA
Bool XineramaQueryExtension(Display *dpy, int *event_base, int *error_base) {
	return xTrue;
}
Bool XineramaIsActive(Display *dpy) {
	return xTrue;
}
Status XineramaQueryVersion(Display *dpy, int *major, int *minor) {
	*major = 1;
	*minor = 0;
	return xTrue;
}

XineramaScreenInfo* XineramaQueryScreens(Display *dpy, int *number) {
	XRRScreenResources *res = XRRGetScreenResources(dpy, XDefaultRootWindow(dpy));

	XineramaScreenInfo *retval = Xmalloc(res->noutput * sizeof(XineramaScreenInfo));
	int i;
	*number = 0;
	for(i=0; i<res->noutput; i++) {
		XRROutputInfo *output = XRRGetOutputInfo(dpy, res, res->outputs[i]);
		if(output->crtc) {
			XRRCrtcInfo *crtc = XRRGetCrtcInfo(dpy, res, output->crtc);

			retval[*number].screen_number = *number;
			retval[*number].x_org = crtc->x;
			retval[*number].y_org = crtc->y;
			retval[*number].width = crtc->width;
			retval[*number].height = crtc->height;
			(*number)++;
			XRRFreeCrtcInfo(crtc);
		}

		XRRFreeOutputInfo(output);
	}

	XRRFreeScreenResources(res);

    return retval;
}
#endif
