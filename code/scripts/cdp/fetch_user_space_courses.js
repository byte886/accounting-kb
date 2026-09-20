#!/usr/bin/env node
/**
 * fetch_user_space_courses.js — 拉取高顿"用户空间/我的课程"全课程清单（为后续课程备料）
 *
 * 背景：用户空间页面（登录后可见"用户空间/我的课程"）会请求
 *   GET https://apigateway.gaodun.com/ep-course/api/v2/front/space/vcourse/pc
 * 返回当前账号在各 project（如 CPA=8）下购买/开通的全部课程。本脚本复用题库采集同款
 * JWT 直连方式（findJwt + https），不操控浏览器页面，可重复执行。
 *
 * ID 体系（切勿混用）：
 *   - vcourseId / id            学员购课实例（虚拟课程）ID，听课/学习进度用它
 *   - saasCourseId / relationCourse  SaaS 课程 ID，syllabus/考点/讲次等课程内容接口用它
 *   - subjectId                 科目 ID（CPA：会计37/审计36/财管45/经济法39/税法38/战略46）
 *   - projectId                 考试项目 ID（CPA=8）
 *
 * 用法：
 *   node scripts/cdp/fetch_user_space_courses.js            # 拉取并写台账
 *   node scripts/cdp/fetch_user_space_courses.js --print    # 额外在终端打印清单表格
 *
 * 输出（账号/跨课级，统一在工作区，不入 Git、不传网盘）：
 *   data/_workspace/_account/user-space/account_courses.json          精简结构化台账（覆盖式，带 fetchedAt）
 *   data/_workspace/_account/user-space/user_space_vcourse_<ts>.json  当次原始响应（保真留痕）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');
const { findJwt, makeHeaders } = require('./gaodun_paper_core');
const { accountDir } = require('./load_profile');

const PROJECT_ROOT = path.resolve(__dirname, '..', '..');
const USER_SPACE_DIR = accountDir('user-space');
const LEDGER = path.join(USER_SPACE_DIR, 'account_courses.json');
const API = 'https://apigateway.gaodun.com/ep-course/api/v2/front/space/vcourse/pc';

const wantPrint = process.argv.includes('--print');

function httpGetJson(url, headers) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers, timeout: 20000 }, (res) => {
      let body = '';
      res.on('data', (d) => { body += d; });
      res.on('end', () => {
        try { resolve({ status: res.statusCode, json: JSON.parse(body), raw: body }); }
        catch (e) { reject(new Error(`响应非JSON(status=${res.statusCode}): ${body.slice(0, 200)}`)); }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
  });
}

/** 从学习入口 URL 判别学习平台：正课在 glivepro，名师专业课在 epiphany（智能学习平台，前端/接口不同） */
function platformOf(url) {
  if (!url) return 'unknown';
  if (url.includes('glivepro')) return 'glivepro';
  if (url.includes('epiphany')) return 'epiphany';
  return 'other';
}

/** 从一门课原始对象提取稳定字段（去掉 lives/courseNotice 等易变大块） */
function simplify(c) {
  return {
    name: c.name,
    vcourseId: c.vcourseId ?? c.id,
    saasCourseId: c.saasCourseId ?? c.relationCourse,
    projectId: c.projectId,
    projectName: c.projectName,
    subjectId: c.subjectId,
    subjectName: c.subjectName,
    vcourseType: c.vcourseType,
    saasCourseType: c.saasCourseType,       // 实测：16=考季正课(glivepro)，13=名师专业课(epiphany)
    wareStatus: c.wareStatus,               // 课件状态，语义≠"是否开课/有无内容"，勿据此判断可否采集
    learnStatus: c.learnStatus,             // 学习状态以此为准：实测 0=待学习 2=已学习 3=已完结
    learnStatusDesc: c.learnStatusDesc,
    leftDays: c.leftDays,
    courseStartTime: c.courseStartTime,
    courseExpireTime: c.courseExpireTime,
    lastLeaningTime: c.lastLeaningTime,
    currentStudyUrl: c.currentStudyUrl,
    platform: platformOf(c.currentStudyUrl),
    isAuditionCourse: c.isAuditionCourse,
  };
}

async function main() {
  const jwt = findJwt();
  // ep-course 与听课端同源上下文；若未来网关收紧来源校验，可在此调整 origin/referer
  const headers = makeHeaders(jwt, {
    origin: 'https://glivepro.gaodun.com',
    referer: 'https://glivepro.gaodun.com/',
  });

  const { status, json, raw } = await httpGetJson(API, headers);
  if (status !== 200) throw new Error(`HTTP ${status}`);
  if (json.status !== 0) throw new Error(`业务失败 status=${json.status} message=${json.message}`);

  const result = json.result || {};
  const courseList = result.courseList || {};
  const projects = result.projectList || [];

  const byProject = {};
  let total = 0;
  for (const [pid, courses] of Object.entries(courseList)) {
    byProject[pid] = (courses || []).map(simplify);
    total += byProject[pid].length;
  }

  const ledger = {
    fetchedAt: new Date().toISOString(),
    sourceApi: API,
    note: 'vcourseId=购课实例(听课用); saasCourseId=SaaS课程(内容接口用); platform: glivepro=考季正课/epiphany=名师专业课(不同学习平台,接口不通用); learnStatus: 0待学习/2已学习/3已完结(以此为准); wareStatus语义≠是否开课',
    projects,
    totalCourses: total,
    courseListByProject: byProject,
  };

  fs.mkdirSync(path.dirname(LEDGER), { recursive: true });
  fs.writeFileSync(LEDGER, JSON.stringify(ledger, null, 2), 'utf8');

  const ts = Date.now();
  fs.mkdirSync(USER_SPACE_DIR, { recursive: true });
  const rawPath = path.join(USER_SPACE_DIR, `user_space_vcourse_${ts}.json`);
  fs.writeFileSync(rawPath, raw, 'utf8');

  console.log(`[OK] 共 ${total} 门课，项目: ${projects.map((p) => `${p.name}(${p.id})`).join(', ') || '(无)'}`);
  console.log(`台账: ${path.relative(PROJECT_ROOT, LEDGER)}`);
  console.log(`原始: ${path.relative(PROJECT_ROOT, rawPath)}`);

  if (wantPrint) {
    for (const [pid, courses] of Object.entries(byProject)) {
      console.log(`\n== project ${pid} ==`);
      courses.forEach((c, i) => {
        console.log(`  ${i + 1}. ${c.name}`);
        console.log(`     vcourseId=${c.vcourseId} saasCourseId=${c.saasCourseId} [${c.platform}] ` +
          `subject=${c.subjectName}(${c.subjectId}) ${c.learnStatusDesc} 剩${c.leftDays}天`);
      });
    }
  }
}

main().catch((e) => {
  console.error('[FAIL]', e.message);
  console.error('提示：若为鉴权失败(401/登录态过期)，需先用 CDP 在登录态下抓一次带 authentication 的请求刷新 jsonl。');
  process.exit(1);
});
