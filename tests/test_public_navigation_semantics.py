from html.parser import HTMLParser
from pathlib import Path


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def test_tonight_has_one_page_current_and_no_section_or_resource_mislabel():
    parser = LinkParser()
    parser.feed(Path("public/tonight/index.html").read_text(encoding="utf-8"))
    current = [link for link in parser.links if link.get("aria-current") == "page"]
    assert len(current) == 1
    assert current[0].get("href") == "./"
    assert current[0].get("rel") == "home"
    assert not {link.get("href") for link in current} & {
        "#filters", "#events", "../calendar.ics", "../events.json",
    }
