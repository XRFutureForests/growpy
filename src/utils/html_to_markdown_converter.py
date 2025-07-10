#!/usr/bin/env python3
"""
HTML to Markdown Converter

A generic script to convert HTML files to Markdown format.
Supports recursive directory conversion and command-line usage.

Usage:
    python html_to_markdown_converter.py input_dir output_dir
    python html_to_markdown_converter.py -h  # for help
"""

import sys
import re
import argparse
from pathlib import Path
import html2text


def setup_html2text_converter():
    """Configure the html2text converter with appropriate settings."""
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.body_width = 0  # No line wrapping
    h.unicode_snob = True
    h.mark_code = True
    h.default_image_alt = ""
    h.pad_tables = True
    h.bypass_tables = False
    h.single_line_break = False
    return h


def clean_markdown_content(content):
    """Clean and improve the converted markdown content."""

    # Convert [code]...[/code] blocks to proper Python markdown code blocks
    def clean_code_block(match):
        code_content = match.group(1)
        lines = code_content.split("\n")

        # Remove leading/trailing empty lines
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        if not lines:
            return "```python\n```"

        # Find minimum indentation (excluding empty lines)
        non_empty_lines = [line for line in lines if line.strip()]
        if non_empty_lines:
            min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
            # Remove the minimum common indentation but preserve relative indentation
            lines = [
                (
                    line[min_indent:]
                    if len(line) > min_indent
                    else ("" if not line.strip() else line.lstrip())
                )
                for line in lines
            ]

        # Join back and clean up
        cleaned_code = "\n".join(lines)
        return f"```python\n{cleaned_code}\n```"

    content = re.sub(
        r"\[code\](.*?)\[/code\]", clean_code_block, content, flags=re.DOTALL
    )

    # Remove excessive newlines (more than 2 consecutive)
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Clean up empty code blocks
    content = re.sub(r"```python\s*\n\s*```", "", content)

    # Fix headers with excessive spacing
    content = re.sub(r"^(#{1,6})\s+(.+)", r"\1 \2", content, flags=re.MULTILINE)

    # Remove style attributes and other HTML remnants
    content = re.sub(r'style="[^"]*"', "", content)
    content = re.sub(r'class="[^"]*"', "", content)

    # Clean up list formatting
    content = re.sub(r"\n\s*\n(\s*[-*+])", r"\n\1", content)
    content = re.sub(r"\n\s*\n(\s*\d+\.)", r"\n\1", content)

    # Ensure proper spacing around headers
    content = re.sub(r"\n(#{1,6}\s)", r"\n\n\1", content)
    content = re.sub(r"(#{1,6}[^\n]+)\n([^\n#])", r"\1\n\n\2", content)

    # Remove excessive whitespace around content (but preserve code block indentation)
    content = re.sub(r"[ \t]+\n", "\n", content)  # Remove trailing spaces

    return content.strip()


def convert_html_to_markdown(html_file_path, output_dir):
    """Convert a single HTML file to Markdown."""
    try:
        with open(html_file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        # Setup converter
        converter = setup_html2text_converter()

        # Convert HTML to Markdown
        markdown_content = converter.handle(html_content)

        # Clean the markdown content
        markdown_content = clean_markdown_content(markdown_content)

        # Determine output file path
        html_file = Path(html_file_path)
        markdown_filename = html_file.stem + ".md"
        output_file_path = output_dir / markdown_filename

        # Ensure output directory exists
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write markdown content
        with open(output_file_path, "w", encoding="utf-8") as file:
            file.write(markdown_content)

        print(f"✓ Converted: {html_file.name} -> {output_file_path}")
        return True

    except Exception as e:
        print(f"✗ Error converting {html_file_path}: {str(e)}")
        return False


def find_html_files(input_dir):
    """Find all HTML files in the given directory recursively."""
    html_files = []
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    if input_path.is_file():
        # Single file
        if input_path.suffix.lower() == ".html":
            html_files.append(input_path)
    else:
        # Directory - find all HTML files recursively
        for html_file in input_path.rglob("*.html"):
            html_files.append(html_file)

    return html_files


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert HTML files to Markdown format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert all HTML files in a directory
    python html_to_markdown_converter.py /path/to/html/files /path/to/output
    
    # Convert a single HTML file
    python html_to_markdown_converter.py file.html /path/to/output
    
    # Get help
    python html_to_markdown_converter.py -h
        """,
    )

    parser.add_argument(
        "input_path", help="Input HTML file or directory containing HTML files"
    )

    parser.add_argument(
        "output_dir", help="Output directory for converted Markdown files"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    return parser.parse_args()


def main():
    """Main function to convert HTML files to Markdown."""
    args = parse_arguments()

    print("HTML to Markdown Converter")
    print("=" * 40)

    # Validate input
    input_path = Path(args.input_path)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        print(f"✗ Error: Input path does not exist: {input_path}")
        sys.exit(1)

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Find all HTML files
        html_files = find_html_files(input_path)

        if not html_files:
            print("No HTML files found in the specified input path.")
            return

        print(f"Found {len(html_files)} HTML file(s) to convert.")
        if args.verbose:
            for html_file in html_files:
                print(f"  - {html_file}")
        print()

        # Convert each HTML file
        successful_conversions = 0
        failed_conversions = 0

        for html_file in html_files:
            if convert_html_to_markdown(html_file, output_dir):
                successful_conversions += 1
            else:
                failed_conversions += 1

        # Print summary
        print("\n" + "=" * 40)
        print("Conversion complete!")
        print(f"✓ Successfully converted: {successful_conversions} files")
        print(f"✗ Failed conversions: {failed_conversions} files")
        print(f"📁 Output directory: {output_dir.resolve()}")

        if failed_conversions > 0:
            print("\nSome files failed to convert. Check the error messages above.")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if html2text is available
    try:
        import html2text
    except ImportError:
        print("Required library not found. Please install it using:")
        print("pip install html2text")
        sys.exit(1)

    main()
