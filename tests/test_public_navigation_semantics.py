from html.parser import HTMLParser
from pathlib import Path


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def test_tonight_exposes_one_page_current_without_mislabeling_destinations():
    parser = LinkParser()
    parser.feed(Path("public/tonight/index.html").read_text(encoding="utf-8"))

    current = [link for link in parser.links if link.get("aria-current") == "page"]
    assert len(current) == 1
    assert current[0].get("href") == "./"

    page_current_hrefs = {link.get("href") for link in current}
    assert "#filters" not in page_current_hrefs
    assert "#events" not in page_current_hrefs
    assert "../calendar.ics" not in page_current_hrefs
    assert "../events.json" not in page_current_hrefs
