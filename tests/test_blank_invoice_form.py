"""Regression checks: no fictional invoice data may be displayed before upload."""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InvoiceInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.fields = {}
        self.options = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == 'form':
            self.form = attr.get('id')
        if self.form in ('invoice-form', 'company-form'):
            if tag in ('input', 'textarea', 'select'):
                self.fields[(self.form, attr.get('id') or attr.get('name'))] = attr
            if tag == 'option':
                self.options.append((self.form, attr))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.form = None


def read_html(name):
    parser = InvoiceInputs()
    parser.feed((ROOT / 'static' / name).read_text(encoding='utf8'))
    return parser


def test_full_workspace_invoice_fields_start_blank():
    doc = read_html('index.html')
    for field in ('invoice-reference', 'invoice-amount', 'invoice-account', 'invoice-text', 'invoice-reviewed'):
        attrs = doc.fields[('invoice-form', field)]
        assert not attrs.get('value'), field
        assert 'checked' not in attrs, field
    assert doc.fields[('invoice-form', 'invoice-supplier')].get('required') is None
    assert any(form == 'invoice-form' and option.get('value') == '' for form, option in doc.options)


def test_quick_workspace_invoice_and_company_fields_start_blank():
    doc = read_html('quick.html')
    for form, field in (
        ('company-form', 'registration'), ('company-form', 'legal_name'),
        ('invoice-form', 'invoice_reference'), ('invoice-form', 'invoice-amount'),
        ('invoice-form', 'bank_account'), ('invoice-form', 'quick-invoice-reviewed'),
    ):
        attrs = doc.fields[(form, field)]
        assert not attrs.get('value'), (form, field)
        assert 'checked' not in attrs, (form, field)
    assert any(form == 'invoice-form' and option.get('value') == '' for form, option in doc.options)


def test_old_invoice_values_cleared_on_new_upload_and_failed_extraction():
    app = (ROOT / 'static' / 'app.js').read_text(encoding='utf8')
    quick = (ROOT / 'static' / 'quick.js').read_text(encoding='utf8')
    assert 'function clearFullInvoice()' in app
    assert "el('invoice-upload-file').addEventListener('change'" in app
    assert 'if(token!==fullInvoiceUploadToken)return' in app
    assert 'if(!fullInvoiceUploaded)' in app
    assert 'if(token===fullInvoiceUploadToken){clearFullInvoice()' in app
    assert 'function clearQuickInvoice()' in quick
    assert "byId('quick-upload-file').addEventListener('change'" in quick
    assert 'if(token!==quickInvoiceUploadToken)return' in quick
    assert 'if(!quickInvoiceUploaded)' in quick
    assert 'if(token===quickInvoiceUploadToken){clearQuickInvoice()' in quick


def test_supplier_name_extraction_only_suggests_and_is_unverified():
    from fraudfence.invoice_extraction import parse_invoice
    single = parse_invoice('Supplier: BuildRite Demo Supplies Pty Ltd\nInvoice No: INV-001\nTotal Amount Due: R850.00\nAccount Number: 0001112223')
    assert single['legal_name'] == 'BuildRite Demo Supplies Pty Ltd'
    assert single['review_required'] is True
    ambiguous = parse_invoice('Supplier: BuildRite Demo Supplies Pty Ltd\nSupplier: Another Fake Company Pty Ltd')
    assert ambiguous['legal_name'] is None
    assert any('Multiple possible legal name' in note for note in ambiguous['warnings'])
