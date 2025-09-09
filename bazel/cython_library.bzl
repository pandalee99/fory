"""Cython compilation rules for Bazel."""

def pyx_library(name, srcs = [], deps = [], py_deps = [], copts = [], linkopts = [], **kwargs):
    """Compiles a group of .pyx / .pxd / .py files.

    First runs Cython to create .cpp files for each input .pyx file.
    Then builds a shared object for each, passing "deps" to each cc_binary
    rule (includes Python headers by default). Finally, creates a py_library rule
    with the shared objects and any pure Python "srcs", with py_deps as its
    dependencies; the shared objects can be imported like normal Python files.

    Args:
        name: Name for the rule.
        srcs: List of .pyx, .pxd, and .py files.
        deps: C/C++ dependencies of the Cython (e.g. Numpy headers).
        py_deps: Pure Python dependencies of the final py_library.
        copts: C++ compiler options.
        linkopts: C++ linker options.
        **kwargs: Additional arguments passed to py_library.
    """
    # Filter input files
    pyx_files = [f for f in srcs if f.endswith('.pyx')]
    pxd_files = [f for f in srcs if f.endswith('.pxd')]
    py_files = [f for f in srcs if f.endswith('.py')]
    
    shared_objects = []
    
    # For each .pyx file, create a .cpp file and then a shared object
    for pyx_file in pyx_files:
        stem = pyx_file[:-4]  # Remove .pyx extension
        cpp_file = stem + ".cpp"
        shared_object_name = stem.split("/")[-1] + ".so"
        
        # Generate .cpp from .pyx using Cython
        native.genrule(
            name = stem.replace("/", "_") + "_cython",
            srcs = [pyx_file] + pxd_files,
            outs = [cpp_file],
            cmd = "python3 -m cython --cplus -3 $(location " + pyx_file + ") -o $@",
        )
        
        # Compile .cpp to .so
        native.cc_binary(
            name = shared_object_name,
            srcs = [cpp_file],
            deps = deps + ["@python//:python_headers"],
            copts = copts + [
                "-fPIC",
                "-O3",
                "-std=c++17",
            ],
            linkopts = linkopts + [
                "-shared",
                "-undefined", "dynamic_lookup",  # For macOS Python extension modules
            ],
            linkshared = 1,
            visibility = ["//visibility:private"],
        )
        
        shared_objects.append(":" + shared_object_name)
    
    # Create the final py_library
    native.py_library(
        name = name,
        data = shared_objects,
        srcs = py_files,
        deps = py_deps,
        **kwargs
    )
