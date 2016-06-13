# asynchia
~ *Readability counts.*

## What is asynchia?
asynchia aims to create a robust, well-written core for you to base your networking programs written in Python on; unlike other projects, it does no attempt of offering protocol implementations, lest it becomes too large to maintain.

## Which versions of Python are supported?
Being a relatively young project allows asynchia to be fully compatible with the backwards-incompatible 3.x versions of Python. It is tested to work with CPython 2.5–3.2 and the latest PyPy release. It is incompatible to Python 2.4, but I will start work on a backport upon request; I have decided, for the time being, that supporting 2.4 does not justify the decrease of code quality connected therewith.

## Why should I use asynchia?
asynchia's biggest strength is at the same time its biggest weakness: one the one hand, asynchia is specifically targetted at modern Python versions and was created with 3.x in mind from the start up, on the other hand, asynchia still is a very young project and thus cannot offer as much stability as other comparable libraries. However, asynchia's development process is aimed at producing beautiful code, not allowing any unclean hacks to end up in the master branch.

## I'm in! How do I install it?
If you have pip available on your system, asynchia can conveniently be installed because it is available in the pypi (make sure you have the required permissions on the system; in case you are installing the package into a global directory you will probably need to execute the command in a root-shell or prepend it with sudo, depending on your system configuration).
### Install asynchia with pip
`$ pip install asynchia`

The same holds true for easy_installed (component of setuptools) – the permission note for the pip way also applies here.
### Install asynchia with easy_install
`$ easy_install asynchia`

If none of these options work for you, just grab the source tarball and execute the following command.
### Manual install
`~/asynchia-0.2.0/ $ python setup.py install`

## Where can I find documentation?
Check out the documentation, but please be aware that some fundamental things are scheduled to change by 0.2.

## Can I have the source-code?
Yes, of course! You can find tarballs for the official releases at GitHub, or check out the git repository over there.

## Where can I reach you?
Visit us in #asynchia on irc.freenode.net, contact the maintainer via XMPP at segfaulthunter (AT) jabber (DOT) ccc (DOT) de, or send an email to flormayer (AT) aim (DOT) com.

## Why are all the headings questions?
I don't know.
