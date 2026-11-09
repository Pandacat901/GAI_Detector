import ast
import hashlib
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pypdf import PdfReader

# The source is a Colab export containing !pip; load only the functions under test.
source = Path(__file__).resolve().parents[1].joinpath('ai_detector.py').read_text()
source = '\n'.join(line for line in source.splitlines() if not line.startswith('!'))
tree = ast.parse(source)
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'clean', 'read_xml', 'metadata_inventory', 'excel_literal'}]
namespace = dict(re=re, ET=ET, zipfile=zipfile, PdfReader=PdfReader, OOXML={'.docx', '.xlsx', '.xlsm', '.pptx'})
exec(compile(ast.Module(body=functions, type_ignores=[]), 'ai_detector.py', 'exec'), namespace)

class InventoryTest(unittest.TestCase):
    def test_office_inventory_has_sources_and_named_properties(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            namespace['EXTRACT'] = root
            path = root / 'submission.docx'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('docProps/core.xml', '<core xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Alice</dc:creator><revision>3</revision></core>')
                z.writestr('docProps/custom.xml', '<Properties xmlns:vt="urn:vt"><property name="Project"><vt:lpwstr>Example</vt:lpwstr></property></Properties>')
                z.writestr('word/document.xml', '<doc xmlns:w="urn:w"><w:ins w:author="Bob" w:date="2024-01-01"><w:t>private body</w:t></w:ins></doc>')
                z.writestr('word/_rels/document.xml.rels', '<Relationships><Relationship TargetMode="External" Type="hyperlink" Target="https://example.test"/></Relationships>')
                z.writestr('word/webextensions/webextension1.xml', '<webextension><reference id="WA123" storeType="OMEX"/></webextension>')
            rows = namespace['metadata_inventory'](path)
            values = {(r['source'], r['field'], r['value']) for r in rows}
            self.assertIn(('docProps/core.xml', 'creator', 'Alice'), values)
            self.assertIn(('docProps/custom.xml', 'custom:Project (lpwstr)', 'Example'), values)
            self.assertIn(('word/document.xml', 'ins_author', 'Bob'), values)
            self.assertIn(('word/_rels/document.xml.rels', 'external_relationship_target', 'https://example.test'), values)
            self.assertIn(('word/webextensions/webextension1.xml', 'add_in_id', 'WA123'), values)
            self.assertNotIn('private body', [r['value'] for r in rows])

    def test_excel_formula_is_literal(self):
        self.assertEqual(namespace['excel_literal']('=1+1'), "'=1+1")
        self.assertEqual(namespace['excel_literal']('Alice'), 'Alice')

if __name__ == '__main__':
    unittest.main()
