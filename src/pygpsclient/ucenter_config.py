"""
ucenter_config.py

Command line utility to convert a u-center "Config changes format version 1.0"
text export into a PyGPSClient batch-flash CSV.

The resulting CSV can be loaded directly into the CFG-VALSET batch queue of
the UBX Configuration dialog (see the "Load CSV" button) and flashed to a
u-blox receiver in one operation.

Output CSV columns: layer,key,value
  layer : RAM | BBR | FLASH        (u-blox memory layer to write to)
  key   : pyubx2 config keyname    (underscore convention, e.g. CFG_RATE_MEAS)
  value : decimal, hex or float    (coerced to the parameter type on load)

Only the [set] section is converted; any [del] entries are reported but not
written, since this CSV drives CFG-VALSET flashing.

Usage::

    ucenter2csv -I config_changes.txt -O flash_config.csv

Created on 2 Jul 2026

:author: semuadmin (Steve Smith)
:copyright: 2020 semuadmin
:license: BSD 3-Clause
"""

import csv
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from pygpsclient._version import __version__ as VERSION

LAYERS = ("RAM", "BBR", "FLASH")


def parse_value(raw: str):
    """
    Parse a decimal, hex (0x..) or floating point value string.

    :param str raw: value token from the u-center export
    :return: value as int or float
    :rtype: int | float
    """

    raw = raw.strip()
    if raw.lower().startswith("0x"):
        return int(raw, 16)
    if "." in raw or "e" in raw.lower():
        return float(raw)
    return int(raw)


def convert(infile: str, outfile: str) -> tuple:
    """
    Convert a u-center config-changes text file to a PyGPSClient flash CSV.

    :param str infile: path to u-center config-changes text export
    :param str outfile: path to output CSV
    :return: tuple of (rows written, [del] entries skipped, bad lines skipped)
    :rtype: tuple
    """

    rows = []
    section = None
    del_count = 0
    skipped = []

    with open(infile, "r", encoding="utf-8") as fin:
        for lineno, line in enumerate(fin, 1):
            code = line.split("#", 1)[0].strip()  # strip trailing comment
            if code == "":
                continue
            low = code.lower()
            if low.startswith("[set]"):
                section = "set"
                continue
            if low.startswith("[del]"):
                section = "del"
                continue
            if low.startswith("["):  # any other section
                section = None
                continue

            if section == "del":
                del_count += 1
                continue
            if section != "set":
                continue

            tokens = code.split()  # <layer> <key> <value>
            if len(tokens) < 3:
                skipped.append((lineno, line.rstrip()))
                continue

            layer = tokens[0].upper()
            if layer not in LAYERS:
                skipped.append((lineno, line.rstrip()))
                continue

            key = tokens[1].replace("-", "_")
            try:
                value = parse_value(tokens[2])
            except ValueError:
                skipped.append((lineno, line.rstrip()))
                continue

            rows.append((layer, key, value))

    with open(outfile, "w", encoding="utf-8", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(["layer", "key", "value"])
        writer.writerows(rows)

    return rows, del_count, skipped


def main():
    """CLI entry point."""

    ap = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter,
        description=(
            "Convert a u-center 'Config changes' text export into a "
            "PyGPSClient batch-flash CSV (layer,key,value)."
        ),
    )
    ap.add_argument("-V", "--version", action="version", version="%(prog)s " + VERSION)
    ap.add_argument(
        "-I",
        "--infile",
        required=True,
        help="Fully-qualified path to u-center config-changes text file",
    )
    ap.add_argument(
        "-O",
        "--outfile",
        required=True,
        help="Fully-qualified path to output CSV file",
    )
    args = ap.parse_args()

    rows, del_count, skipped = convert(args.infile, args.outfile)

    print(f"Wrote {len(rows)} set row(s) to {args.outfile}")
    if del_count:
        print(f"NOTE: skipped {del_count} [del] entrie(s) (not written to CSV)")
    if skipped:
        print(f"WARNING: skipped {len(skipped)} unparseable line(s):")
        for lineno, raw in skipped[:20]:
            print(f"  line {lineno}: {raw}")


if __name__ == "__main__":
    main()
