from scripts.collect_faa_space import discover_operational_links, parse_counts


def test_parse_counts_from_faa_text():
    html = b"<div>670 Licensed Launches 43 Licensed Reentries 46 Permitted (Experimental) Launches 24 Active Launch Licenses</div>"
    counts = parse_counts(html)
    assert counts["licensed_launches"] == 670
    assert counts["licensed_reentries"] == 43
    assert counts["permitted_experimental_launches"] == 46
    assert counts["active_launch_licenses"] == 24


def test_discover_operational_links_requires_all_four_sources():
    html = b"""<a href="/commercial">Recent Launch Data</a>
    <a href="https://explore.dot.gov/launches">Licensed Launches</a>
    <a href="https://explore.dot.gov/reentries">Licensed Reentries</a>
    <a href="https://explore.dot.gov/permits">Permitted Launches</a>"""
    links = discover_operational_links(html)
    assert set(links) == {
        "recent_launch_data",
        "licensed_launches",
        "licensed_reentries",
        "permitted_launches",
    }
