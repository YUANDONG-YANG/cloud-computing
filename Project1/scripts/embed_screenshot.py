"""Embed a PNG screenshot into the Master Overview after an existing figure.

The overview is one self-contained HTML file, so images are stored inline as
base64 data URIs instead of being linked from docs/evidence/.

Example:
    python scripts/embed_screenshot.py docs/evidence/github-actions-run-NN.png \
        --after "GitHub Actions run 13 succeeded" \
        --alt "GitHub Actions run NN succeeded" \
        --caption "Workflow run #NN ... (date and clock visible)"
"""
import argparse
import base64
import html
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "docs/reports/Project1-Master-Overview.html"


def embed(image, after_alt, alt, caption, report=REPORT):
    page = report.read_text(encoding="utf-8")
    anchor = page.find(f'alt="{after_alt}"')
    if anchor == -1:
        raise SystemExit(f'No image with alt="{after_alt}" in {report.name}')
    if f'alt="{html.escape(alt)}"' in page:
        raise SystemExit(f'An image with alt="{alt}" is already embedded')
    end = page.index("</figure>", anchor) + len("</figure>")
    data = base64.b64encode(Path(image).read_bytes()).decode("ascii")
    figure = (f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'
              f"<figcaption>{html.escape(caption)}</figcaption></figure>")
    report.write_text(page[:end] + figure + page[end:], encoding="utf-8")
    print(f"Embedded {image} after '{after_alt}' in {report.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image")
    parser.add_argument("--after", required=True, help="alt text of the figure to insert after")
    parser.add_argument("--alt", required=True)
    parser.add_argument("--caption", required=True)
    args = parser.parse_args()
    embed(args.image, args.after, args.alt, args.caption)
