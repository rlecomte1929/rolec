#!/usr/bin/env python3
"""
Stage 3: Generate .docx files from Stanford course research documents.
Uses only Python stdlib (zipfile + XML) - no external dependencies required.
"""
import os
import re
import io
import zipfile
from pathlib import Path
from datetime import date

BASE_DIR = Path("/tmp/rolec/research/stanford-courses")

COURSES = [
    {
        "dir": "ms-e435",
        "name": "MS&E435 | Spring 2026 — Economics of Generative AI & Enterprise AI",
        "short": "MSE435",
        "synthesis": "ms-e435-spring-2026.md",
        "filename": "Stanford_MSE435_ReloPass_Research.docx",
    },
    {
        "dir": "cs224r",
        "name": "Stanford CS224R — Deep Reinforcement Learning",
        "short": "CS224R",
        "synthesis": "cs224r-deep-rl.md",
        "filename": "Stanford_CS224R_ReloPass_Research.docx",
    },
    {
        "dir": "cs230",
        "name": "Stanford CS230 — Deep Learning | Autumn 2025",
        "short": "CS230",
        "synthesis": "cs230-deep-learning.md",
        "filename": "Stanford_CS230_ReloPass_Research.docx",
    },
    {
        "dir": "cs329h",
        "name": "Stanford CS329H — Machine Learning from Human Preferences | Autumn 2024",
        "short": "CS329H",
        "synthesis": "cs329h-ml-human-prefs.md",
        "filename": "Stanford_CS329H_ReloPass_Research.docx",
    },
    {
        "dir": "cs229",
        "name": "Stanford CS229 — Machine Learning | Spring 2026",
        "short": "CS229",
        "synthesis": "cs229-machine-learning.md",
        "filename": "Stanford_CS229_ReloPass_Research.docx",
    },
]

SOURCE_DIR = Path("/tmp/relopass-research")

# ── MINIMAL DOCX BUILDER ─────────────────────────────────────────────────────

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

WORD_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>"""

SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
</w:settings>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="259" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="160"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:pStyle w:val="Heading1"/>
      <w:outlineLvl w:val="0"/>
      <w:spacing w:before="480" w:after="240"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="36"/>
      <w:szCs w:val="36"/>
      <w:color w:val="2E74B5"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:pStyle w:val="Heading2"/>
      <w:outlineLvl w:val="1"/>
      <w:spacing w:before="360" w:after="160"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="28"/>
      <w:szCs w:val="28"/>
      <w:color w:val="2E74B5"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="Normal"/>
    <w:pPr>
      <w:pStyle w:val="Heading3"/>
      <w:outlineLvl w:val="2"/>
      <w:spacing w:before="240" w:after="120"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="24"/>
      <w:szCs w:val="24"/>
      <w:color w:val="1F3864"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:pPr>
      <w:jc w:val="center"/>
      <w:spacing w:before="240" w:after="240"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="52"/>
      <w:szCs w:val="52"/>
      <w:color w:val="2E74B5"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet">
    <w:name w:val="List Bullet"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:numPr>
        <w:ilvl w:val="0"/>
        <w:numId w:val="0"/>
      </w:numPr>
      <w:ind w:left="720" w:hanging="360"/>
    </w:pPr>
  </w:style>
</w:styles>"""


class DocxBuilder:
    """Minimal DOCX builder using only Python stdlib."""

    def __init__(self, title="Document"):
        self.title = title
        self.paragraphs = []  # list of (style, text, bold) tuples

    def add_title(self, text):
        self.paragraphs.append(("Title", text, True))

    def add_heading(self, text, level=1):
        style = f"Heading{level}"
        self.paragraphs.append((style, text, True))

    def add_para(self, text, bold=False, center=False):
        self.paragraphs.append(("Normal" + ("+center" if center else ""), text, bold))

    def add_bullet(self, text):
        self.paragraphs.append(("ListBullet", text, False))

    def add_page_break(self):
        self.paragraphs.append(("__pagebreak__", "", False))

    def _escape(self, text):
        """Escape XML special characters."""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text

    def _make_para_xml(self, style, text, bold):
        """Generate XML for a single paragraph."""
        esc = self._escape(text)

        if style == "__pagebreak__":
            return """<w:p>
  <w:r><w:br w:type="page"/></w:r>
</w:p>"""

        center = "+center" in style
        style_clean = style.replace("+center", "")

        ppr_parts = [f'<w:pStyle w:val="{style_clean}"/>']
        if center:
            ppr_parts.append('<w:jc w:val="center"/>')

        ppr = f'<w:pPr>{"".join(ppr_parts)}</w:pPr>'

        rpr = "<w:rPr><w:b/></w:rPr>" if bold and style_clean == "Normal" else ""

        # Split text into runs (handles line breaks within paragraph)
        lines = esc.split("&#10;") if "&#10;" in esc else esc.split("\n")

        # Re-escape since we're working with raw text
        raw_lines = text.split("\n")
        runs = []
        for i, line in enumerate(raw_lines):
            line_esc = self._escape(line)
            if i > 0:
                runs.append("<w:br/>")
            if line_esc:
                runs.append(f"{rpr}<w:t xml:space=\"preserve\">{line_esc}</w:t>")

        run_xml = "".join(f"<w:r>{r}</w:r>" if not r.startswith("<w:br") else f"<w:r>{r}</w:r>" for r in runs)

        if not run_xml:
            run_xml = f"<w:r>{rpr}<w:t></w:t></w:r>"

        return f"<w:p>{ppr}{run_xml}</w:p>"

    def build_document_xml(self):
        """Build the full document.xml content."""
        body_parts = []
        for style, text, bold in self.paragraphs:
            body_parts.append(self._make_para_xml(style, text, bold))

        body = "\n".join(body_parts)

        return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
            xmlns:cx="http://schemas.microsoft.com/office/drawing/2014/chartex"
            xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
            xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
            xmlns:v="urn:schemas-microsoft-com:vml"
            xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:w10="urn:schemas-microsoft-com:office:word"
            xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
            xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
            xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
            xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
            xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
            mc:Ignorable="w14 wp14">
  <w:body>
{body}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1800" w:bottom="1440" w:left="1800" w:header="720" w:footer="720" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>"""

    def save(self, filepath):
        """Save the .docx file."""
        doc_xml = self.build_document_xml()
        today = date.today().strftime("%Y-%m-%dT00:00:00Z")
        core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>{self._escape(self.title)}</dc:title>
  <dc:creator>Claude Code</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{today}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{today}</dcterms:modified>
</cp:coreProperties>"""

        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", CONTENT_TYPES)
            zf.writestr("_rels/.rels", ROOT_RELS)
            zf.writestr("word/_rels/document.xml.rels", WORD_RELS)
            zf.writestr("word/document.xml", doc_xml)
            zf.writestr("word/styles.xml", STYLES)
            zf.writestr("word/settings.xml", SETTINGS)
            zf.writestr("docProps/core.xml", core_xml)

        return filepath


# ── CONTENT PROCESSING ───────────────────────────────────────────────────────

def strip_markdown(text):
    """Strip markdown formatting for plain text output."""
    # Remove bold/italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Remove inline code
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Remove markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove image links
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    # Remove horizontal rules
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    return text


def add_text_block(doc, text):
    """Add a block of text to the doc, handling paragraphs and lists."""
    if not text or not text.strip():
        return

    paragraphs = re.split(r'\n{2,}', text.strip())

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check for heading markers (from synthesis structure)
        if para.startswith('#### '):
            doc.add_heading(strip_markdown(para[5:].strip()), level=3)
            continue
        elif para.startswith('### '):
            doc.add_heading(strip_markdown(para[4:].strip()), level=3)
            continue
        elif para.startswith('## '):
            doc.add_heading(strip_markdown(para[3:].strip()), level=2)
            continue
        elif para.startswith('# '):
            doc.add_heading(strip_markdown(para[2:].strip()), level=2)
            continue

        # Check if all lines are list items
        lines = para.split('\n')
        all_list = all(l.strip().startswith('- ') or l.strip().startswith('* ') or
                      l.strip().startswith('• ') or not l.strip() for l in lines)

        if all_list and any(l.strip() for l in lines):
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('* '):
                    doc.add_bullet(strip_markdown(line[2:]))
                elif line.startswith('• '):
                    doc.add_bullet(strip_markdown(line[2:]))
            continue

        # Mixed content - handle line by line
        current_text = strip_markdown(para)
        if current_text.strip():
            doc.add_para(current_text)


def read_synthesis(course_dir, course):
    """Read the synthesis markdown file."""
    # Try the repo copy first, then original source
    for path in [
        course_dir / "synthesis.md",
        SOURCE_DIR / course["synthesis"],
    ]:
        if path.exists():
            return path.read_text(encoding='utf-8', errors='replace')
    return f"[Synthesis not found for {course['name']}]"


def extract_videos(synthesis_text):
    """Extract video sections from the synthesis document."""
    # Pattern: ## Video N: ... or ## Lecture N: ...
    video_pattern = re.compile(
        r'(?m)^## (Video \d+|Lecture \d+)[:\s]+(.*?)$'
    )

    videos = []
    matches = list(video_pattern.finditer(synthesis_text))

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(synthesis_text)

        video_label = match.group(1)
        video_title = match.group(2).strip()
        video_content = synthesis_text[start:end]

        # Extract number
        num_match = re.search(r'\d+', video_label)
        num = int(num_match.group()) if num_match else i + 1

        # Extract subsections
        transcript_match = re.search(
            r'### Full Transcript\s*\n(.*?)(?=###|\Z)',
            video_content, re.DOTALL
        )
        summary_match = re.search(
            r'### Condensed Summary\s*\n(.*?)(?=###|\Z)',
            video_content, re.DOTALL
        )
        relopass_match = re.search(
            r'### ReloPass Application Notes\s*\n(.*?)(?=###|\Z)',
            video_content, re.DOTALL
        )

        videos.append({
            'num': num,
            'label': video_label,
            'title': video_title,
            'transcript': transcript_match.group(1).strip() if transcript_match else "",
            'summary': summary_match.group(1).strip() if summary_match else "",
            'relopass': relopass_match.group(1).strip() if relopass_match else "",
            'full_content': video_content,
        })

    return videos


def get_playlist_overview(synthesis_text):
    """Extract the playlist/course overview section."""
    # Try to get everything before the first ## Video section
    first_video = re.search(r'(?m)^## (Video \d+|Lecture \d+)', synthesis_text)
    if first_video:
        overview = synthesis_text[:first_video.start()].strip()
    else:
        # Just take the first section
        overview = synthesis_text[:3000]
    return overview


def get_cross_lecture_section(synthesis_text):
    """Extract cross-lecture or strategic summary sections."""
    # Look for patterns like "Strategic Summary", "Cross-Lecture", "ReloPass Application"
    patterns = [
        r'(?m)^## Cross-Lecture.*?\n(.*?)(?=^##|\Z)',
        r'(?m)^## Strategic.*?\n(.*?)(?=^##|\Z)',
        r'(?m)^## ReloPass.*?\n(.*?)(?=^##|\Z)',
        r'(?m)^## Implementation.*?\n(.*?)(?=^##|\Z)',
    ]

    results = {}
    for p in patterns:
        m = re.search(p, synthesis_text, re.DOTALL)
        if m:
            heading = re.search(r'^## (.+?)$', synthesis_text[m.start():], re.MULTILINE)
            key = heading.group(1) if heading else "Section"
            results[key] = m.group(1).strip()

    return results


# ── DOCUMENT GENERATOR ───────────────────────────────────────────────────────

def generate_docx(course):
    course_dir = BASE_DIR / course["dir"]
    output_path = BASE_DIR / course["filename"]

    print(f"\nGenerating: {course['filename']}")

    synthesis_text = read_synthesis(course_dir, course)

    doc = DocxBuilder(title=course["name"])

    # ── COVER PAGE ──────────────────────────────────────────
    doc.add_title("ReloPass Research Package")
    doc.add_para("")
    doc.add_para(course["name"], bold=True, center=True)
    doc.add_para("")
    doc.add_para("Stanford Course Research — Transcript Archive & ReloPass Application Analysis", center=True)
    doc.add_para("")
    doc.add_para("Generated: August 2026", center=True)
    doc.add_page_break()

    # ── SECTION 1: COURSE OVERVIEW ───────────────────────────
    doc.add_heading("1. Course Overview", level=1)
    overview = get_playlist_overview(synthesis_text)
    add_text_block(doc, overview)
    doc.add_page_break()

    # ── SECTION 2: PER-VIDEO/LECTURE CONTENT ─────────────────
    doc.add_heading("2. Per-Lecture Summaries & Full Transcripts", level=1)

    videos = extract_videos(synthesis_text)

    if videos:
        for video in videos:
            title_str = f"{video['label']}: {video['title']}"
            doc.add_heading(title_str[:120], level=2)

            # Condensed Summary
            if video['summary']:
                doc.add_heading("Condensed Summary", level=3)
                add_text_block(doc, video['summary'])

            # ReloPass notes per lecture (if present)
            if video['relopass']:
                doc.add_heading("ReloPass Application Notes (Lecture)", level=3)
                add_text_block(doc, video['relopass'])

            # Full Verbatim Transcript
            if video['transcript']:
                doc.add_heading("Full Verbatim Transcript", level=3)
                add_text_block(doc, video['transcript'])
            elif not video['summary'] and not video['relopass']:
                doc.add_para("(Transcript content embedded in course synthesis document.)")

            doc.add_page_break()
    else:
        # No video sections found — dump the whole synthesis structured
        doc.add_para("(No per-lecture sections identified — see course synthesis below.)")
        doc.add_page_break()

    # ── SECTION 3: CROSS-LECTURE SUMMARY ─────────────────────
    doc.add_heading("3. Cross-Lecture Strategic Summary", level=1)
    cross = get_cross_lecture_section(synthesis_text)
    if cross:
        for heading, content in cross.items():
            doc.add_heading(heading, level=2)
            add_text_block(doc, content)
    else:
        doc.add_para("(Cross-lecture summaries are integrated within the per-lecture ReloPass Application Notes above.)")

    doc.add_page_break()

    # ── SECTION 4: RELOPASS APPLICATION NOTES (GLOBAL) ──────
    doc.add_heading("4. ReloPass Application Notes", level=1)
    # Extract any top-level ReloPass section not already captured
    relopass_global = re.search(
        r'(?m)^## .*?ReloPass.*?\n(.*?)(?=^##|\Z)',
        synthesis_text, re.DOTALL
    )
    if relopass_global:
        add_text_block(doc, relopass_global.group(1))
    else:
        doc.add_para("ReloPass application notes are included within each lecture section above.")

    # ── SECTION 5: IMPLEMENTATION PREP ───────────────────────
    doc.add_heading("5. Implementation Preparation Notes", level=1)
    impl = re.search(
        r'(?m)^## .*?Implementation.*?\n(.*?)(?=^##|\Z)',
        synthesis_text, re.DOTALL
    )
    if impl:
        add_text_block(doc, impl.group(1))
    else:
        doc.add_para("See per-lecture ReloPass Application Notes and Cross-Lecture Strategic Summary for implementation guidance.")

    # ── SAVE ─────────────────────────────────────────────────
    doc.save(str(output_path))
    size_kb = output_path.stat().st_size // 1024
    print(f"  Saved: {output_path} ({size_kb} KB)")
    return str(output_path)


if __name__ == "__main__":
    generated = []
    errors = []
    for course in COURSES:
        try:
            path = generate_docx(course)
            generated.append(path)
        except Exception as e:
            print(f"ERROR generating {course['filename']}: {e}")
            import traceback
            traceback.print_exc()
            errors.append(course['filename'])

    print(f"\nDone. Generated {len(generated)}/{len(COURSES)} files.")
    for p in generated:
        size = Path(p).stat().st_size // 1024
        print(f"  {p} ({size} KB)")
    if errors:
        print(f"Errors: {errors}")
