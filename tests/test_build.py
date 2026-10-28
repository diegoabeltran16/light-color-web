from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build import BuildError, _audit_component, _render, build, compose_html, render_product_detail, render_service_detail, validate_base_path, validate_connected_preview_entries, validate_destination, validate_manifest_data, validate_product_demo_registry, validate_empty_product_registry, validate_public_entries, validate_service_registry, validate_source  # noqa: E402
from validate_public import validate_output_tree  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "build-minimal"


class ManifestTests(unittest.TestCase):
    def test_manifest_json_and_schema(self):
        data = json.loads((FIXTURE / "site-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(validate_manifest_data(data)), 10)

    def test_rejects_traversal_and_absolute_sources(self):
        for source in ("../outside.html", "/etc/passwd", "a\\b.html", "C:/private.txt", "assets/CON.txt"):
            with self.subTest(source=source), self.assertRaises(BuildError):
                validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [
                    {"source": source, "output": "index.html", "kind": "html"}
                ]})

    def test_component_allowlist_rejects_unknown_names(self):
        from build import validate_component_names
        with self.assertRaises(BuildError):
            validate_component_names({"components": ["header", "arbitrary/path"]})

    def test_public_mode_rejects_fixture_source(self):
        entries = validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [
            {"source": "index.html", "output": "index.html", "kind": "html", "root": "fixture"}
        ]})
        with self.assertRaisesRegex(BuildError, "root=src"):
            validate_public_entries(entries)

    def test_public_mode_blocks_historical_dcastell_review_assets(self):
        entries = validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [
            {"source": route, "output": route, "kind": "html", "root": "src"}
            for route in (
                "index.html", "nosotros/index.html", "servicios/index.html",
                "servicios/corte-de-cabello/index.html", "servicios/coloracion-con-tinte/index.html",
                "servicios/henna-capilar/index.html", "productos/index.html",
            )
        ] + [
            {"source": "assets/home/review-400.jpg", "output": "assets/home/review-400.jpg", "kind": "asset", "root": "src"}
        ]})
        with self.assertRaisesRegex(BuildError, "revisión editorial"):
            validate_public_entries(entries)

    def test_rejects_duplicate_outputs_case_insensitively(self):
        entries = [
            {"source": "a.html", "output": "index.html", "kind": "html"},
            {"source": "b.html", "output": "INDEX.html", "kind": "html"},
        ]
        with self.assertRaises(BuildError):
            validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": entries})

    def test_rejects_file_directory_collision(self):
        entries = [
            {"source": "a.html", "output": "assets", "kind": "asset"},
            {"source": "b.html", "output": "assets/app.js", "kind": "js"},
        ]
        with self.assertRaises(BuildError):
            validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": entries})

    def test_rejects_unsupported_kind_and_hidden_output(self):
        for item in (
            {"source": "a", "output": "a.html", "kind": "python"},
            {"source": "a", "output": ".secret", "kind": "asset"},
            {"source": ".env", "output": "data.txt", "kind": "asset"},
            {"source": "tests/fixtures/demo.json", "output": "data.json", "kind": "asset"},
        ):
            with self.subTest(item=item), self.assertRaises(BuildError):
                validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [item]})


class PathTests(unittest.TestCase):
    def test_base_paths(self):
        self.assertEqual(validate_base_path("/"), "/")
        self.assertEqual(validate_base_path("/light-color-web/"), "/light-color-web/")
        for invalid in ("", "light-color-web", "/../", "/x//", "//host/"):
            with self.subTest(invalid=invalid), self.assertRaises(BuildError):
                validate_base_path(invalid)

    def test_missing_source_rejected(self):
        with self.assertRaises(BuildError):
            validate_source(FIXTURE, "not-there.svg")

    def test_symlink_source_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.txt"
            outside.write_text("private", encoding="utf-8")
            (root / "escape.txt").symlink_to(outside)
            with self.assertRaises(BuildError):
                validate_source(root, "escape.txt")

    def test_output_traversal_rejected(self):
        with self.assertRaises(BuildError):
            validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [
                {"source": "index.html", "output": "../outside.html", "kind": "html"}
            ]})

    def test_output_must_be_in_dedicated_temporary_directory(self):
        with self.assertRaises(BuildError):
            validate_destination(ROOT / "temporary-output", ROOT)
        with self.assertRaises(BuildError):
            validate_destination(Path("/tmp") / "site", ROOT)

    def test_page_renderer_rejects_javascript_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            page = Path(temporary) / "unsafe.html"
            for content, message in (
                ('<a href="javascript:alert(1)">bad</a>', "javascript"),
                ('<img srcset="javascript:alert(1) 1x" alt="bad">', "javascript"),
                ('<script src="https://cdn.invalid/app.js"></script>', "terceros"),
            ):
                with self.subTest(content=content):
                    page.write_text(content, encoding="utf-8")
                    with self.assertRaisesRegex(BuildError, message):
                        _render({"kind": "html", "source": "unsafe.html"}, page, "/", [], {})


class BuildTests(unittest.TestCase):
    def test_service_cards_keep_image_and_content_in_separate_vertical_flow(self):
        script = (ROOT / "src" / "scripts" / "catalog.js").read_text(encoding="utf-8")
        css = (ROOT / "src" / "styles" / "services.css").read_text(encoding="utf-8")
        reference_css = (ROOT / "R003" / "catalog.css").read_text(encoding="utf-8")

        self.assertIn("var content = record.detailStatus === 'ready' ? document.createElement('a') : document.createElement('div')", script)
        self.assertIn("content.append(media, body);", script)
        self.assertIn("content.className = 'lc-services__card-content';", script)
        self.assertIn("body.className = 'lc-catalog__card-body';", script)
        self.assertIn("min-height: 330px; flex: 1 0 auto; flex-direction: column", css)
        self.assertIn("height: 190px; min-height: 190px; flex: 0 0 190px", css)
        self.assertIn("width: 100%; height: 190px; object-fit: cover", css)
        self.assertIn("overflow: hidden", css[css.index(".lc-services__card-media {"):css.index(".lc-services__card-media img {")])
        mobile = css[css.index("@media (max-width: 640px)"):css.index("@media (prefers-reduced-motion")]
        self.assertIn(".lc-services__card-media img { height: auto; aspect-ratio: 1.35; }", mobile)
        self.assertNotIn(".lc-services__card-media img { height: 100%;", mobile)
        self.assertIn("position: static; display: flex; min-width: 0; flex: 1 0 auto", css)
        self.assertIn("aspect-ratio: 1.35", css)
        self.assertIn(".lc-catalog--services .lc-services__card-content { display:flex; height:100%; flex:1; flex-direction:column", reference_css)
        self.assertIn(".lc-catalog--services .lc-services__card-media { height:190px; min-height:190px; }", reference_css)
        self.assertNotRegex(css, r"\.lc-services__card(?:-content|-media)?\s*\{[^}]*position:\s*absolute")

    def test_home_preview_preserves_required_section_structure(self):
        html = (ROOT / "src" / "pages" / "home.html").read_text(encoding="utf-8")
        css = (ROOT / "src" / "styles" / "home.css").read_text(encoding="utf-8")
        js = (ROOT / "src" / "scripts" / "home.js").read_text(encoding="utf-8")
        footer = (ROOT / "src" / "components" / "footer.html").read_text(encoding="utf-8")
        shared_css = (ROOT / "src" / "styles" / "shared.css").read_text(encoding="utf-8")
        shared_js = (ROOT / "src" / "scripts" / "shared.js").read_text(encoding="utf-8")

        self.assertEqual(html.count('class="home-offering home-offering--'), 2)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertIn(".home-offerings { grid-template-columns: 1fr; }", css)
        self.assertEqual(html.count("class=\"home-principles__grid\""), 1)
        self.assertEqual(html.count("class=\"home-principles__commitments\""), 1)
        self.assertEqual(html.count("class=\"home-principles__commitments\" aria-label"), 1)
        self.assertEqual(html.count("home-principles__commitment-icon"), 4)
        self.assertIn("home-principles__divider", html)
        self.assertNotIn("home-contact", html)
        self.assertIn("class=\"lc-site-footer__art\"", footer)
        self.assertIn("grid-template-columns: 1.15fr 1fr .9fr 1.1fr", shared_css)
        self.assertIn("grid-template-columns: 1fr; width: calc(100% - 36px)", shared_css)
        self.assertIn("class=\"lc-site-footer__social\"", footer)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn('id="lc-footer-map-frame"', footer)
        self.assertLess(footer.index('id="lc-footer-map-frame"'), footer.index('class="lc-site-footer__directions"'))
        self.assertIn('data-lc-map-button', footer)
        self.assertIn("lc-site-footer__map-icon", footer)
        self.assertIn("lc-site-footer__map-hint", footer)
        self.assertIn("height: 250px", shared_css[shared_css.index(".lc-site-footer__map {"):shared_css.index(".lc-site-footer__map-button {")])
        self.assertIn("container.replaceChildren(frame)", shared_js)
        self.assertIn("new URL('https://www.google.com/maps/embed?", shared_js)
        self.assertIn("frame.loading = 'lazy'", shared_js)
        self.assertIn("button.getAttribute('aria-controls')", shared_js)
        self.assertIn("document.querySelectorAll('[data-lc-map-button]')", shared_js)
        self.assertIn("button.dataset.mapReady === 'true'", shared_js)
        self.assertNotIn("fetch(", shared_js)
        self.assertNotIn("XMLHttpRequest", shared_js)
        self.assertNotIn("google.com/maps/embed", js)
        self.assertNotIn("google.com/maps/embed", html)
        self.assertNotIn('class="lc-site-footer"', html)
        self.assertIn('class="lc-site-footer"', footer)
        self.assertEqual(html.count("<!-- lc:include footer -->"), 1)
        self.assertEqual(html.count("<!-- lc:include whatsapp -->"), 1)
        self.assertEqual(html.count("<!-- lc:include"), 4)
        self.assertIn('<br class="home-hero__desktop-break">', html)
        self.assertIn('class="home-hero__first-line"', html)
        self.assertIn('class="home-hero__accent"', html)
        self.assertIn(".home-hero__accent { color: #f5627f; }", css)
        self.assertIn("grid-template-columns: minmax(0, 780px) minmax(0, 1fr)", css)
        self.assertIn(".home-hero__first-line { white-space: nowrap; }", css)
        self.assertIn("@media (min-width: 1025px) and (max-width: 1199px)", css)
        self.assertIn(".home-hero__copy { position: static;", css)
        self.assertEqual(html.count('class="home-review-card home-review-card--'), 2)
        self.assertEqual(html.count('data-editorial-review="historical-dcastell-awaiting-review"'), 2)
        self.assertEqual(html.count('{{base}}assets/home/review-400.jpg'), 4)
        self.assertEqual(html.count('{{base}}assets/home/review-300.jpg'), 2)
        hero_visual = html.split('<div class="home-hero__visual">', 1)[1].split("</div>", 1)[0]
        self.assertIn('class="home-review-card home-review-card--copy"', hero_visual)
        self.assertLess(hero_visual.index('home-review-card--copy'), hero_visual.index('home-hero__silhouette'))
        copy_card_rule = css.split(".home-review-card--copy {", 1)[1].split("}", 1)[0]
        self.assertIn("top: clamp(175px, 35%, 190px)", copy_card_rule)
        self.assertIn("left: clamp(-205px, -15vw, -165px)", copy_card_rule)
        self.assertIn("@media (min-width: 1200px)", css)
        self.assertIn(".home-review-card--visual { position: absolute; right: clamp(8px, 2vw, 28px); bottom: clamp(18px, 5%, 42px)", css)
        self.assertNotIn("home-visitor-counter", html + css)
        self.assertNotIn("Referencia visual provisional", html)
        testimonial_rule = css.split(".home-testimonial {", 1)[1].split("}", 1)[0]
        self.assertIn("box-shadow: 0 1px 3px rgb(35 72 87 / 6%)", testimonial_rule)
        self.assertIn("width: min(100%, 560px)", css)
        self.assertIn(".home-hero__desktop-break { display: none; }", css)
        self.assertIn("@media (min-width: 768px) and (max-width: 1023px)", css)
        self.assertIn(".home-principles__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }", css)
        self.assertIn(".home-benefits { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));", css)
        self.assertIn(".home-benefits { grid-template-columns: repeat(4, minmax(0, 1fr)); }", css)
        self.assertIn(".home-benefits li:nth-child(1) { grid-column: 1 / 3; }", css)
        self.assertIn(".home-benefits li:nth-child(2) { grid-column: 3 / 5; }", css)
        self.assertIn(".home-benefits li:nth-child(3) { grid-column: 2 / 4; }", css)
        self.assertIn(".home-benefits a:focus-visible", css)
        self.assertIn(".home-benefits a {", css)
        self.assertIn("text-decoration: none", css[css.index(".home-benefits a {"):css.index(".home-benefits a:focus-visible")])
        self.assertIn(".home-offering--services .home-eyebrow { color: #8e2338; }", css)
        self.assertNotIn(".home-offering__copy .home-eyebrow span", css)
        self.assertIn(".home-principles { padding: clamp(24px, 2.2vw, 32px) 24px;", css)
        self.assertIn(".home-offerings { display: grid;", css)
        self.assertIn("margin: 0 auto 24px;", css)
        self.assertNotIn("height:", css[css.index(".home-principles {"):css.index(".home-section-inner")])
        self.assertIn("class=\"home-testimonials__stop\" type=\"button\" aria-label=\"Detener la rotación automática de reseñas\"", html)
        self.assertIn("home-testimonials__status\" aria-live=\"polite\"", html)
        self.assertNotIn("home-testimonials__toggle", html + css + js)

        self.assertIn(".home-testimonials__stop:focus-visible", css)
        self.assertIn("setAttribute('aria-label', label)", js)
        self.assertIn("setAttribute('aria-disabled', stopped ? 'true' : 'false')", js)
        self.assertIn("if (userPaused || reducedMotion.matches) return", js)
        self.assertIn("stopForVisitor();", js)
        self.assertEqual(js.count("window.setInterval("), 1)
        self.assertIn("var delay = 10000;", js)
        self.assertIn("window.clearInterval", js)
        self.assertIn("focusin", js)
        self.assertIn("focusout", js)
        self.assertIn("pointerdown", js)
        self.assertIn("touchstart", js)
        self.assertIn("wheel", js)
        self.assertIn("pauseForKeyboardScroll", js)
        self.assertIn("'ArrowLeft', 'ArrowRight', 'Home', 'End', 'PageUp', 'PageDown'", js)
        self.assertIn("aria-live=\"polite\"", html)
        self.assertIn("reducedMotion.matches", js)
        self.assertIn("if (!userPaused && !reducedMotion.matches)", js)
        self.assertNotIn("userPaused = false", js.split("function applyMotionPreference()", 1)[1])
        self.assertIn("if (userPaused) stopTimer();\n    else startTimer();", js)
        self.assertIn("!isVisible()", js)
        self.assertIn("carousel.scrollTo", js)
        social = footer.split('class="lc-site-footer__social"', 1)[1].split('class="lc-site-footer__hours"', 1)[0]
        self.assertNotIn("3125973539</a>", social)
        self.assertIn("313 3226726", footer)
        self.assertIn("phone=573125973539", html)

    def test_shared_header_uses_only_a_subtle_divider(self):
        css = (ROOT / "src" / "styles" / "shared.css").read_text(encoding="utf-8")
        header_rule = css.split(".lc-site-header {", 1)[1].split("}", 1)[0]
        detail_rule = css.split(".lc-site-header--detail {", 1)[1].split("}", 1)[0]

        self.assertIn("border-bottom: 1px solid #edf1f2", header_rule)
        self.assertIn("box-shadow: none", header_rule)
        self.assertNotIn("border: 0", detail_rule)

    def test_connected_preview_manifest_is_explicit_and_public_release_stays_incomplete(self):
        manifest = json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
        entries = validate_manifest_data(manifest)
        validate_connected_preview_entries(entries, manifest["components"])
        sources = {entry["source"] for entry in entries}
        self.assertNotIn("docs/privacy-policy-preparation.md", sources)
        self.assertTrue((ROOT / "docs" / "privacy-policy-preparation.md").is_file())
        with self.assertRaisesRegex(BuildError, "revisión editorial"):
            validate_public_entries(entries)
        altered_entries = [*entries, {
            "source": "assets/unlisted.svg", "output": "assets/unlisted.svg", "kind": "asset", "root": "src"
        }]
        with self.assertRaisesRegex(BuildError, "allowlist explícita"):
            validate_connected_preview_entries(altered_entries, manifest["components"])

    def test_connected_preview_builds_products_demo_routes_from_src_under_root_and_prefix(self):
        results = []
        expected_outputs = {
            entry["output"] for entry in validate_manifest_data(
                json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
            )
        } | {"build-manifest.json"} | {
            *(f"productos/demo-{number:02d}/index.html" for number in range(1, 4)),
            *(f"assets/products/product-demo-{letter}{suffix}.svg" for letter in "abc" for suffix in ("", "-alt")),
        }
        for base in ("/", "/light-color-web/"):
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "home-preview"
                result = build("preview-connected", base, output, ROOT)
                self.assertEqual(result["mode"], "preview-connected")
                self.assertTrue((output / "index.html").is_file())
                self.assertTrue((output / "nosotros" / "index.html").is_file())
                self.assertTrue((output / "servicios" / "index.html").is_file())
                self.assertTrue((output / "productos" / "index.html").is_file())
                for slug in ("corte-de-cabello", "coloracion-con-tinte", "henna-capilar"):
                    self.assertTrue((output / "servicios" / slug / "index.html").is_file())
                products = (output / "productos" / "index.html").read_text(encoding="utf-8")
                demo_data = json.loads((output / "assets" / "products" / "products.json").read_text(encoding="utf-8"))
                self.assertEqual(len(demo_data), 3)
                self.assertIn('data-catalog-type="products"', products)
                self.assertIn("Aún no hay productos publicados", products)
                self.assertIn("products-demo.json", (output / "build-manifest.json").read_text(encoding="utf-8"))
                for number in range(1, 4):
                    detail = (output / "productos" / f"demo-{number:02d}" / "index.html").read_text(encoding="utf-8")
                    self.assertIn("demostración local", detail.lower())
                    self.assertEqual(detail.count("data-gallery-thumb"), 2)
                    self.assertIn(f'href="{base}productos/"', detail)
                self.assertEqual(
                    {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()},
                    expected_outputs,
                )
                html = (output / "index.html").read_text(encoding="utf-8")
                css = (output / "assets/home.css").read_text(encoding="utf-8")
                js = (output / "assets/home.js").read_text(encoding="utf-8")
                shared_css = (output / "assets/shared.css").read_text(encoding="utf-8")
                shared_js = (output / "assets/shared.js").read_text(encoding="utf-8")
                for generated in (html, css, js, shared_css, shared_js):
                    self.assertNotIn("{{base}}", generated)
                declared_files = {
                    path.relative_to(output).as_posix()
                    for path in output.rglob("*") if path.is_file()
                }
                for generated in (html, css):
                    for local_path in re.findall(re.escape(base) + r"([^\s\"')>,]+)", generated):
                        if local_path.startswith("assets/"):
                            self.assertIn(local_path, declared_files, local_path)
                self.assertIn(f'href="{base}assets/brand/favicon-32.png"', html)
                self.assertIn('aria-current="page">Inicio</a>', html)
                self.assertIn(f'href="{base}servicios/"', html)
                self.assertIn(f'href="{base}productos/"', html)
                self.assertIn(f'srcset="{base}assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-300x300.webp 300w', html)
                self.assertIn(f'url("{base}assets/home/promo-backdrop.jpg")', css)
                self.assertEqual(html.count('class="lc-whatsapp-float"'), 1)
                self.assertEqual(html.count('class="home-testimonial"'), 4)
                self.assertIn('class="home-testimonials__viewport" role="region"', html)
                self.assertNotIn("joinchat", html.lower())
                self.assertNotIn("R003/", html)
                self.assertNotIn("wp-content/", html)
                self.assertNotIn("data-demo-mode", html)
                self.assertNotIn("innerHTML", js)
                self.assertIn("prefers-reduced-motion", js)
                self.assertIn("setInterval", js)
                self.assertNotIn("google.com/maps/embed", html)
                self.assertNotIn('class="home-contact"', html)
                self.assertEqual(html.count('id="site-footer"'), 1)
                self.assertIn('class="lc-site-footer__brand"', html)
                self.assertIn('class="lc-site-footer__social"', html)
                self.assertIn('class="lc-site-footer__hours"', html)
                self.assertIn('class="lc-site-footer__contact"', html)
                self.assertEqual(html.count('class="lc-site-footer__copyright"'), 1)
                self.assertEqual(html.count('id="lc-footer-map-frame"'), 1)
                self.assertEqual(html.count('data-lc-map-button'), 1)
                self.assertIn("document.createElement('iframe')", shared_js)
                self.assertIn("button.getAttribute('aria-controls')", shared_js)
                self.assertIn("container.replaceChildren(frame)", shared_js)
                self.assertIn("if (container.querySelector('iframe')) return", shared_js)
                inventory = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(inventory["mode"], "preview-connected")
                about = (output / "nosotros" / "index.html").read_text(encoding="utf-8")
                about_css = (output / "assets/about.css").read_text(encoding="utf-8")
                for generated in (about, about_css):
                    self.assertNotIn("{{base}}", generated)
                self.assertIn(f'href="{base}nosotros/"', about)
                self.assertIn('aria-current="page">Nosotros</a>', about)
                self.assertEqual(about.count('id="site-footer"'), 1)
                self.assertEqual(about.count('class="lc-whatsapp-float"'), 1)
                self.assertEqual(about.count('class="lc-site-footer__copyright"'), 1)
                self.assertEqual(about.count('id="lc-footer-map-frame"'), 1)
                self.assertEqual(about.count('id="lc-about-map"'), 1)
                self.assertEqual(about.count('data-lc-map-button'), 2)
                self.assertNotIn('assets/about.js', about)
                self.assertNotIn('class="home-contact"', about)
                self.assertNotIn("google.com/maps/embed", about)
                self.assertIn("7:00 a. m. a 7:00 p. m.", about)
                self.assertIn("9:00 a. m. a 6:00 p. m.", about)
                self.assertIn("Agendemos nuestra cita", about)
                self.assertIn("4.6495826%2C-74.08647", about)
                ids = re.findall(r'\bid="([^"]+)"', about)
                self.assertEqual(len(ids), len(set(ids)))
                for section_id in ("conoce-light-color", "privacidad", "visitanos"):
                    self.assertIn(f'id="{section_id}"', about)
                self.assertIn(f'src="{base}assets/home/654729676-5fc380e1-e7af-4f92-b1fd-3f80f4c08387-768x768.webp"', about)
                self.assertEqual(about.count('aria-label="Instagram"'), 2)
                self.assertIn('aria-label="TikTok"', about)
                self.assertIn('aria-label="Pinterest"', about)
                self.assertIn('<h3>Instagram</h3>', about)
                self.assertNotIn('Perfil 1', about)
                self.assertNotIn('Perfil 2', about)
                self.assertNotIn('Una identidad inspirada en el movimiento y el color.', about)
                self.assertNotIn('MOMENTOS Y NOVEDADES', about.upper())
                self.assertNotIn('Te esperamos en Light Color.', about)
                self.assertNotRegex(about, r'<a[^>]+(?:instagram|tiktok|pinterest|facebook)')
                self.assertIn('grid-template-areas: "title ." "location details"', about_css)
                self.assertIn('grid-template-areas: "title" "location" "details"', about_css)
                self.assertIn('color: #8d65bd', about_css)
                self.assertIn('color: #4b326d', about_css)
                self.assertIn('color: #cc334e', about_css)
                self.assertNotIn('.lc-about-page a { color:inherit; }', about_css)
                self.assertIn("id=\"lc-about-map-trigger\"", about)
                self.assertNotIn("google.com/maps/embed", about)
                self.assertIn("frame.src = mapUrl.href", shared_js)
                self.assertIn("button.addEventListener('click'", shared_js)
                self.assertIn("container.replaceChildren(frame)", shared_js)
                self.assertIn("aspect-ratio: 16 / 10", about_css)
                self.assertIn("background: var(--lc-about-ink)", about_css)
                self.assertNotIn("cloudflare", about.lower())
                self.assertNotIn("/privacidad/", about)
                header_pattern = re.compile(r'<header class="lc-site-header".*?</header>', re.S)
                home_header = header_pattern.search(html)
                about_header = header_pattern.search(about)
                self.assertIsNotNone(home_header)
                self.assertIsNotNone(about_header)
                normalize_header = lambda value: re.sub(
                    r'\s+', ' ', re.sub(r' aria-current="page"| is-active', '', value)
                ).replace(' >', '>').strip()
                self.assertEqual(normalize_header(home_header.group()), normalize_header(about_header.group()))
                footer_pattern = re.compile(r'<footer id="site-footer".*?</footer>', re.S)
                home_footer = footer_pattern.search(html)
                about_footer = footer_pattern.search(about)
                self.assertIsNotNone(home_footer)
                self.assertIsNotNone(about_footer)
                self.assertEqual(home_footer.group(), about_footer.group())
                for col in ("brand", "social", "hours", "contact"):
                    self.assertEqual(home_footer.group().count(f'lc-site-footer__{col}'), 1)
                for footer_copy in (home_footer.group(), about_footer.group()):
                    self.assertIn('assets/brand/logo.png', footer_copy)
                    self.assertIn('assets/home/products-art-1254.png', footer_copy)
                    self.assertIn("Lunes a sábado", footer_copy)
                    self.assertIn("Domingos y festivos", footer_copy)
                    self.assertIn("Cl. 57b #50-91, Bogotá", footer_copy)
                    self.assertIn("313 3226726", footer_copy)
                    self.assertEqual(footer_copy.count("© 2026 Light Color"), 1)
                self.assertIn('font-family: "Sagona", Georgia, serif', shared_css)
                self.assertNotIn("lc-site-header", css)
                self.assertNotIn("lc-site-header", about_css)
                self.assertNotIn("lc-site-footer", css)
                self.assertNotIn("lc-site-footer", about_css)
                self.assertIn("align-items: center", about_css)
                self.assertNotIn("privacy-policy-preparation", str(inventory["files"]))
                self.assertEqual(html.count('href="' + base + 'nosotros/#'), 3)
                self.assertIn(f'href="{base}nosotros/#conoce-light-color"', html)
                self.assertIn(f'href="{base}nosotros/#visitanos"', html)
                self.assertIn(f'href="{base}nosotros/#privacidad"', html)
                services = (output / "servicios" / "index.html").read_text(encoding="utf-8")
                services_css = (output / "assets" / "services.css").read_text(encoding="utf-8")
                catalog_js = (output / "assets" / "catalog.js").read_text(encoding="utf-8")
                service_data = json.loads((output / "assets" / "services" / "services.json").read_text(encoding="utf-8"))
                self.assertIn(f'data-catalog-data="{base}assets/services/services.json"', services)
                self.assertIn('aria-current="page">Servicios</a>', services)
                self.assertEqual(services.count('class="lc-whatsapp-float"'), 1)
                self.assertEqual(services.count('id="site-footer"'), 1)
                self.assertEqual(services.count('class="lc-site-footer__copyright"'), 1)
                self.assertEqual(footer_pattern.search(services).group(), home_footer.group())
                header_normalize = lambda value: re.sub(r'\s+', ' ', re.sub(r' aria-current="page"| is-active', '', value)).replace(' >', '>').strip()
                self.assertEqual(header_normalize(header_pattern.search(services).group()), normalize_header(home_header.group()))
                self.assertEqual(len(service_data), 24)
                self.assertEqual({name: sum(item["category"] == name for item in service_data) for name in ("Cabello", "Rostro", "Uñas", "Piel")}, {"Cabello": 8, "Rostro": 7, "Uñas": 6, "Piel": 3})
                self.assertIn("Encuentra opciones de belleza y cuidado personal pensadas para ti.", services)
                self.assertIn('url("../assets/services/portada_servicios.png")', services_css)
                self.assertIn("normalize", catalog_js)
                self.assertIn("replaceChildren", catalog_js)
                self.assertIn("sort.value = 'title-asc'", catalog_js)
                self.assertNotIn("innerHTML", catalog_js)
                self.assertNotIn("location.href", catalog_js)
                self.assertNotIn("R003/", services + services_css + catalog_js)
                self.assertNotIn("wp-content/", services)
                for slug in ("corte-de-cabello", "coloracion-con-tinte", "henna-capilar"):
                    detail = (output / "servicios" / slug / "index.html").read_text(encoding="utf-8")
                    self.assertIn(f'data-service-id="{slug}"', detail)
                    self.assertIn(f'href="{base}servicios/"', detail)
                    self.assertIn(f'href="{base}assets/brand/favicon-32.png"', detail)
                    self.assertIn('aria-current="page">Servicios</a>', detail)
                    self.assertEqual(detail.count('class="lc-whatsapp-float"'), 1)
                    self.assertEqual(detail.count('id="site-footer"'), 1)
                    self.assertEqual(footer_pattern.search(detail).group(), home_footer.group())
                    self.assertEqual(header_normalize(header_pattern.search(detail).group()), normalize_header(home_header.group()))
                    self.assertIn("Consultar por WhatsApp", detail)
                    self.assertNotIn("R003/", detail)
                    self.assertNotIn("wp-content/", detail)
                    self.assertNotIn("{{", detail)
                    self.assertRegex(detail, r"data-gallery-thumb")
                    self.assertIn(f"src=\"{base}assets/services/{slug}/portada_catalogo.png\"", detail)
                corte = (output / "servicios" / "corte-de-cabello" / "index.html").read_text(encoding="utf-8")
                self.assertEqual(corte.count("data-gallery-thumb"), 7)
                self.assertIn("para todas las edades", corte)
                self.assertIn("ArrowRight", catalog_js)
                self.assertIn("dataset.detailStatus", catalog_js)
                self.assertIn("Información en preparación", catalog_js)
                self.assertNotIn("href=\"" + base + "servicios/mechas-iluminaciones-balayage/", services)
                self.assertNotIn("https://", services_css)
                for page in (services, services_css, catalog_js):
                    self.assertNotIn("{{base}}", page)
                for page in (services, *[
                    (output / "servicios" / slug / "index.html").read_text(encoding="utf-8")
                    for slug in ("corte-de-cabello", "coloracion-con-tinte", "henna-capilar")
                ]):
                    for resource in re.findall(r'(?:src|data-image-src|href)="([^"]+)"', page):
                        if resource.startswith(base + "assets/"):
                            self.assertTrue((output / resource[len(base):]).is_file(), resource)
                for css_url in re.findall(r'url\(["\']?([^"\')]+)', services_css):
                    css_asset = (Path("assets/services.css").parent / css_url).as_posix()
                    self.assertTrue((output / css_asset).is_file(), css_url)
                repeated = build("preview-connected", base, Path(temporary) / "repeat", ROOT)
                self.assertEqual(repeated["files"], result["files"])
                first_tree = {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob("*") if path.is_file()}
                repeated_tree = {path.relative_to(Path(temporary) / "repeat").as_posix(): path.read_bytes() for path in (Path(temporary) / "repeat").rglob("*") if path.is_file()}
                self.assertEqual(first_tree, repeated_tree)
                results.append({p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()})
        self.assertEqual(set(results[0]), set(results[1]))

    def test_service_source_and_asset_allowlist_are_exact(self):
        manifest = json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
        entries = validate_manifest_data(manifest)
        registry = validate_service_registry(ROOT / "src", entries)
        self.assertEqual(set(registry), {"corte-de-cabello", "coloracion-con-tinte", "henna-capilar"})
        all_records = json.loads((ROOT / "src" / "catalog-data" / "services.json").read_text(encoding="utf-8"))
        ready = [record for record in all_records if record["detailStatus"] == "ready"]
        pending = [record for record in all_records if record["detailStatus"] == "pending"]
        self.assertEqual((len(all_records), len(ready), len(pending)), (24, 3, 21))
        self.assertTrue(all(record["detailPath"] is None for record in pending))
        for record_id, record in registry.items():
            self.assertEqual(record["detailPath"], f"servicios/{record_id}/")
            self.assertTrue((ROOT / "src" / record["cover"]).is_file())
            self.assertTrue(all((ROOT / "src" / image).is_file() for image in record["gallery"]))

    def test_products_commercial_registry_is_empty_and_demo_fixture_is_preview_only(self):
        manifest = json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
        entries = validate_manifest_data(manifest)
        validate_empty_product_registry(ROOT / "src")
        demo = validate_product_demo_registry(ROOT)
        self.assertEqual(len(demo), 3)
        self.assertEqual({record["group"] for record in demo}, {"Marca de prueba A", "Marca de prueba B", "Otros productos — prueba"})
        self.assertEqual({group: sum(record["group"] == group for record in demo) for group in {record["group"] for record in demo}}, {
            "Marca de prueba A": 1, "Marca de prueba B": 1, "Otros productos — prueba": 1,
        })
        self.assertEqual(json.loads((ROOT / "src" / "catalog-data" / "products.json").read_text(encoding="utf-8")), [])
        self.assertFalse(any("product-demo-" in entry["source"] or entry["output"].startswith("productos/demo-") for entry in entries))

    def test_public_product_page_and_shared_script_do_not_embed_demo_records_or_groups(self):
        page = (ROOT / "src" / "pages" / "products.html").read_text(encoding="utf-8")
        script = (ROOT / "src" / "scripts" / "catalog.js").read_text(encoding="utf-8")
        canonical = (ROOT / "src" / "catalog-data" / "products.json").read_text(encoding="utf-8")
        for content in (page, script, canonical):
            self.assertNotIn("Producto de prueba", content)
            self.assertNotIn("Marca de prueba", content)
            self.assertNotIn("product-demo-", content)
        self.assertEqual(json.loads(canonical), [])

    def test_products_renderer_escapes_demo_text_and_has_accessible_gallery_controls(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "products-demo" / "products-demo.json").read_text(encoding="utf-8"))[0]
        template = (ROOT / "src" / "templates" / "product-detail.html").read_text(encoding="utf-8")
        rendered = render_product_detail(template, fixture, "/light-color-web/")
        self.assertIn('src="/light-color-web/assets/products/product-demo-a.svg"', rendered)
        self.assertEqual(rendered.count("data-gallery-thumb"), 2)
        self.assertIn('aria-pressed="true"', rendered)
        self.assertIn("demostración local", rendered.lower())

    def test_public_manifest_rejects_product_demo_routes(self):
        manifest = json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
        entries = validate_manifest_data(manifest)
        entries = [entry for entry in entries if entry["source"] not in {"assets/home/review-400.jpg", "assets/home/review-300.jpg"}]
        demo_entry = {"source": "pages/products.html", "output": "productos/demo-01/index.html", "kind": "html", "root": "src"}
        with self.assertRaises(BuildError):
            validate_public_entries([*entries, demo_entry])

    def test_product_card_content_stays_in_normal_flow_and_media_has_fixed_crop(self):
        script = (ROOT / "src" / "scripts" / "catalog.js").read_text(encoding="utf-8")
        css = (ROOT / "src" / "styles" / "products.css").read_text(encoding="utf-8")
        self.assertIn("body.append(group, title);", script)
        self.assertIn("body.append(badge);", script)
        self.assertIn("body.append(note);", script)
        self.assertIn("link.append(media, body);", script)
        self.assertIn("results.forEach(function (record) { grid.append(makeCard(record)); });", script)
        self.assertIn("height:190px; min-height:190px; flex:0 0 190px; overflow:hidden", css)
        self.assertIn("width:100%; height:190px; object-fit:cover", css)
        self.assertIn(".lc-products__card-link { display:flex; min-width:0; min-height:320px; flex:1; flex-direction:column", css)
        self.assertIn("@media(max-width:900px)", css)
        self.assertIn("@media(max-width:640px)", css)

    def test_product_catalog_source_contract_covers_search_filters_sort_and_reset(self):
        script = (ROOT / "src" / "scripts" / "catalog.js").read_text(encoding="utf-8")
        product_logic = script[script.index("function validProducts"):script.index("function initServiceCatalog")]
        self.assertIn("normalize(record.name + ' ' + record.group).includes(normalize(search.value))", product_logic)
        self.assertIn("record.group === group", product_logic)
        self.assertIn("sortRecords(records.filter", product_logic)
        self.assertIn("sort.value = 'title-asc'", product_logic)
        self.assertIn("form.addEventListener('reset'", product_logic)
        self.assertIn("results.forEach(function (record) { grid.append(makeCard(record)); });", product_logic)
        self.assertIn("results.length + (results.length === 1 ? ' resultado' : ' resultados')", product_logic)

    def test_service_detail_manifest_record_cannot_escape_approved_routes(self):
        for record, output in (("manicure", "servicios/manicure/index.html"), ("corte-de-cabello", "servicios/otro/index.html")):
            with self.subTest(record=record, output=output), self.assertRaises(BuildError):
                validate_manifest_data({"schema_version": 1, "site": "light-color-web", "entries": [
                    {"source": "templates/service-detail.html", "output": output, "kind": "html", "root": "src", "active": "servicios", "record": record}
                ]})

    def test_service_detail_renderer_escapes_editorial_text(self):
        import copy
        manifest = json.loads((ROOT / "src" / "site-manifest.json").read_text(encoding="utf-8"))
        entries = validate_manifest_data(manifest)
        registry = validate_service_registry(ROOT / "src", entries)
        service = copy.deepcopy(registry["corte-de-cabello"])
        service["name"] = '<img src=x onerror="alert(1)">'
        service["description"] = ["<script>alert(1)</script>"]
        template = (ROOT / "src" / "templates" / "service-detail.html").read_text(encoding="utf-8")
        rendered = render_service_detail(template, service, "/")
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", rendered)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertNotIn('<script>alert(1)</script>', rendered)

    def test_about_reuses_the_exact_social_svg_paths_from_home(self):
        home = (ROOT / "src" / "components" / "footer.html").read_text(encoding="utf-8")
        about = (ROOT / "src" / "pages" / "about.html").read_text(encoding="utf-8")
        pattern = re.compile(r'<svg viewBox="0 0 (?:448|496) 512"[^>]*><path d="([^"]+)')
        home_paths = pattern.findall(home)
        about_paths = pattern.findall(about)

        self.assertEqual(len(home_paths), 3)
        self.assertEqual(len(about_paths), 3)
        self.assertEqual(about_paths[0], home_paths[0])
        self.assertEqual(about_paths[1:], home_paths[1:])

    def test_component_inclusion_rejects_unknown_and_nested_names(self):
        with self.assertRaisesRegex(BuildError, "no declarado"):
            compose_html("<!-- lc:include mystery -->", ["header"], {"header": "<header></header>"}, "inicio", None)
        with self.assertRaisesRegex(BuildError, "circular"):
            _audit_component("header", "<!-- lc:include footer -->")
        with self.assertRaisesRegex(BuildError, "javascript"):
            _audit_component("footer", '<a href="javascript:alert(1)">x</a>')
        with self.assertRaisesRegex(BuildError, "remoto"):
            _audit_component("footer", '<img src="//cdn.invalid/image.svg" alt="x">')
        with self.assertRaisesRegex(BuildError, "circular"):
            _audit_component("header", "<!-- lc:include footer")

    def test_command_line_constructor(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "cli-site"
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools" / "build.py"), "--mode", "test",
                 "--base-path", "/", "--output", str(output)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "build-manifest.json").is_file())

    def test_root_and_prefix_builds_are_allowlisted(self):
        results = []
        for base in ("/", "/light-color-web/"):
            with tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "site"
                result = build("test", base, output, ROOT)
                self.assertEqual(result["files"], 11)
                self.assertEqual(
                    {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()},
                    {
                        "index.html", "nested/page.html", "assets/site.css", "assets/app.js", "assets/pixel.svg",
                        "assets/shared.css", "assets/shared.js", "assets/brand/logo.png",
                        "assets/brand/favicon-32.png", "assets/brand/favicon-192.png", "build-manifest.json",
                    },
                )
                html = (output / "index.html").read_text(encoding="utf-8")
                css = (output / "assets/site.css").read_text(encoding="utf-8")
                js = (output / "assets/app.js").read_text(encoding="utf-8")
                shared_css = (output / "assets/shared.css").read_text(encoding="utf-8")
                shared_js = (output / "assets/shared.js").read_text(encoding="utf-8")
                nested_html = (output / "nested/page.html").read_text(encoding="utf-8")
                self.assertIn(f'href="{base}nested/page.html"', html)
                self.assertIn(f'srcset="{base}assets/pixel.svg 1x, {base}assets/pixel.svg 2x"', html)
                self.assertIn("https://example.invalid/", html)
                self.assertIn(f"url(\"{base}assets/pixel.svg\")", css)
                self.assertIn(f'"{base}assets/site.css"', js)
                self.assertIn(f'href="{base}assets/brand/favicon-32.png"', html)
                self.assertIn(f'src="{base}assets/brand/logo.png"', html)
                self.assertIn(f'href="{base}servicios/"', html)
                self.assertIn('aria-current="page">Productos</a>', html)
                self.assertEqual(html.count('class="lc-whatsapp-float"'), 1)
                self.assertIn("wa.me/573125973539", html)
                self.assertNotIn("joinchat", html.lower())
                self.assertEqual(html.count('id="site-footer"'), 1)
                self.assertNotIn("lc:include", html)
                self.assertIn(".lc-site-footer", shared_css)
                self.assertIn("Escape", shared_js)
                self.assertNotIn("innerHTML", shared_js)
                self.assertIn("lc-site-header--detail", nested_html)
                self.assertIn('aria-current="page">Servicios</a>', nested_html)
                self.assertTrue((output / "assets/brand/favicon-192.png").is_file())
                build_manifest = json.loads((output / "build-manifest.json").read_text(encoding="utf-8"))
                self.assertEqual({component["name"] for component in build_manifest["components"]}, {"header", "footer", "whatsapp", "favicon"})
                results.append((base, {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}))
        self.assertEqual(set(results[0][1]), set(results[1][1]))

    def test_deterministic_double_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            build("test", "/", first, ROOT)
            build("test", "/", second, ROOT)
            snapshot = lambda base: {
                path.relative_to(base).as_posix(): path.read_bytes()
                for path in base.rglob("*") if path.is_file()
            }
            self.assertEqual(snapshot(first), snapshot(second))

    def test_public_build_fails_closed_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "public"
            with self.assertRaisesRegex(BuildError, "revisión editorial"):
                build("public", "/", output, ROOT)
            self.assertFalse(output.exists())

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("untouched", encoding="utf-8")
            with self.assertRaisesRegex(BuildError, "ya existe"):
                build("test", "/", output, ROOT)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "untouched")

    def test_unexpected_file_and_fixture_markers_fail_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            rogue = output / "rogue.txt"
            rogue.write_text("fixture", encoding="utf-8")
            errors = validate_output_tree(output, {})
            self.assertTrue(any("no declarado" in error for error in errors))
            rogue.unlink()
            demo = output / "index.html"
            demo.write_text('data-demo-mode="true"', encoding="utf-8")
            import hashlib
            errors = validate_output_tree(output, {"index.html": hashlib.sha256(demo.read_bytes()).hexdigest()})
            self.assertTrue(any("demostrativo" in error for error in errors))

    def test_symlink_in_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            external = output.parent / (output.name + "-external")
            external.write_text("outside", encoding="utf-8")
            (output / "escape.txt").symlink_to(external)
            errors = validate_output_tree(output, {})
            self.assertTrue(any("simbólico" in error for error in errors))
            external.unlink()


if __name__ == "__main__":
    unittest.main()
