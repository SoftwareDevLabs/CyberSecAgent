#!/usr/bin/env bash
# Install pinned versions of all external pipeline tools.
# Usage: bash scripts/install-tools.sh
# Installs to /usr/local/bin by default; override with TOOLS_INSTALL_DIR.
set -euo pipefail

INSTALL_DIR="${TOOLS_INSTALL_DIR:-/usr/local/bin}"

SYFT_VERSION="1.4.1"
GRYPE_VERSION="0.84.0"
OSV_SCANNER_VERSION="2.4.0"  # v2.x CLI: "osv-scanner scan --sbom <path>" (cve_matcher.py targets this)
OPENGREP_VERSION="1.7.0"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

# Normalise arch names to match release asset naming conventions
case "$ARCH" in
  x86_64)  ARCH_SYFT="amd64"; ARCH_GRYPE="amd64"; ARCH_OSV="amd64"; ARCH_OG="amd64" ;;
  arm64|aarch64) ARCH_SYFT="arm64"; ARCH_GRYPE="arm64"; ARCH_OSV="arm64"; ARCH_OG="arm64" ;;
  *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

case "$OS" in
  darwin)  OS_SYFT="darwin";  OS_GRYPE="darwin";  OS_OSV="darwin";  OS_OG="darwin" ;;
  linux)   OS_SYFT="linux";   OS_GRYPE="linux";   OS_OSV="linux";   OS_OG="linux" ;;
  *) echo "Unsupported OS: $OS"; exit 1 ;;
esac

need_sudo() {
  if [[ ! -w "$INSTALL_DIR" ]]; then
    echo "sudo"
  else
    echo ""
  fi
}

install_binary() {
  local name="$1" url="$2" archive="$3" binary_in_archive="$4"
  local dest="$INSTALL_DIR/$name"

  if [[ -f "$dest" ]]; then
    local existing
    existing=$("$dest" version 2>/dev/null | head -1 || "$dest" --version 2>/dev/null | head -1 || echo "unknown")
    echo "✓ $name already installed ($existing)"
    return
  fi

  echo "→ Installing $name ..."
  local tmp
  tmp="$(mktemp -d)"
  curl -sSfL "$url" -o "$tmp/$archive"

  if [[ "$archive" == *.tar.gz ]]; then
    tar -xzf "$tmp/$archive" -C "$tmp"
  elif [[ "$archive" == *.zip ]]; then
    unzip -q "$tmp/$archive" -d "$tmp"
  else
    # raw binary
    cp "$tmp/$archive" "$tmp/$name"
  fi

  local SUDO
  SUDO="$(need_sudo)"
  $SUDO install -m 755 "$tmp/$binary_in_archive" "$dest"
  rm -rf "$tmp"
  echo "  installed → $dest"
}

echo "Installing CyberGuard pipeline tools to $INSTALL_DIR"
echo "──────────────────────────────────────────────────────"

# Syft — SBOM generator
install_binary \
  "syft" \
  "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_${OS_SYFT}_${ARCH_SYFT}.tar.gz" \
  "syft_${SYFT_VERSION}_${OS_SYFT}_${ARCH_SYFT}.tar.gz" \
  "syft"

# Grype — CVE matcher
install_binary \
  "grype" \
  "https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/grype_${GRYPE_VERSION}_${OS_GRYPE}_${ARCH_GRYPE}.tar.gz" \
  "grype_${GRYPE_VERSION}_${OS_GRYPE}_${ARCH_GRYPE}.tar.gz" \
  "grype"

# OSV-Scanner — CVE matcher (supplemental)
install_binary \
  "osv-scanner" \
  "https://github.com/google/osv-scanner/releases/download/v${OSV_SCANNER_VERSION}/osv-scanner_${OS_OSV}_${ARCH_OSV}" \
  "osv-scanner_${OS_OSV}_${ARCH_OSV}" \
  "osv-scanner_${OS_OSV}_${ARCH_OSV}"

# OpenGrep — reachability analysis (default)
install_binary \
  "opengrep" \
  "https://github.com/opengrep/opengrep/releases/download/v${OPENGREP_VERSION}/opengrep-${OS_OG}-${ARCH_OG}.tar.gz" \
  "opengrep-${OS_OG}-${ARCH_OG}.tar.gz" \
  "opengrep"

echo ""
echo "All tools installed. Verify with:"
echo "  syft version && grype version && osv-scanner --version && opengrep --version"
