#!/usr/bin/env node
/**
 * refresh_auth_token.js — 从用户已登录的日常 Chrome 抓取最新 authentication token
 *
 * 原理：连接到用户正在使用的 Chrome，找到高顿页面，监听网络请求，
 *       刷新页面触发带 authentication 头的 API 请求，捕获后保存到 auth 目录。
 *
 * 用法：node scripts/cdp/refresh_auth_token.js [--profile cpa-accounting-2026]
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { connectDailyChrome, listPages, safeDisconnect, newBackgroundPage, captureFrontmost, restoreFrontmost } = require('./connect_browser');

const AUTH_DIR = path.join(__dirname, '..', '..', 'data', '_workspace', '_account', 'auth');

// 模块加载即记录前台 App（main 内连接触发的授权弹窗会把 Chrome 置前，退出时归还）
const __front = captureFrontmost();

async function main() {
  console.log('[1] 连接日常 Chrome...');
  const browser = await connectDailyChrome({ timeoutMs: 30000, retries: 3 });
  console.log('    Chrome 已连接');

  // 列出所有页面，找到高顿页面
  const pages = await listPages(browser);
  console.log('[2] 当前标签页：');
  pages.forEach((p, i) => console.log(`    [${i}] ${p.title || '(无标题)'} -> ${p.url}`));

  // 找高顿页面
  const allPages = await browser.pages();
  let gaodunPage = allPages.find((p) => {
    const u = p.url();
    return /gaodun\.com/.test(u) && !/chrome:\/\//.test(u);
  });

  if (!gaodunPage) {
    console.log('[3] 未找到高顿页面，新建标签页打开 v.gaodun.com/space/...');
    gaodunPage = await newBackgroundPage(browser);
    await gaodunPage.goto('https://v.gaodun.com/space/', { waitUntil: 'networkidle2', timeout: 30000 });
  } else {
    console.log(`[3] 找到高顿页面: ${gaodunPage.url()}`);
  }

  // 监听网络请求，捕获 authentication 头
  let capturedToken = null;
  let capturedUrl = null;
  const captured = [];

  const onRequest = (request) => {
    const url = request.url();
    if (!/apigateway\.gaodun\.com/.test(url)) return;
    const headers = request.headers();
    const auth = headers['authentication'] || headers['Authentication'];
    if (auth && auth.startsWith('Basic ')) {
      capturedToken = auth;
      capturedUrl = url;
      captured.push({ url, method: request.method(), auth: auth.substring(0, 30) + '...' });
    }
  };

  gaodunPage.on('request', onRequest);

  // 也监听所有其他页面的请求（高顿可能在iframe或其他tab中发请求）
  for (const p of allPages) {
    if (p !== gaodunPage) {
      p.on('request', onRequest);
    }
  }

  console.log('[4] 刷新高顿页面，触发 API 请求...');
  try {
    await gaodunPage.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  } catch (e) {
    console.log(`    刷新等待超时（正常，继续监听）: ${e.message.substring(0, 80)}`);
  }

  // 等待捕获 token（最多15秒）
  console.log('[5] 等待捕获 authentication token...');
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (capturedToken) break;
  }

  // 如果刷新没捕获到，尝试导航到用户空间页面
  if (!capturedToken) {
    console.log('[6] 刷新未捕获，尝试导航到用户空间...');
    try {
      await gaodunPage.goto('https://v.gaodun.com/space/', { waitUntil: 'networkidle2', timeout: 30000 });
    } catch (e) {
      console.log(`    导航等待超时: ${e.message.substring(0, 80)}`);
    }
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (capturedToken) break;
    }
  }

  if (!capturedToken) {
    console.error('❌ 未能捕获 authentication token');
    console.error('   请确认 Chrome 中已登录高顿账号，且页面能正常加载');
    await safeDisconnect(browser);
    restoreFrontmost(__front);
    process.exit(1);
  }

  console.log(`[7] 捕获成功！`);
  console.log(`    来源URL: ${capturedUrl}`);
  console.log(`    Token前30位: ${capturedToken.substring(0, 30)}...`);
  console.log(`    共捕获 ${captured.length} 条带 authentication 的请求`);

  // 解码JWT查看过期时间
  try {
    const jwt = capturedToken.replace('Basic ', '');
    const payload = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64').toString());
    const expDate = new Date(payload.exp * 1000);
    const iatDate = new Date(payload.iat * 1000);
    console.log(`    JWT签发: ${iatDate.toLocaleString('zh-CN')}`);
    console.log(`    JWT过期: ${expDate.toLocaleString('zh-CN')}`);
  } catch (e) {
    console.log(`    JWT解码失败: ${e.message}`);
  }

  // 保存到 auth 目录（jsonl格式，与findJwt兼容）
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  const ts = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
  const outFile = path.join(AUTH_DIR, `refresh_${ts}.jsonl`);
  const record = {
    kind: 'request',
    method: 'GET',
    url: capturedUrl,
    headers: {
      authentication: capturedToken,
      'content-type': 'application/json;charset=UTF-8',
      accept: 'application/json, text/plain, */*',
      origin: 'https://glivepro.gaodun.com',
    },
    postData: null,
  };
  fs.writeFileSync(outFile, JSON.stringify(record) + '\n', 'utf8');
  console.log(`[8] Token已保存: ${outFile}`);

  // 验证findJwt能读到
  const { findJwt } = require('./gaodun_paper_core');
  const readBack = findJwt();
  if (readBack === capturedToken) {
    console.log('[9] ✅ findJwt 回读验证通过，做题脚本可以使用新token');
  } else {
    console.log('[9] ⚠️ findJwt 回读的token与刚捕获的不一致，可能有更新的文件');
    console.log(`    回读前30位: ${readBack.substring(0, 30)}...`);
  }

  await safeDisconnect(browser);
  restoreFrontmost(__front); // 授权弹窗若把 Chrome 置前，归还运行前的前台 App
  console.log('\n✅ Token刷新完成，可以重启做题任务');
}

main().catch((e) => {
  restoreFrontmost(__front);
  console.error('❌ 刷新token失败:', e.message);
  console.error(e.stack);
  process.exit(1);
});
