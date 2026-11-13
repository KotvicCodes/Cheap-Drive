"""Optional headless offline interaction checks. Requires requirements-dev.txt."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from week_report import analyze, render
from make_browser_fixture import fixture


def main():
    from playwright.sync_api import sync_playwright
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real-trace',type=Path,help='optional local completed level-4 trace; never uploaded')
    args=parser.parse_args()
    cache=ROOT/'.cache';cache.mkdir(exist_ok=True)
    path=cache/'browser-fixture.html';path.write_text(render(analyze(fixture())))
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        context=browser.new_context(accept_downloads=False)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(path.as_uri())
        result=page.evaluate((ROOT/'tests/browser_checks.js').read_text())
        print(json.dumps(result))
        page.set_viewport_size({'width':390,'height':844})
        page.evaluate("""()=>{for(const tab of ['overview','orders','timeline','source','captures']){document.querySelector('[data-tab="'+tab+'"]').click();if(document.documentElement.scrollWidth>innerWidth+1)throw Error('Mobile page overflow');}}""")
        if args.real_trace:
            real=cache/'real-browser-report.html';real.write_text(render(analyze(args.real_trace.read_bytes())))
            page.goto(real.as_uri())
            script=(ROOT/'tests/real_browser_checks.js').read_text()
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':900})
                print(json.dumps(page.evaluate(script)))
        if errors:
            raise AssertionError('Unexpected browser errors; inspect privately in the local debugger.')
        context.close();browser.close()


if __name__=='__main__':main()
