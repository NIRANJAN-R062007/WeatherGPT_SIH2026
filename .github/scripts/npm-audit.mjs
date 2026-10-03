// `npm audit` for the Security workflow: every high or critical advisory
// fails the job, except the ones accepted below, each by GHSA id with the
// reason it can't be fixed yet and doesn't reach users. Run from web/:
//   node ../.github/scripts/npm-audit.mjs
// npm audit has no ignore list of its own, hence this wrapper.
import { spawnSync } from 'node:child_process';

const ACCEPTED = {
  // braces <= 3.0.3: deeply nested brace patterns can exhaust the stack.
  // No patched braces exists (2026-10-03). It only comes in through
  // tailwindcss 3 (chokidar, micromatch), a devDependency that runs at build
  // time on our own `content` globs; nothing of it is in the shipped bundle,
  // and no outside input reaches it. Drop this entry once braces ships a fix
  // or web/ moves to Tailwind 4 (which doesn't use braces).
  'GHSA-vfj7-8cjw-p6xm': 'braces stack exhaustion, build-time only via tailwindcss 3',
};

const FAIL_AT = new Set(['high', 'critical']);

const run = spawnSync('npm', ['audit', '--json'], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
let report;
try {
  report = JSON.parse(run.stdout);
} catch {
  console.error(`npm audit didn't return JSON (exit ${run.status}):\n${run.stderr || run.stdout}`);
  process.exit(1);
}
if (report.error) {
  console.error(`npm audit failed: ${JSON.stringify(report.error)}`);
  process.exit(1);
}

// Advisories are the object entries in each package's `via`; string entries
// point at another package and are covered by that package's advisories.
const advisories = new Map();
for (const [name, vuln] of Object.entries(report.vulnerabilities ?? {})) {
  for (const via of vuln.via ?? []) {
    if (typeof via !== 'object' || !FAIL_AT.has(via.severity)) continue;
    const id = (via.url ?? '').split('/').pop() || String(via.source);
    const entry = advisories.get(id) ?? { title: via.title, severity: via.severity, packages: new Set() };
    entry.packages.add(name);
    advisories.set(id, entry);
  }
}

let failing = 0;
for (const [id, { title, severity, packages }] of advisories) {
  const where = [...packages].join(', ');
  if (id in ACCEPTED) {
    console.log(`accepted  ${severity}  ${id}  ${title} (${where}): ${ACCEPTED[id]}`);
  } else {
    console.log(`FAILING   ${severity}  ${id}  ${title} (${where})`);
    failing++;
  }
}
for (const id of Object.keys(ACCEPTED)) {
  if (!advisories.has(id)) console.log(`note: ${id} is accepted but no longer reported; remove it from ACCEPTED.`);
}
console.log(failing ? `${failing} high/critical advisor${failing === 1 ? 'y' : 'ies'} not accepted.` : 'No unaccepted high/critical advisories.');
process.exit(failing ? 1 : 0);
