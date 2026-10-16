// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Alma Creativa
// Captura headless de una página de LibreNMS, logueado (verificación visual de dashboards/mapas).
// URL: LNMS_URL (default http://localhost:8000)
// Uso: PWCORE=<ruta a playwright-core> LU=<usuario> LP=<password> node shot.js <path> <out.png> [ancho] [alto]
//   PWCORE: p.ej. ~/.npm/_npx/<hash>/node_modules/playwright-core (cualquier instalación de Playwright)
const pw = require(process.env.PWCORE);
(async () => {
  const b = await pw.chromium.launch();
  const p = await b.newPage({ viewport: { width: +(process.argv[4] || 1440), height: +(process.argv[5] || 900) } });
  const base = process.env.LNMS_URL || 'http://localhost:8000';
  await p.goto(base + '/login');
  await p.fill('input[name=username]', process.env.LU);
  await p.fill('input[name=password]', process.env.LP);
  await Promise.all([p.waitForNavigation(), p.click('button[type=submit]')]);
  await p.goto(base + process.argv[2], { waitUntil: 'networkidle' });
  await p.waitForTimeout(4000);
  await p.screenshot({ path: process.argv[3], fullPage: true });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
