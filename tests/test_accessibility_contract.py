from scripts.enforce_accessibility_contract import enforce, verify


def test_enforce_adds_keyboard_navigation_contract() -> None:
    source = '<html><head><style>a{color:inherit}</style></head><body><main class="shell"><a href="#">link</a><button>go</button><input><select></select><summary>more</summary></main></body></html>'
    rendered = enforce(source)

    assert rendered.index('class="skip-link"') < rendered.index('id="main-content"')
    assert 'href="#main-content"' in rendered
    assert '<main id="main-content" class="shell" tabindex="-1">' in rendered
    assert ':where(a,button,input,select,summary):focus-visible' in rendered
    assert '.skip-link:focus' in rendered
    verify(rendered)


def test_enforce_is_idempotent() -> None:
    source = '<html><head><style></style></head><body><main class="shell"></main></body></html>'
    once = enforce(source)
    assert enforce(once) == once
