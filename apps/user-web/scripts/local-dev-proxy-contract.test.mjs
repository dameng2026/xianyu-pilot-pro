import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const userWebRoot = path.resolve(scriptDir, '..')
const projectRoot = path.resolve(userWebRoot, '..', '..')
const viteConfig = fs.readFileSync(path.join(userWebRoot, 'vite.config.js'), 'utf8')
const devLauncher = fs.readFileSync(path.join(projectRoot, 'dev-start.ps1'), 'utf8')

const portMatch = viteConfig.match(/server:\s*\{[\s\S]*?\bport:\s*(\d+)/)
assert.equal(Number(portMatch?.[1]), 5174, 'local user-web must use the port advertised by dev-start.ps1')
assert.match(
  viteConfig,
  /['"]\/api['"]\s*:\s*\{[\s\S]*?target:\s*['"]http:\/\/localhost:18080['"]/
)
assert.match(
  viteConfig,
  /['"]\/uploads['"]\s*:\s*\{[\s\S]*?target:\s*['"]http:\/\/localhost:18080['"]/
)
assert.doesNotMatch(viteConfig, /['"]\/uploads['"]\s*:\s*\{[\s\S]*?target:\s*['"]http:\/\/localhost:12401['"]/)
assert.match(devLauncher, /user-web \[5174\]/)

console.log('local-dev-proxy-contract: ok')
