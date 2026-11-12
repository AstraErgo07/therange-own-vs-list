"""smoke_test_app.py - headless check that every page loads and the decision buttons work.
Run:  python smoke_test_app.py   (any test rows in the local decision log are removed afterwards)"""
import os
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

os.chdir(Path(__file__).parent)
sys.path.insert(0, ".")
PAGE = "app_pages/cds_own_vs_list_page.py"
DATA = Path("cds_own_vs_list/range_listings.csv")
LOG = Path("cds_own_vs_list/decisions.csv")
BACKUP = LOG.read_bytes() if LOG.exists() else None
try:
    for page in [PAGE, "app_pages/method_page.py"]:
        at = AppTest.from_file(page, default_timeout=60).run()
        print(page, "exceptions:", [e.value for e in at.exception], "| dataframes:", len(at.dataframe))
        assert not at.exception, page
        assert any(c.value.startswith("Own vs List v1.1") for c in at.caption), page
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    cols = [list(d.value.columns) for d in at.dataframe]
    assert sum(any("Avg selling price per unit" in c for c in cs) for cs in cols) >= 2, cols
    assert any(e.label == "How these numbers are worked out" for e in at.expander)
    assert any("1P contribution per unit" in str(t.value.to_dict()) for t in at.table)
    # unambiguous counts and a category selector
    page_text = " ".join(getattr(m, "value", "") or "" for m in list(at.markdown) + list(at.caption) + list(at.info))
    assert "47 marketplace listings assessed across 8 categories" in page_text, page_text[:500]
    assert "35 of The Range's own items are used only as price/contribution comparisons" in page_text
    assert "not assessed" in page_text
    segs = list(at.segmented_control)
    assert segs, "expected a category segmented control"
    labels = []
    for s in segs:
        opts = getattr(s, "options", None) or getattr(s, "value", None)
        labels.append((getattr(s, "label", None), opts, str(s)))
    print("segmented_control:", labels)
    # open lighting via the query param used by the selector
    at2 = AppTest.from_file(PAGE, default_timeout=60)
    at2.query_params["category"] = "lighting"
    at2.run()
    assert not at2.exception, [e.value for e in at2.exception]
    # ranking table should only show lighting (6 marketplace listings)
    lighting_ok = False
    for d in at2.dataframe:
        cs = list(d.value.columns)
        if "Category" in cs and "SKU" in cs:
            cats = set(d.value["Category"].astype(str))
            print("filtered table categories:", cats, "rows", len(d.value))
            if cats and cats <= {"lighting"} and len(d.value) == 6:
                lighting_ok = True
    assert lighting_ok, "query param ?category=lighting should show 6 lighting rows"
    # override without a reason -> error; accept -> log written
    [b for b in at.button if b.key and b.key.startswith("cds_ovr_")][0].click().run()
    print("override w/o reason errors:", [e.value for e in at.error])
    assert at.error
    [b for b in at.button if b.key and b.key.startswith("cds_acc_")][0].click().run()
    print("accept success:", [s.value for s in at.success])
    assert at.success and LOG.exists()
    # a missing data file shows the error on the page, not a crash
    hidden = DATA.with_suffix(".bak")
    DATA.rename(hidden)
    try:
        at = AppTest.from_file(PAGE, default_timeout=60).run()
        assert not at.exception and any("Something went wrong" in e.value for e in at.error), at.exception
        print("error wrapper ok")
    finally:
        hidden.rename(DATA)
    # launcher: default page, footer with version
    at = AppTest.from_file("streamlit_app.py", default_timeout=60).run()
    ok_footer = any("Not affiliated with The Range or CDS" in c.value and "v1.1" in c.value
                    and "Made by Ami Sata" in c.value for c in at.caption)
    assert not at.exception and ok_footer and any("Own vs List" in t.value for t in at.title)
    print("launcher ok")
finally:
    if BACKUP is None:
        LOG.unlink(missing_ok=True)
    else:
        LOG.write_bytes(BACKUP)
print("SMOKE TEST PASSED")
