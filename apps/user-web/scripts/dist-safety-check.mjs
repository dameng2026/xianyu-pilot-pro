import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distRoot = path.join(projectRoot, 'dist')
// 与 vite.config.js 的 pure_funcs 对齐：仅检查 log/info/debug/trace/dir/table 等纯诊断输出。
// 保留 console.error / console.warn 用于线上排障（vite.config.js 未将其列入 pure_funcs）。
const consoleCallPattern = /\bconsole\s*(?:\.\s*(?:log|info|debug|trace|dir|table)|\[\s*['"](?:log|info|debug|trace|dir|table)['"]\s*\])\s*\(/
const debuggerStatementPattern = /(?:^|[;{}])\s*debugger\s*(?:;|(?=\}))/

assert.match('console.log("secret")', consoleCallPattern)
assert.match('console.info("secret")', consoleCallPattern)
assert.match('console.debug("secret")', consoleCallPattern)
assert.match('console.trace("secret")', consoleCallPattern)
assert.doesNotMatch('console.error("keep for prod triage")', consoleCallPattern)
assert.doesNotMatch('console.warn("keep for prod triage")', consoleCallPattern)
assert.doesNotMatch('console.error, continueWork()', consoleCallPattern)
assert.match(';debugger;', debuggerStatementPattern)
assert.doesNotMatch('["class", "debugger", "async"]', debuggerStatementPattern)

function filesUnder(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? filesUnder(target) : [target]
  })
}

assert.ok(fs.existsSync(distRoot), 'production build output is missing')
const files = filesUnder(distRoot)
assert.equal(files.some(file => file.endsWith('.map')), false, 'source maps must not ship')

for (const file of files.filter(candidate => candidate.endsWith('.js'))) {
  const source = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(source, consoleCallPattern, `${path.basename(file)} retains console calls`)
  assert.doesNotMatch(source, debuggerStatementPattern, `${path.basename(file)} retains debugger statements`)
}

console.log('dist-safety-check: ok')
