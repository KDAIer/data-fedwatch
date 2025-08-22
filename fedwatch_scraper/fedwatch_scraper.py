import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import os


"""
fedwatch_scraper.py

用途：自动在 CME FedWatch Tool 页面（Historical → Downloads）下载所有历史概率文件。
说明：脚本使用 Playwright 控制浏览器，自动接受 Cookie、关闭弹窗、进入 Downloads 区块并逐个点击下载卡片。
下载文件会保存到脚本同级的 `downloads/` 文件夹，若存在同名文件会自动在文件名后追加序号。

运行方式（示例）：
  python .\fedwatch_scraper.py

注意：脚本假定页面元素大体稳定；若网站改版，可能需要调整定位器。
"""


async def main():

    # 下载目录（不存在则创建）
    download_dir = "downloads"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    # 是否以无头模式运行（True=不弹出浏览器窗口，False=可见窗口，便于调试）
    HEADLESS = True

    async with async_playwright() as p:
        # 如果在无头模式下导航出现 HTTP2 错误，自动回退为有头模式重试一次
        browser = None
        context = None
        page = None
        navigated = False
        for use_headless in (HEADLESS, False) if HEADLESS else (False,):
            try:
                print(f"启动浏览器（headless={use_headless}）...")
                browser = await p.chromium.launch(headless=use_headless)
                context = await browser.new_context(accept_downloads=True)
                page = await context.new_page()

                print("正在打开 FedWatch 页面...")
                await page.goto("https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html", timeout=90000)
                print("页面已加载。")
                navigated = True
                break
            except Exception as e:
                msg = str(e)
                print(f"页面打开失败: {msg}")
                # 如果是 HTTP2 协议错误且当前尝试为无头模式，则尝试回退到有头模式
                if "ERR_HTTP2_PROTOCOL_ERROR" in msg and use_headless:
                    print("检测到 HTTP2 协议错误，尝试以有头模式重试页面导航...")
                    try:
                        await browser.close()
                    except Exception:
                        pass
                    continue
                # 其他错误直接抛出
                raise

        if not navigated:
            raise Exception("无法打开目标页面（包括回退到有头模式也失败）")

        try:
            # 处理 Cookie 同意按钮（OneTrust）
            try:
                print("正在查找 Cookie 同意按钮...")
                cookie_button = page.locator("#onetrust-accept-btn-handler")
                await cookie_button.wait_for(timeout=15000)
                if await cookie_button.is_visible():
                    await cookie_button.click()
                    print("已接受 Cookie。")
                else:
                    print("Cookie 按钮不可见或已被接受。")
            except PlaywrightTimeoutError:
                print("未找到 Cookie 按钮，继续执行。")

            # 关闭或隐藏可能阻挡点击的通用横幅/弹窗
            try:
                banner_close = page.locator("button[aria-label='Close']").first
                if await banner_close.is_visible():
                    await banner_close.click()
                    print("已关闭可关闭横幅（如存在）。")
            except Exception:
                # 忽略任何关闭失败，继续后续操作
                pass

            # 处理左下角可能出现的 'Visualize the Pace' 弹窗
            try:
                print("尝试查找并关闭 'Visualize the Pace' 弹窗...")
                candidate_selectors = [
                    "button.vv-close-button",
                    "button[aria-label='Close']",
                    "//button[contains(@class,'close') or contains(., '×') or contains(., 'Close')]",
                ]
                closed = False
                for sel in candidate_selectors:
                    btn = page.locator(sel)
                    if await btn.count():
                        if await btn.first.is_visible():
                            await btn.first.click()
                            print(f"通过选择器关闭弹窗：{sel}")
                            closed = True
                            break
                if not closed:
                    print("未检测到可关闭的弹窗（或已隐藏）。")
            except Exception:
                print("未找到 'Visualize the Pace' 弹窗，继续执行。")

            # 在页面中查找并点击侧边栏的 'Downloads' 入口；该入口可能位于 iframe 内
            print("在页面帧中查找 'Downloads' 链接并尝试点击...")
            tool_frame = None

            # 小幅下滑以触发懒加载的 iframe
            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(500)

            # 先在主页面查找
            try:
                main_dl = page.get_by_role("link", name="Downloads", exact=True)
                if await main_dl.count():
                    await main_dl.scroll_into_view_if_needed()
                    await main_dl.click()
                    tool_frame = None
            except Exception:
                pass

            # 若主页面未找到，则遍历所有 iframe 在其中查找
            if tool_frame is None:
                clicked = False
                for f in page.frames:
                    try:
                        loc = f.get_by_role("link", name="Downloads", exact=True)
                        if await loc.count():
                            await loc.scroll_into_view_if_needed()
                            await loc.click()
                            tool_frame = f
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked:
                    raise Exception("未能在任何 frame 中定位到 'Downloads' 链接")

            # 等待 Downloads 页面中的标题出现，表示已进入下载视图
            downloads_header_text = "Federal Reserve Meeting - Probability History Downloads"
            if tool_frame:
                await tool_frame.wait_for_selector(f"text={downloads_header_text}", timeout=40000)
            else:
                await page.wait_for_selector(f"text={downloads_header_text}", timeout=40000)
            print("已进入 Downloads 页面（或对应的嵌入工具视图）。")

            # 再次尝试关闭或隐藏左下角弹窗，避免遮挡下载卡片
            try:
                popup_close = page.locator("text=Visualize the Pace of the Treasury Roll").locator("xpath=ancestor::div[1]//button[contains(@class,'close') or contains(@class,'vv-close') or @aria-label='Close']").first
                if await popup_close.count():
                    if await popup_close.is_visible():
                        await popup_close.click()
                        print("已关闭 Downloads 页面上的 'Visualize the Pace' 弹窗。")
                else:
                    # 找不到关闭按钮时，尝试用 JS 强制隐藏弹窗容器
                    await page.evaluate("""
                        const el = [...document.querySelectorAll('div,section')].find(e => e.innerText && e.innerText.includes('Visualize the Pace of the Treasury Roll'));
                        if (el) {
                          const box = el.closest('div');
                          if (box) {
                            box.style.display = 'none';
                            box.style.visibility = 'hidden';
                          }
                        }
                    """)
                    print("通过 JS 强制隐藏弹窗容器（如存在）。")
            except Exception:
                # 忽略弹窗关闭失败，继续后续扫描
                pass

            # 在下载页内扫描所有链接，识别并点击下载卡片
            search_scope = tool_frame if tool_frame else page
            print("收集下载卡片...")
            # 等待至少有一个 a 元素被附加到 DOM（不强制可见），避免因首个元素不可见导致超时
            await search_scope.wait_for_selector("a", state="attached", timeout=40000)
            all_links = search_scope.locator("a")
            total = await all_links.count()
            print(f"扫描 {total} 个链接以查找下载卡片...")

            # 候选卡片：文本包含中文的“月”且带有年份，或包含单词 upcoming
            candidates = []
            years = [str(y) for y in range(2020, 2032)]
            for i in range(total):
                a = all_links.nth(i)
                try:
                    txt = (await a.inner_text()).strip()
                except Exception:
                    continue
                norm = " ".join(txt.split())
                if not norm:
                    continue
                # 含“月”且包含年份，或文本包含“upcoming”
                if ("月" in norm and any(y in norm for y in years)) or ("upcoming" in norm.lower()):
                    candidates.append(i)

            print(f"找到 {len(candidates)} 个可下载卡片。")

            # 依次点击触发下载并保存
            for idx, i in enumerate(candidates, start=1):
                link = all_links.nth(i)
                async with page.expect_download(timeout=60000) as download_info:
                    await link.scroll_into_view_if_needed()
                    # 使用 force=True 以确保能点击被覆盖或不可交互的元素（已尝试隐藏遮挡弹窗）
                    await link.click(timeout=30000, force=True)

                download = await download_info.value

                # 目标文件路径（使用建议文件名）
                target_path = os.path.join(download_dir, download.suggested_filename)
                # 若目标文件已存在，先删除以实现覆盖保存
                try:
                    if os.path.exists(target_path):
                        os.remove(target_path)
                        print(f"已删除已存在文件以覆盖：{target_path}")
                except Exception as ex:
                    print(f"尝试删除已存在文件失败，将继续保存（可能覆盖失败）：{ex}")

                await download.save_as(target_path)
                print(f"已保存并覆盖（如存在） [{idx}/{len(candidates)}] 到 {target_path}")
                await page.wait_for_timeout(500)

        except Exception as e:
            print(f"发生错误: {e}")
            await page.screenshot(path="error_screenshot.png")
            print("已保存错误截图：error_screenshot.png")
        finally:
            print("正在关闭浏览器...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
