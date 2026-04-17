from pathlib import Path

p = Path("src/growpy/io/usd/twig_geometry.py")
text = p.read_text(encoding="utf-8")
start_marker = "def _DEAD_densify_and_trim_interleaved_REPLACED("
end_marker = "def _is_likely_tube_component("
i = text.index(start_marker)
j = text.index(end_marker)
cleaned = text[:i] + text[j:]
p.write_text(cleaned, encoding="utf-8")
print(f"removed {j - i} chars")
