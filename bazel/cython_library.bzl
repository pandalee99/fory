# Custom Cython rules for Bazel 8.4.0
load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library")
load("@rules_python//python:defs.bzl", "py_library")

def pyx_library(name, deps = [], cc_kwargs = {}, py_deps = [], srcs = [], **kwargs):
    """Compiles a group of .pyx / .pxd / .py files.

    First runs Cython to create .cpp files for each input .pyx or .py + .pxd
    pair. Then builds a shared object for each, passing "deps" and **cc_kwargs
    to each cc_binary rule (includes Python headers by default). Finally, creates
    a py_library rule with the shared objects and any pure Python "srcs", with py_deps
    as its dependencies; the shared objects can be imported like normal Python files.

    Args:
        name: Name for the rule.
        deps: C/C++ dependencies of the Cython (e.g. Numpy headers).
        cc_kwargs: cc_binary extra arguments such as copts, linkstatic, linkopts, features
        py_deps: Other py_library dependencies.
        srcs: .py, .pyx, or .pxd files.
        **kwargs: Extra keyword arguments passed to the final py_library.
    """
    shared_objects = []
    pyx_srcs = []
    py_srcs = []
    pxd_srcs = []

    for src in srcs:
        if src.endswith('.pyx'):
            pyx_srcs.append(src)
        elif src.endswith('.py'):
            py_srcs.append(src)
        elif src.endswith('.pxd'):
            pxd_srcs.append(src)

    for pyx_src in pyx_srcs:
        stem = pyx_src.replace('.pyx', '').replace('/', '_')
        cpp_out = stem + ".cpp"
        
        # Run Cython to generate C++ file
        native.genrule(
            name = name + "_" + stem + "_cython",
            srcs = [pyx_src] + pxd_srcs,
            outs = [cpp_out],
            cmd = "$(location @cython//:cython_binary) --cplus -3 $(location %s) -o $@" % pyx_src,
            tools = ["@cython//:cython_binary"],
        )

        shared_object_name = stem + ".so"
        
        # Compile the generated C++ into a shared object
        cc_binary(
            name = shared_object_name,
            srcs = [cpp_out],
            deps = deps + ["@local_config_python//:python_headers"],
            linkshared = True,
            **cc_kwargs
        )
        shared_objects.append(":" + shared_object_name)

    # Create the final py_library
    py_library(
        name = name,
        data = shared_objects,
        srcs = py_srcs,
        deps = py_deps,
        **kwargs
    )
