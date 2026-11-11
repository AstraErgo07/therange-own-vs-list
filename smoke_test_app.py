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
        assert any(c.value.startswith("Own vs List v1.0") for c in at.caption), page
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    cols = [list(d.value.columns) for d in at.dataframe]
    assert sum(any("Avg selling price per unit" in c for c in cs) for cs in cols) >= 2, cols
    assert any(e.label == "How these numbers are worked out" for e in at.expander)
    assert any("1P profit per unit" in str(t.value.to_dict()) for t in at.table)
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
    ok_footer = any("Not affiliated with The Range or CDS" in c.value and "v1.0" in c.value
                    and "Made by Ami Sata" in c.value for c in at.caption)
    assert not at.exception and ok_footer and any("Own vs List" in t.value for t in at.title)
    print("launcher ok")
finally:
    if BACKUP is None:
        LOG.unlink(missing_ok=True)
    else:
        LOG.write_bytes(BACKUP)
print("SMOKE TEST PASSED")
