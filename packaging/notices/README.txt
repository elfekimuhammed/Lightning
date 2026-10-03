Third-party notices that the Windows bundle needs but that no installed package provides.

packaging/package_app.py copies every file in this folder (except this README) into the bundle's
licenses/third-party/ folder. A file named <distribution>-LICENSE.txt also stands in for a runtime
distribution that ships no licence file of its own (proxy-tools). Refresh a text when the component's
version changes: Python-3.13-incorporated-software.txt is checked against the Python minor version at
build time, and package_app.py --strict fails on a different one.
