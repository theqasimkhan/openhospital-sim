import asyncio
import os
from playwright.async_api import async_playwright

async def take_screenshots():
    out_dir = "docs/screenshots"
    os.makedirs(out_dir, exist_ok=True)
    
    pages = [
        ("/forecasting", "forecasting.png")
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        for route, filename in pages:
            url = f"http://localhost:3001{route}"
            print(f"Navigating to {url}...")
            try:
                await page.goto(url)
                # Wait longer for the forecasting charts to animate/render
                await page.wait_for_timeout(6000)
                path = os.path.join(out_dir, filename)
                await page.screenshot(path=path)
                print(f"Saved {path}")
            except Exception as e:
                print(f"Failed {url}: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshots())
