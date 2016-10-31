#!/bin/sh

set -e

if [ $# -ne 1 ]; then
   cat >&2 <<EOF
Usage: $(basename "$0") directory

Updates and compiles source code in all repositories found in given directory.
   
This script simplifies updates of typical wiking application deployments which
run from git repositories specific for a particular web server's virtual host.
All sudbirectories, which are git repositories are updated from git by running
"git pull" and if they contain a makefile, "make" is run as well.  This usually
compiles Python byte code and generates Gettext translations in repositories
typically needed for Wiking web applications (LCG, Pytis, Wiking etc).  In case
of any error, the script exits without processing the remaining repositories.

Note, that you may need to run upgrade-db.py separately after updating.

EOF
   exit 1
fi

srcdir=$1

if [ ! -d "$srcdir" ]; then
    echo "Not a directory: $srcdir"
    exit 1
fi

cd $srcdir
for repo in $(ls); do
   if [ -d $repo/.git ]; then
      echo "Updating repository: $repo"
      cd $repo
      git pull
      if [ -f Makefile -o -f makefile ]; then
         make
      fi
      cd ..
   fi
done

