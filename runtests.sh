#!/bin/sh

# asynchia - asynchronous networking library
# Copyright (C) 2010 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Users of unixoid operating systems can use this file to run
# the tests without needing to worry about enabling the Python interpreter
# to find the library or about old copies of the library that may reside
# in a directory exposed to Python by being contained in sys.path.
# To put it in a nutshell: Use this file to run the tests to minimize
# error-sources.

printhelp() {
	echo "-p [PYTHON INTERPRETER]\n-l [LOGFILE]"
	exit
}


SCRIPTDIR=`dirname "$0"`
LOGFILE="$SCRIPTDIR/runtests.log"
TESTMAIN="$SCRIPTDIR/asynchia/test/__main__.py"
PYTHON=`which python`

export PYTHONPATH="$SCRIPTDIR":"$PYTHONPATH"

while getopts p:l:h option
do
	case $option in
		p)
			PYTHON=$OPTARG
		;;
		l)
			LOGFILE=$OPTARG
		;;
		*)
			printhelp
		;;
	esac
done

rm -rf "$SCRIPTDIR"/tmpenv;
mkdir "$SCRIPTDIR"/tmpenv;
$PYTHON "$SCRIPTDIR"/ext/virtualenv.py\
   --no-site-packages -p "$PYTHON" "$SCRIPTDIR"/tmpenv;

INTR="$SCRIPTDIR"/tmpenv/bin/python

"$INTR" "$TESTMAIN" 2>&1 | tee "$LOGFILE"

rm -rf "$SCRIPTDIR"/tmpenv;
