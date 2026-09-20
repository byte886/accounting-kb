#!/usr/bin/env node
/**
 * batch_ep3_papers.js — 批量做ep3平台名师专业课的试卷
 * 
 * 用法：
 *   node scripts/cdp/batch_ep3_papers.js --profile ep3-audit-2026
 *   node scripts/cdp/batch_ep3_papers.js --profile ep3-finance-2026
 */
'use strict';
const fs = require('fs');
const path = require('path');
const core = require('./gaodun_paper_core');
const { loadProfile, workspaceDirFor, argvProfileKey } = require('./load_profile');

const ROOT = path.resolve(__dirname, '..', '..');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 拟人化随机停顿：防风控，避免机械的固定节奏
const randInt = (min, max) => Math.floor(min + Math.random() * (max - min + 1));
const randSleep = (minSec, maxSec) => sleep(randInt(minSec, maxSec) * 1000);
// 节奏窗口：0:00-6:00 夜间风控宽松→快节奏；其余时段白天→拟人慢节奏
// （夜间窗口起止可按需调整 NIGHT_START_HOUR / NIGHT_END_HOUR）
const NIGHT_START_HOUR = 0;
const NIGHT_END_HOUR = 6;
function isNightMode() {
  const h = new Date().getHours();
  return h >= NIGHT_START_HOUR && h < NIGHT_END_HOUR;
}

async function main() {
  const profile = loadProfile(argvProfileKey());
  const manifestDir = workspaceDirFor(profile.key, 'manifest');
  const logsDir = workspaceDirFor(profile.key, 'logs');
  fs.mkdirSync(logsDir, { recursive: true });
  
  const invPath = path.join(manifestDir, 'papers_inventory.json');
  const auditPath = path.join(manifestDir, 'papers_audit.json');
  
  if (!fs.existsSync(invPath)) {
    console.error(`错误: ${invPath} 不存在`);
    process.exit(1);
  }
  
  const inventory = JSON.parse(fs.readFileSync(invPath, 'utf8'));
  let audit = JSON.parse(fs.readFileSync(auditPath, 'utf8'));
  
  console.log(`=== 批量做ep3平台试卷 ===`);
  console.log(`profile: ${profile.key}`);
  console.log(`总试卷数: ${inventory.length}`);
  console.log(`待做试卷数: ${audit.length}`);
  console.log(`开始时间: ${new Date().toISOString()}`);
  console.log(`当前节奏: ${isNightMode() ? '夜间快节奏(0-6点)' : '白天拟人慢节奏(6-24点)'}`);

  let success = 0;
  let failed = 0;
  let skipped = 0;
  let nextRestAt = randInt(8, 12); // 白天模式下一次长休息出现在第几张

  for (let i = 0; i < audit.length; i++) {
    const paper = audit[i];
    console.log(`\n[${i + 1}/${audit.length}] 做试卷: ${paper.paperId} - ${paper.title}`);
    
    try {
      const result = await core.doPaperViaApi({
        target: {
          paperId: paper.paperId,
          title: paper.title,
          csItemId: paper.csItemId,
          resourceId: paper.resourceId,
        },
        jwt: core.findJwt(),
        log: (...a) => console.log('  ', ...a),
      });
      
      if (result.submitted) {
        console.log(`  ✅ 提交成功，得分: ${result.userScore}/${result.totalScore}`);
        if (result.fullScore) {
          console.log(`  ✅ 满分`);
        } else if (result.platformDone) {
          console.log(`  ✅ 平台最优`);
        } else {
          console.log(`  ⚠️  未达平台最优`);
        }
        success++;
        
        // 从audit中移除
        audit = audit.filter(p => p.paperId !== paper.paperId);
        fs.writeFileSync(auditPath, JSON.stringify(audit, null, 2));
      } else {
        console.log(`  ❌ 提交失败`);
        if (result.error) {
          console.log(`  错误: ${result.error}`);
        }
        failed++;
      }
    } catch (e) {
      console.log(`  ❌ 异常: ${e.message}`);
      failed++;
    }
    
    // 每10张试卷保存一次进度
    if ((i + 1) % 10 === 0) {
      console.log(`\n=== 进度: ${i + 1}/${audit.length}，成功: ${success}，失败: ${failed} ===`);
    }

    // 拟人化节奏：最后一张不停；其余按当前时段决定停顿
    if (i < audit.length - 1) {
      if (isNightMode()) {
        // 夜间 0:00-6:00：快节奏，卷间 1~3s，不长休息
        await randSleep(1, 3);
      } else {
        // 白天：每隔 8~12 张安排一次 40~90s 的"起身休息"，其余卷间 6~15s
        if (i + 1 >= nextRestAt) {
          const rest = randInt(40, 90);
          console.log(`  ☕ 白天拟人长休息 ${rest}s（防风控）...`);
          await sleep(rest * 1000);
          nextRestAt = i + 1 + randInt(8, 12);
        } else {
          await randSleep(6, 15);
        }
      }
    }
  }
  
  console.log(`\n=== 批量做题完成 ===`);
  console.log(`成功: ${success}`);
  console.log(`失败: ${failed}`);
  console.log(`跳过: ${skipped}`);
  console.log(`结束时间: ${new Date().toISOString()}`);
  
  // 保存最终的audit
  fs.writeFileSync(auditPath, JSON.stringify(audit, null, 2));
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
