import tempfile
import unittest
from pathlib import Path

import pymupdf

from analysis.report import build_report


class ReportTests(unittest.TestCase):
    def test_markdown_edits_reach_pdf_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'report.md'
            output = Path(directory) / 'report.pdf'
            text = '# First page\n\n## Our question\n\n**Our edited explanation** includes A & B and n<5.\n\n- A useful point\n\n# Second page\n\nA second paragraph.\n\n# Third page\n\n[Course](https://example.com)\n'
            source.write_text(text)
            build_report(source,output)
            self.assertEqual(source.read_text(),text)
            with pymupdf.open(output) as pdf:
                self.assertEqual(len(pdf),3)
                rendered='\n'.join(page.get_text() for page in pdf)
            self.assertIn('Our edited explanation',rendered)
            self.assertIn('A & B and n<5.',rendered)

    def test_overflow_preserves_previous_pdf_and_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'report.md'
            output = Path(directory) / 'report.pdf'
            text='# First page\n\n'+('Long paragraph. '*2500)+'\n\n# Second page\n\n# Third page\n'
            source.write_text(text)
            output.write_bytes(b'Previous PDF must survive')
            with self.assertRaisesRegex(ValueError,'too long'):
                build_report(source,output)
            self.assertEqual(output.read_bytes(),b'Previous PDF must survive')
            self.assertEqual(source.read_text(),text)
