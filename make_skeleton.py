#!/usr/bin/env python
# encoding: utf-8
import os
import re
import tempfile

with tempfile.NamedTemporaryFile(suffix='.c') as temp:
    temp.write("#include <X11/extensions/Xrandr.h>")
    temp.flush()
    output = os.popen("gcc -E '{}'".format(temp.name)).read()

ccode = open("libXrandr.c").read()

print """
#include <X11/extensions/Xrandr.h>
#include <X11/Xlib.h>
"""

functions = re.findall(r"(?m)^(\w+(?:\s*\*+)?)\s*(XRR\w+)\s*\(([^)]+)\);", output)

for function in functions:
    rettype, name, parameters = function
    parameter_array = re.split("\s*,\s*", parameters)
    call = []
    actions = []

    for x in parameter_array:
        x = x.split()
        param = x[-1].replace("*", "")
        call.append(param)
        if param != x[-1]:
            continue
        if x[0] == "RRCrtc":
            actions.append(
                " {param} = {param} & ~XID_SPLIT_MOD;".format(param=param))
        elif x[0] == "RROutput":
            actions.append(
                " {param} = {param} & ~XID_SPLIT_MOD;".format(param=param))

    if re.search("(?<!_){}".format(name), ccode):
        print(("static {ret} (*_{fn})({par_def});\n".format(
            ret=rettype, par_def=", ".join(parameter_array), fn=name)))
        continue

    if actions:
        actions.append("")
    returnv = "return " if rettype.lower() != "void" else ""
    print(("static {ret} (*_{fn})({par_def});\n"
          "{ret} {fn}({par_def}) {{\n"
          "{actions}"
          "{returnv}_{fn}({par_call});\n"
          "}}\n\n").format(
              ret=rettype,
              fn=name,
              returnv=returnv,
              actions="\n".join(actions),
              par_def=", ".join(parameter_array),
              par_call=", ".join(call)
          ))

defns = []
for function in functions:
    defns.append("_{fn} = dlsym(xrandr_lib, \"{fn}\")".format(fn=function[1]))
print("#define FUNCTION_POINTER_INITIALIZATIONS {defns}".format(defns="; ".join(defns)))
