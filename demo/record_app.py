import time
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    ctx = b.new_context(viewport={"width":1600,"height":900}, record_video_dir="vid_app", record_video_size={"width":1280,"height":720})
    pg = ctx.new_page(); pg.goto("http://localhost:8501"); pg.wait_for_selector("text=Investigate", timeout=60000); time.sleep(3)
    ta = pg.locator("textarea").first; ta.fill(""); ta.type("Why did revenue drop in September 2026?", delay=60); time.sleep(1)
    t0=time.time(); open("marks.txt","w").write(f"click {time.time()}\n")
    pg.get_by_role("button", name="Investigate").click()
    pg.wait_for_selector("text=Ranked explanation", timeout=1800000)
    open("marks.txt","a").write(f"done {time.time()}\n"); time.sleep(2)
    main = pg.locator("section.main, [data-testid='stMain']").first
    for i in range(40):
        pg.mouse.move(640,400); pg.mouse.wheel(0,250); time.sleep(0.6)
    time.sleep(2); open("marks.txt","a").write(f"end {time.time()}\n")
    ctx.close(); b.close()
