#!/usr/bin/env bash
# =============================================================================
# download_ldbc_snb.sh
#
# Download official LDBC SNB (Social Network Benchmark) data for a given
# scale factor from the GitHub releases.
#
# Usage:
#   ./download_ldbc_snb.sh <sf> [output_dir]
#   ./download_ldbc_snb.sh 1                    # downloads SF1 to data/ldbc_snb/sf1/
#   ./download_ldbc_snb.sh 0.1 ./my_data/      # downloads SF0.1 to ./my_data/
#
# Scale factors and approximate compressed sizes:
#   SF0.1  ~22 MB
#   SF0.3  ~66 MB
#   SF1   ~220 MB
#   SF3   ~660 MB
#   SF10  ~2.2 GB
#
# Requirements: curl, tar/gzip
# =============================================================================

set -euo pipefail

# ---- Configuration -----------------------------------------------------------
readonly GITHUB_BASE="https://github.com/ldbc/ldbc_snb_datagen/releases/download"
readonly VERSION="v0.4.1"   # Update to latest release as needed
readonly REPO="ldbc/ldbc_snb_datagen"

# ---- Helpers ----------------------------------------------------------------

usage() {
    cat <<EOF
Usage: $(basename "$0") <sf> [output_dir]

Arguments:
  sf          Scale factor (0.1, 0.3, 1, 3, 10, 30)
  output_dir  Output directory (default: data/ldbc_snb/sf<sf>)

Examples:
  $(basename "$0") 1          # Download SF1 to data/ldbc_snb/sf1/
  $(basename "$0") 0.1 ./data/  # Download SF0.1 to ./data/
EOF
    exit 1
}

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

warn() {
    echo "[$(date '+%H:%M:%S')] WARNING: $*" >&2
}

die() {
    echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2
    exit 1
}

# Check required tools
check_deps() {
    local missing=()
    command -v curl >/dev/null 2>&1 || missing+=("curl")
    command -v tar  >/dev/null 2>&1 || missing+=("tar")

    if [[ ${#missing[@]} -gt 0 ]]; then
        die "Missing required tools: ${missing[*]}. Please install them first."
    fi
}

# Validate scale factor
validate_sf() {
    local sf="$1"
    case "$sf" in
        0.1|0.3|1|3|10|30) return 0 ;;
        *) die "Unsupported scale factor: $sf. Supported: 0.1, 0.3, 1, 3, 10, 30" ;;
    esac
}

# Get download URL for a scale factor
get_download_url() {
    local sf="$1"
    echo "${GITHUB_BASE}/${VERSION}/ldbc_snb_sf${sf}.tar.gz"
}

# Get expected file size (for progress display)
get_expected_size() {
    local sf="$1"
    case "$sf" in
        0.1)  echo "~22 MB"   ;;
        0.3)  echo "~66 MB"   ;;
        1)    echo "~220 MB"  ;;
        3)    echo "~660 MB"  ;;
        10)   echo "~2.2 GB"  ;;
        30)   echo "~6.6 GB"  ;;
    esac
}

# Download with retry and progress
download_with_retry() {
    local url="$1"
    local output="$2"
    local max_retries=3
    local retry=0

    while (( retry < max_retries )); do
        (( retry++ ))
        log "Download attempt $retry of $max_retries..."

        if curl -fSL \
            --progress-bar \
            --retry 3 \
            --retry-delay 5 \
            -o "$output" \
            "$url"; then
            return 0
        fi

        if (( retry < max_retries )); then
            warn "Download failed. Retrying in 10 seconds..."
            sleep 10
        fi
    done

    return 1
}

# Extract tar.gz archive
extract_archive() {
    local archive="$1"
    local output_dir="$2"

    log "Extracting archive..."
    if command -v tar >/dev/null 2>&1; then
        tar -xzf "$archive" -C "$output_dir"
    else
        die "tar command not found"
    fi
}

# ---- Main -------------------------------------------------------------------

main() {
    # Parse arguments
    local sf="${1:-}"
    local output_dir="${2:-}"

    [[ -z "$sf" ]] && usage

    validate_sf "$sf"

    if [[ -z "$output_dir" ]]; then
        # Default output: data/ldbc_snb/sf<sf>
        output_dir="data/ldbc_snb/sf${sf}"
    fi

    # Resolve to absolute path
    output_dir="$(realpath "$output_dir" 2>/dev/null || echo "$output_dir")"

    check_deps

    # Create output directory
    mkdir -p "$output_dir"

    # Check if data already exists
    if [[ -d "$output_dir/sf${sf}" ]] || find "$output_dir" -name "*.csv" -o -name "*.gz" 2>/dev/null | grep -q .; then
        warn "Data directory already contains files."
        read -rp "Overwrite? [y/N] " confirm
        [[ "${confirm,,}" != "y" ]] && { log "Aborted."; exit 0; }
        rm -rf "$output_dir"/*
    fi

    local download_url
    download_url=$(get_download_url "$sf")
    local archive_file="${output_dir}/ldbc_snb_sf${sf}.tar.gz"

    log "=========================================="
    log "  LDBC SNB Data Downloader"
    log "=========================================="
    log "  Scale factor : SF${sf}"
    log "  Expected size: $(get_expected_size "$sf")"
    log "  Output dir   : $output_dir"
    log "  URL          : $download_url"
    log "=========================================="

    # Download
    log "Starting download..."
    if ! download_with_retry "$download_url" "$archive_file"; then
        die "Failed to download after $max_retries attempts."
    fi

    local file_size
    file_size=$(du -h "$archive_file" 2>/dev/null | cut -f1 || stat -c%s "$archive_file" 2>/dev/null || echo "unknown")
    log "Download complete. File size: $file_size"

    # Extract
    extract_archive "$archive_file" "$output_dir"

    # Cleanup archive
    rm -f "$archive_file"

    log "=========================================="
    log "  Download Complete!"
    log "=========================================="
    log "  Data extracted to: $output_dir"
    log ""
    log "  Next steps:"
    log "    1. Generate CSV from raw data (if needed)"
    log "    2. Use generate_ldbc_snb.py for synthetic data"
    log "    3. Load into TigerGraph using the loader"
    log "=========================================="
}

main "$@"
