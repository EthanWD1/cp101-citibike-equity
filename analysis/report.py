"""Compile the editable Markdown report, preserving its source and existing analysis."""
import json
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from PIL import Image

from .config import PROCESSED, FIGURES, SCOPES

REPO = "https://github.com/EthanWD1/cp101-citibike-equity"


def number(value, places=1):
    return "N/A" if pd.isna(value) else f"{value:,.{places}f}"


class Report:
    def __init__(self, path):
        self.pdf = canvas.Canvas(str(path), pagesize=letter)
        self.pdf.setTitle("Group PAIR — Citi Bike station density and neighborhood mobility")
        self.pdf.setAuthor("Timothy Phan and Ethan Deng")
        self.width = 536
        self.margin = 38
        self.page = 0
        self.y = 0

    def new_page(self, title):
        if self.page:
            if self.y < 38:
                raise ValueError(f"Report page {self.page} overflowed: y={self.y}")
            self.footer()
            self.pdf.showPage()
        self.page += 1
        self.y = 752
        self.pdf.setFillColor(colors.HexColor("#214c64"))
        self.pdf.setFont("Helvetica-Bold", 17)
        self.pdf.drawString(self.margin, self.y, title)
        self.y -= 21
        self.pdf.setStrokeColor(colors.HexColor("#b9c8cf"))
        self.pdf.line(self.margin, self.y + 8, self.margin + self.width, self.y + 8)

    def para(self, text, size=9.5, leading=12.4, gap=7, bold=False):
        style = ParagraphStyle("body", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                               leading=leading, textColor=colors.HexColor("#202b30"))
        paragraph = Paragraph(text, style)
        _, height = paragraph.wrap(self.width, 1000)
        paragraph.drawOn(self.pdf, self.margin, self.y - height)
        self.y -= height + gap

    def table(self, rows, widths, font=8.2):
        style = ParagraphStyle("table", fontName="Helvetica", fontSize=font, leading=font+2)
        content = [[Paragraph(escape(str(cell)), style) for cell in row] for row in rows]
        table = Table(content, colWidths=widths, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e5edf1")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LINEBELOW", (0,0), (-1,0), .6, colors.HexColor("#a6b9c5")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f5f7f8")]),
        ]))
        _, height = table.wrap(self.width, 1000)
        table.drawOn(self.pdf, self.margin, self.y-height)
        self.y -= height + 8

    def picture(self, filename, width):
        with Image.open(FIGURES / filename) as img:
            height = width * img.height / img.width
        self.pdf.drawImage(str(FIGURES / filename), self.margin + (self.width-width)/2,
                           self.y-height, width=width, height=height, preserveAspectRatio=True)
        self.y -= height + 5

    def footer(self):
        self.pdf.setFont("Helvetica", 8)
        self.pdf.setFillColor(colors.HexColor("#58646a"))
        self.pdf.drawString(self.margin, 23, "Group PAIR · CYPLAN 101 · Track B · Midterm report")
        self.pdf.drawRightString(574, 23, f"{self.page} / 3")

    def finish(self):
        if self.y < 38 or self.page != 3:
            raise ValueError(f"Expected three unclipped pages, got {self.page}, y={self.y}")
        self.footer()
        self.pdf.save()


def inline_markdown(text):
    """Translate the report's small Markdown subset into safe ReportLab markup."""
    pattern = r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^\s)]+\))'
    pieces = re.split(pattern, text)
    result = []
    for piece in pieces:
        if piece.startswith('**') and piece.endswith('**'):
            result.append('<b>' + escape(piece[2:-2]) + '</b>')
        elif piece.startswith('*') and piece.endswith('*'):
            result.append('<i>' + escape(piece[1:-1]) + '</i>')
        elif piece.startswith('`') and piece.endswith('`'):
            result.append('<font name="Courier">' + escape(piece[1:-1]) + '</font>')
        elif re.fullmatch(r'\[[^\]]+\]\([^\s)]+\)', piece):
            label, url = re.fullmatch(r'\[([^\]]+)\]\(([^\s)]+)\)', piece).groups()
            if not url.startswith(('https://', 'http://')):
                raise ValueError('Report links must use https:// or http://')
            result.append('<link href="' + escape(url, {'"':'&quot;'}) + '" color="#214c64">' + escape(label) + '</link>')
        else:
            result.append(escape(piece))
    return ''.join(result)


def markdown_blocks(text):
    """Yield headings, paragraphs, list items, images, and generated-table markers."""
    # Keep table markers but omit explanatory author comments.
    text = re.sub(r'<!--(.*?)-->', lambda m: m.group(0) if re.fullmatch(r'\s*table: \w+\s*',m.group(1)) else '',text,flags=re.S)
    paragraph = []
    for line in [*text.splitlines(), '']:
        stripped = line.strip()
        special = bool(re.match(r'^(#{1,2} |!\[|<!-- table: |[-*] |\d+\. )',stripped))
        if not stripped or special:
            if paragraph:
                yield 'paragraph', ' '.join(paragraph)
                paragraph = []
        if not stripped:
            continue
        if stripped.startswith('# '):
            yield 'page', stripped[2:]
        elif stripped.startswith('## '):
            yield 'heading', stripped[3:]
        elif stripped.startswith('<!-- table: '):
            match = re.fullmatch(r'<!-- table: (\w+) -->',stripped)
            if not match:
                raise ValueError('Use <!-- table: cleaning --> or <!-- table: boroughs -->')
            yield 'table', match.group(1)
        elif stripped.startswith('!['):
            match = re.fullmatch(r'!\[[^\]]*\]\(([^)]+)\)',stripped)
            if not match:
                raise ValueError('Put each Markdown image on its own line: ![caption](relative/path.png)')
            yield 'image', match.group(1)
        elif re.match(r'^[-*] ',stripped):
            yield 'item', '• ' + stripped[2:]
        elif re.match(r'^\d+\. ',stripped):
            yield 'item', stripped
        elif stripped.startswith(('```','###','|')):
            raise ValueError('Supported report Markdown: # page titles, ## headings, paragraphs, lists, bold, italics, links, and images.')
        else:
            paragraph.append(stripped)


def generated_table(report, name):
    """Keep numerical tables connected to processed outputs, independently of prose."""
    if name == 'cleaning':
        counts = json.loads((PROCESSED / 'validation.json').read_text())['counts']
        ledger = pd.read_csv(PROCESSED / 'cleaning_ledger.csv')
        rows = [['Stage','Before','Affected / excluded','After']]
        for key, label in [('missing_ride_id','Missing ride ID'),('duplicate_ride_id','Duplicate ride ID'),
                           ('invalid_start_time','Invalid start timestamp'),('outside_september','Start outside September')]:
            row = ledger.loc[ledger.stage.eq('trips') & ledger.step.eq(key)].iloc[0]
            rows.append([label,f'{row.before:,}',f'{row.affected:,}',f'{row.after:,}'])
        rows.append(['Eligible residential tracts',f"{counts['all_nyc_tracts']:,}",
                     f"{counts['all_nyc_tracts']-counts['eligible_tracts']:,}",f"{counts['eligible_tracts']:,}"])
        report.table(rows,[212,96,132,96])
    elif name == 'boroughs':
        boroughs = pd.read_csv(PROCESSED / 'borough_summary.csv').set_index('scope')
        rows = [['Borough','Eligible tracts','Zero stations (%)','Median stations / km²','Sept. departures*']]
        for scope in SCOPES[1:]:
            row = boroughs.loc[scope]
            rows.append([scope,f'{int(row.eligible_tracts):,}',number(row.zero_station_pct),
                         number(row.median_stations_per_km2,2),f'{int(row.departures_all_tracts):,}'])
        report.table(rows,[102,83,111,124,116],font=8.1)
    else:
        raise ValueError(f'Unknown generated table: {name}')


def build_report(source=Path('docs/report_source.md'), output=Path('Group_PAIR_midterm.pdf')):
    """Render Markdown without rewriting it; keep the previous PDF if rendering fails."""
    source, output = Path(source), Path(output)
    if not source.is_file():
        raise FileNotFoundError(f'Edit {source} to provide the report text before compiling.')
    blocks = list(markdown_blocks(source.read_text()))
    if sum(kind == 'page' for kind,_ in blocks) != 3 or not blocks or blocks[0][0] != 'page':
        raise ValueError('Keep exactly three # page titles in the Markdown report, starting with a page title.')
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        candidate = Path(temporary) / output.name
        report = Report(candidate)
        for kind, text in blocks:
            if kind == 'page':
                report.new_page(text)
            elif kind == 'heading':
                report.para(inline_markdown(text),size=10.5,leading=13,gap=4,bold=True)
            elif kind == 'table':
                generated_table(report,text)
            elif kind == 'image':
                path = (source.parent / text).resolve()
                if not path.is_file():
                    raise FileNotFoundError(f'Missing report image: {text}')
                report.picture(path,width=490 if path.name.startswith('01_') else 510)
            else:
                report.para(inline_markdown(text),size=9.2,leading=11.8,gap=6)
            if report.y < 38:
                raise ValueError(f'Report page {report.page} is too long. Shorten the Markdown text on that page; the previous PDF was kept.')
        report.finish()
        candidate.replace(output)
    print(f'Compiled {output} from {source}; Markdown source preserved.',flush=True)


if __name__ == '__main__':
    build_report()
