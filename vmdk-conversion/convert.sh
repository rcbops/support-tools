#!/usr/bin/env bash

set -e
set -u

DO_UPLOAD=0
INPUT_FILE=""
OUTPUT_FILE=""
IMAGE_NAME=""

function cleanup {
    retval=$?

    set +x

    if [ $retval -eq 0 ]; then
        # clean exit
        rm ${LOGFILE}
    else
        echo "Exiting on error.  Logfile in ${LOGFILE}"
    fi

    return $retval
}

function setup_logging {
    LOGFILE=$(mktemp)
    trap cleanup EXIT
    exec 9>$LOGFILE
    BASH_XTRACEFD=9
    set -x
}

function debug_out {
    if [ ! -z "${DEBUG:-0}" ]; then
        echo $@
    fi
}

function verify_args {
    must_exit=0

    if [ -z "$INPUT_FILE" ]; then
        echo "Input file must be specified!"
        must_exit=1
    elif [ ! -f "$INPUT_FILE" ]; then
        echo "Input file must exist!"
        must_exit=1
    elif [ -z "$OUTPUT_FILE" ]; then
        OUTPUT_FILE="$(dirname "$INPUT_FILE")/$(basename "$INPUT_FILE" .vmdk).qcow2"
    fi

    if [ $DO_UPLOAD -eq 1 ]; then
        if [ -z "${OS_AUTH_URL:-}" ]; then
            echo "No openstack environment sourced!"
            must_exit=1
        fi

        if [ -z "${IMAGE_NAME}" ]; then
            echo "No image name specified!"
            must_exit=1
        fi
    fi

    if [ $must_exit -eq 1 ]; then
        trap - EXIT
        cleanup
        exit 1
    fi
}

function do_convert() {
    input_file="$1"
    output_file="$2"

    if [ ! -f "${output_file}" ]; then
        qemu-img convert -c -O qcow2 "${input_file}" "${output_file}"
    fi
}

setup_logging

ARGS=$(getopt --options="o:un:" --longoptions="outfile:,upload,name:" -n "convert.sh" -- "$@")

if [ $? -ne 0 ]; then
    # warning message will be printed by getopt
    exit 1
fi

eval set -- "$ARGS"
while true; do
    case "$1" in
        -o|--outfile)
            shift
            if [ -n "$1" ]; then
                debug_out "setting output file to $1"
                OUTPUT_FILE="$1"
                shift
            fi
            ;;
        -u|--upload)
            shift
            DO_UPLOAD=1
            ;;
        -n|--name)
            shift
            if [ -n "$1" ]; then
                debug_out "setting glance image name to $1"
                IMAGE_NAME="$1"
                shift
            fi
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Something is crazy wrong."
            exit 1
            ;;
    esac
done

INPUT_FILE=${1:-}

verify_args

echo "Converting \"${INPUT_FILE}\" to \"${OUTPUT_FILE}\""

do_convert "${INPUT_FILE}" "${OUTPUT_FILE}"

if [ $DO_UPLOAD -eq 1 ]; then
    glance image-create --name="${IMAGE_NAME}" --is-public=true --container-format=bare --disk-format=qcow2 < "${OUTPUT_FILE}"
fi
