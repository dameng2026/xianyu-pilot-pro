import assert from 'node:assert/strict'
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const distRoot = path.join(projectRoot, 'dist')

function runBuild() {
  if (process.env.npm_execpath) {
    execFileSync(process.execPath, [process.env.npm_execpath, 'run', 'build'], {
      cwd: projectRoot,
      stdio: 'inherit'
    })
    return
  }

  if (process.platform === 'win32') {
    // Windows cannot execute .cmd launchers directly through CreateProcess.
    // Invoke the fixed command through cmd.exe explicitly instead of enabling
    // child_process `shell`, which is deprecated for argument-bearing calls.
    execFileSync(process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe', ['/d', '/s', '/c', 'npm run build'], {
      cwd: projectRoot,
      stdio: 'inherit'
    })
    return
  }

  execFileSync('npm', ['run', 'build'], {
    cwd: projectRoot,
    stdio: 'inherit'
  })
}

function filesUnder(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? filesUnder(target) : [target]
  })
}

function buildDigest() {
  runBuild()
  const manifest = filesUnder(distRoot)
    .sort((left, right) => left.localeCompare(right))
    .map((file) => {
      const relative = path.relative(distRoot, file).split(path.sep).join('/')
      const digest = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
      return `${relative} ${digest}`
    })
    .join('\n')
  return crypto.createHash('sha256').update(manifest).digest('hex')
}

const first = buildDigest()
const second = buildDigest()
assert.equal(second, first, 'identical source and build metadata must produce byte-identical assets')
console.log(`reproducible-build: ok (${first})`)
