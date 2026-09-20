// 测试：通过 CDP 连接 Chrome，复用登录态创建飞书 wiki 节点
const { connectDailyChrome, findPage, safeDisconnect } = require('./connect_browser');

(async () => {
  try {
    // 连接日常 Chrome
    const browser = await connectDailyChrome({ ensureRunning: false });
    console.log('[OK] 已连接 Chrome');

    // 找到飞书知识库的标签页
    const page = await findPage(browser, 'feishu.cn/wiki');
    console.log('[OK] 找到飞书标签页:', page.url());

    // 在页面里执行 JavaScript，调用飞书 API 创建节点
    const result = await page.evaluate(async () => {
      // 飞书 wiki 创建节点 API
      const spaceId = '7678261729456852192';
      const parentNodeToken = 'S62XwuAFsieUE7k6Qzzc28rLnDb'; // 03_总论

      const response = await fetch(`/open-apis/wiki/v2/spaces/${spaceId}/nodes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          obj_type: 'docx',
          parent_node_token: parentNodeToken,
          node_type: 'origin',
          title: '01_会计概述'
        })
      });

      const data = await response.json();
      return data;
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
