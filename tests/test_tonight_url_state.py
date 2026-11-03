"""Untrusted shared URLs must not create unbounded Tonight DOM work."""
import json
import re
import subprocess
from pathlib import Path

SCRIPT = Path("public/tonight/tonight.js")


def _run(query: str, *, populate: bool = False) -> dict:
    source = SCRIPT.read_text(encoding="utf-8")
    read = re.search(r"function readUrl\(\)\{.*?\}function writeUrl\(\)\{.*?\}(?=function records)", source)
    assert read, "URL parser/serializer must remain testable"
    pop = re.search(r"function populate\(\)\{.*?\}(?=function bind)", source)
    assert pop, "dataset-dependent filter validation must remain testable"
    js = """
const PAGE=30,MAX_RENDER=300,MAX_QUERY_CHARS=256;
const state={q:'',range:'today',category:'all',source:'all',deadlines:false,limit:PAGE,
             events:[{category:'VRChat',source:'official'}],historyOff:false};
const location={search:QUERY,pathname:'/tonight/'};
let canonical='';
const history={replaceState:(_a,_b,value)=>{canonical=value}};
const elements={};
const $=selector=>elements[selector]??=( {innerHTML:'',value:'',checked:false,setAttribute(){}});
const category=e=>e.category,source=e=>e.source,esc=v=>v;
""" .replace("QUERY", json.dumps(query, ensure_ascii=False))
    js += read.group(0) + "\n" + pop.group(0) + "\nreadUrl();\n"
    if populate:
        js += "populate();\n"
    js += "writeUrl();console.log(JSON.stringify({state,canonical}));"
    completed = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def test_untrusted_limit_and_range_cannot_force_unbounded_render():
    for value in ("999999999", "Infinity", "-1", "31.5", "31", "1e9"):
        result = _run(f"?range=garbage&limit={value}")
        assert result["state"]["range"] == "today"
        assert 30 <= result["state"]["limit"] <= 300
        assert result["state"]["limit"] % 30 == 0
        assert "range=" not in result["canonical"]
    assert _run("?limit=999999999")["state"]["limit"] == 30
    assert _run("?limit=999999990")["state"]["limit"] == 300
    assert _run("?limit=31.5")["state"]["limit"] == 30


def test_canonical_roundtrip_and_dataset_option_validation():
    valid = _run("?q=%E5%A4%A7%E9%98%AA&range=week&category=VRChat&source=official&deadlines=1&limit=90", populate=True)
    assert valid["state"]["q"] == "大阪"
    assert valid["state"]["limit"] == 90
    assert "category=VRChat" in valid["canonical"]
    assert "limit=90" in valid["canonical"]
    invalid = _run("?category=not-a-category&source=unknown&limit=Infinity", populate=True)
    assert invalid["state"]["category"] == "all"
    assert invalid["state"]["source"] == "all"
    assert "category=" not in invalid["canonical"]
    assert "source=" not in invalid["canonical"]
    assert "limit=" not in invalid["canonical"]


def test_long_untrusted_query_is_rejected_not_silently_truncated():
    oversized = _run("?q=" + "あ" * 257, populate=True)
    assert oversized["state"]["q"] == ""
    assert "256文字" in oversized["state"]["urlWarning"]
    assert "q=" not in oversized["canonical"]
    boundary = _run("?q=" + "あ" * 256, populate=True)
    assert boundary["state"]["q"] == "あ" * 256
    assert "q=" in boundary["canonical"]
    assert _run("?" + boundary["canonical"].split("?", 1)[1])["state"]["q"] == "あ" * 256


def test_repeated_query_keys_use_first_value_deterministically():
    result = _run("?q=%E5%A4%A7%E9%98%AA&q=%E6%9D%B1%E4%BA%AC&range=week&range=all")
    assert result["state"]["q"] == "大阪"
    assert result["state"]["range"] == "week"
    assert result["canonical"].count("q=") == 1
    assert result["canonical"].count("range=") == 1
