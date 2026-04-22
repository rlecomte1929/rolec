#!/usr/bin/env bash
# Preflight for Prompt A PDF-path unblock (GAP-011).
#
# Exit 0 iff the tools strictly required for the PDF unblock scope are
# available. Warns (does not fail) on ancillary tools whose absence only
# affects surfaces that are themselves out of scope (scanned-PDF OCR
# fixtures — GAP-001 confirms the codebase has no OCR path).
#
# Required (gate on these):
#   - soffice   — DOCX → PDF conversion for §8 parity fixtures
#   - qpdf      — §9 R1 encrypted-PDF fixture generation
#
# Advisory (warn if missing):
#   - pdftotext, pdftoppm — reference extraction / rasterization
#   - tesseract            — OCR (not used by the codebase today)
#   - img2pdf              — scanned-PDF image-to-pdf packaging

set -u

# User-local Homebrew landed at ~/homebrew because no sudo was available
# for a system-wide install. Both locations are probed so this script
# works on hosts with either setup.
export PATH="${HOME}/homebrew/bin:${HOME}/Applications/LibreOffice.app/Contents/MacOS:/opt/homebrew/bin:/usr/local/bin:${PATH}"

required=(soffice qpdf)
advisory=(pdftotext pdftoppm tesseract img2pdf)

missing_required=()
missing_advisory=()

echo "--- required tools ---"
for t in "${required[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "  $t: $(command -v $t)"
  else
    echo "  $t: MISSING (required)"
    missing_required+=("$t")
  fi
done

echo "--- advisory tools ---"
for t in "${advisory[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "  $t: $(command -v $t)"
  else
    echo "  $t: missing (advisory — only needed for scanned-PDF / OCR fixtures)"
    missing_advisory+=("$t")
  fi
done

if [[ ${#missing_required[@]} -gt 0 ]]; then
  echo ""
  echo "FAIL — required tools missing: ${missing_required[*]}"
  echo "Install with one of:"
  echo "  brew install ${missing_required[*]}"
  echo "  # or for libreoffice:  brew install --cask libreoffice"
  exit 1
fi

if [[ ${#missing_advisory[@]} -gt 0 ]]; then
  echo ""
  echo "WARN — advisory tools missing: ${missing_advisory[*]}"
  echo "  Scanned-PDF / OCR fixture generation will be skipped."
  echo "  Install later with:  brew install poppler tesseract img2pdf"
fi

echo ""
echo "OK — required toolchain present."
exit 0
