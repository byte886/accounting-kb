// 测试：在飞书页面里调用简单的 API
const { connectDailyChrome, findPage, safeDisconnect } = require('./connect_browser');

(async () => {
  try {
    // 连接日常 Chrome
    const browser = await connectDailyChrome({ ensureRunning: false });
    console.log('[OK] 已连接 Chrome');

    // 找到飞书知识库的标签页
    const page = await findPage(browser, 'feishu.cn/wiki');
    console.log('[OK] 找到飞书标签页:', page.url());

    // 在页面里执行 JavaScript，先测试一个简单的 API
    const result = await page.evaluate(async () => {
      try {
        // 先测试获取当前用户信息
        const response = await fetch('/open-apis/authen/v1/user_info', {
          method: 'GET',
          credentials: 'include'
        });

        const data = await response.json();
        return { success: true, data };
      } catch (err) {
        return { success: false, error: err.message };
      }
    });

    console.log('[结果]', JSON.stringify(result, null, 2));

    // 断开连接
    await safeDisconnect(browser);
    console.log('[OK] 已断开连接');

  } catch (err) {
    console.error('[错误]', err);
    process.exit(1);
  }
})();
