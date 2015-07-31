#!/usr/bin/env bash

# DDevSDN for Ubuntu 
# Dayoung Kim (kdy906@naver.com)

# Fail on error
set -e

# Fail on unset var usage
set -o nounset

# Get directory of DDevSDN folder
ROOT_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd -P )"

# Set up build directory, which by default is the working directory
#  unless the working directory is a subdirectory of mininet, 
#  in which case we use the directory containing mininet
BUILD_DIR="$(pwd -P)"
case $BUILD_DIR in
  $ROOT_DIR/*) BUILD_DIR=$ROOT_DIR;; # currect directory is a subdirectory
  *) BUILD_DIR=$BUILD_DIR;;
esac

# Attempt to identify Linux release

DIST=Unknown
RELEASE=Unknown
CODENAME=Unknown
ARCH=`uname -m`
if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; fi
if [ "$ARCH" = "i686" ]; then ARCH="i386"; fi

test -e /etc/debian_version && DIST="Debian"
grep Ubuntu /etc/lsb-release &> /dev/null && DIST="Ubuntu"
if [ "$DIST" = "Ubuntu" ] || [ "$DIST" = "Debian" ]; then
    install='sudo apt-get -y install'
    remove='sudo apt-get -y remove'
    pkginst='sudo dpkg -i'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
        $install lsb-release
    fi
fi
test -e /etc/fedora-release && DIST="Fedora"
if [ "$DIST" = "Fedora" ]; then
    install='sudo yum -y install'
    remove='sudo yum -y erase'
    pkginst='sudo rpm -ivh'
    # Prereqs for this script
    if ! which lsb_release &> /dev/null; then
        $install redhat-lsb-core
    fi
fi
if which lsb_release &> /dev/null; then
    DIST=`lsb_release -is`
    RELEASE=`lsb_release -rs`
    CODENAME=`lsb_release -cs`
fi
echo "Detected Linux distribution: $DIST $RELEASE $CODENAME $ARCH"

# Kernel params

KERNEL_NAME=`uname -r`
KERNEL_HEADERS=kernel-headers-${KERNEL_NAME}

if ! echo $DIST | egrep 'Ubuntu|Debian|Fedora'; then
    echo "ddevsdn.sh currently only supports Ubuntu, Debian and Fedora."
    exit 1
fi

# More distribution info
DIST_LC=`echo $DIST | tr [A-Z] [a-z]` # as lower case


# Determine whether version $1 >= version $2
# usage: if version_ge 1.20 1.2.3; then echo "true!"; fi
function version_ge {
    # sort -V sorts by *version number*
    latest=`printf "$1\n$2" | sort -V | tail -1`
    # If $1 is latest version, then $1 >= $2
    [ "$1" == "$latest" ]
}
# Install Cbench
function cbench {
    if [ ! -d "$BUILD_DIR/openflow" ]; then
        openflow
    fi
    echo "installing KulCloud Cbench... (support openflow1.3)"
    cd $BUILD_DIR

    sudo apt-get install autoconf automake libtool libsnmp-dev libpcap-dev

    git clone git://gitosis.stanford.edu/oflops.git
    cd oflops
    sh ./boot.sh
    ./configure --with-openflow-src-dir=$BUILD_DIR/openflow
    make
    make install

    cd $BUILD_DIR
}
# Install KCCbench
function kccbench {
    if [ ! -d "$BUILD_DIR/openflow" ]; then
        openflow
    fi
    echo "installing KulCloud Cbench... (support openflow1.3)"
    cd $BUILD_DIR

    sudo apt-get install libconfig8-dev libsnmp-dev libpcap-dev
    #Downloads from KulCloud's blog
    wget http://www.weebly.com/uploads/1/3/2/6/13260234/kc-cbench.tgz

    tar -xvzf kc-cbench.tgz
    cd kc-cbench
    ./boot.sh
    ./configure --with-openflow-src-dir=$BUILD_DIR/openflow
    make
    make install

    cd $BUILD_DIR
}
# Install OpenMUL
function openmul {
    echo "Installing MUL Controller..."

    cd $BUILD_DIR/
    git clone https://github.com/openmul/openmul.git

    cd openmul
    ./build.sh

    cp application/nbapi/c-swig/.libs/_mul_nbapi.so application/nbapi/py-tornado/app/lib/
    cp application/nbapi/c-swig/.libs/_mul_nbapi.so.0 application/nbapi/py-tornado/app/lib/
    cp application/nbapi/c-swig/.libs/_mul_nbapi.so.0.0.0 application/nbapi/py-tornado/app/lib/
    cp application/nbapi/c-swig/mul_nbapi.py application/nbapi/py-tornado/app/lib/

    cp application/nbapi/c-swig/.libs/_mul_nbapi.so TEST-SCRIPTS/python/
    cp application/nbapi/c-swig/.libs/_mul_nbapi.so.0 TEST-SCRIPTS/python/
    cp application/nbapi/c-swig/.libs/_mul_nbapi.so.0.0.0 TEST-SCRIPTS/python/
    cp application/nbapi/c-swig/mul_nbapi.py TEST-SCRIPTS/python/

    cd $BUILD_DIR
}
function openflow {
    echo "Installing OpenFlow"
    cd $BUILD_DIR

    git clone git://openflowswitch.org/openflow.git
    cd openflow

    ./boot.sh
    ./configure
    make
    make install    

    cd $BUILD_DIR
}
function usage {
    echo $BUILD_DIR
    printf '\nUsage: %s [-acdfhimnorv]\n\n' $(basename $0) >&2

    printf 'This DDevSDN script attempts to install, run and testing useful software\n' >&2
    printf 'for OpenMUL.It should (hopefully) work on Ubuntu 11.10+\n' >&2
    printf 'If you run into trouble, try\n' >&2
    printf 'installing one thing at a time, and looking at the \n' >&2
    printf 'specific installation function in this script.\n\n' >&2

    printf 'options:\n' >&2
    printf -- ' -a: -install (A)vior, sdn gui\n' >&2
    printf -- ' -b: -install controller (B)enchmark (oflops)\n' >&2
    printf -- ' -d: -install Open(D)ayLight controller\n' >&2
    printf -- ' -f: -install (F)loodlight controller\n' >&2
    printf -- ' -i: -install M(I)ninet \n' >&2
    printf -- ' -k: -install (K)CCbench \n' >&2
    printf -- ' -m: -install open(M)ul controller\n' >&2
    printf -- ' -n: -install O(N)os controller\n' >&2
    printf -- ' -o: -install (O)penflow \n' >&2
    printf -- ' -r: -install (R)yu controller\n' >&2
    printf -- ' -v: -install open(V)switch\n' >&2

    exit 2
}

if [ $# -eq 0 ]
then
    usage
else
    while getopts 'abdfikmnorv' OPTION
    do
      case $OPTION in
      #a)    avior;;
      b)    cbench;;
      #d)    opendaylight;;
      #f)    floodlight;;
      #i)    mininet;;
      k)    kccbench;;
      m)    openmul;;
      #n)    onos;;
      o)    openflow;;
      #r)    ryu;;
      #v)    openvswitch;;
      ?)    usage;;
      esac
    done
    shift $(($OPTIND - 1))
fi
