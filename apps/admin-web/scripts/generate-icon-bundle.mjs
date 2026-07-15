import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = path.resolve(projectRoot, '..', '..')
const outputFile = path.join(projectRoot, 'src', 'assets', 'generated', 'iconify-bundle.json')
const sourceRoots = [
  path.join(projectRoot, 'src'),
  path.join(repositoryRoot, 'apps', 'core-api', 'src', 'main', 'java')
]
const packages = {
  fluent: '@iconify-json/fluent',
  iconamoon: '@iconify-json/iconamoon',
  'icon-park-outline': '@iconify-json/icon-park-outline',
  'line-md': '@iconify-json/line-md',
  ri: '@iconify-json/ri',
  solar: '@iconify-json/solar',
  'svg-spinners': '@iconify-json/svg-spinners',
  'system-uicons': '@iconify-json/system-uicons',
  vaadin: '@iconify-json/vaadin'
}
const sourceExtensions = new Set(['.java', '.js', '.json', '.ts', '.tsx', '.vue'])
const iconPattern = new RegExp(`\\b(${Object.keys(packages).map(escapeRegex).join('|')}):([a-z0-9][a-z0-9-]*)\\b`, 'gi')

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function filesUnder(directory) {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name)
    if (entry.isDirectory()) return filesUnder(target)
    return sourceExtensions.has(path.extname(entry.name).toLowerCase()) ? [target] : []
  })
}

const requested = new Map(Object.keys(packages).map(prefix => [prefix, new Set()]))
for (const file of sourceRoots.flatMap(filesUnder)) {
  const content = fs.readFileSync(file, 'utf8')
  for (const match of content.matchAll(iconPattern)) {
    requested.get(match[1].toLowerCase())?.add(match[2].toLowerCase())
  }
}

const collections = []
const missing = []
for (const [prefix, packageName] of Object.entries(packages)) {
  const source = JSON.parse(fs.readFileSync(require.resolve(`${packageName}/icons.json`), 'utf8'))
  const icons = {}
  const aliases = {}

  function include(name) {
    if (source.icons?.[name]) {
      icons[name] = source.icons[name]
      return
    }
    const alias = source.aliases?.[name]
    if (alias) {
      aliases[name] = alias
      include(alias.parent)
      return
    }
    missing.push(`${prefix}:${name}`)
  }

  for (const name of [...requested.get(prefix)].sort()) include(name)
  collections.push({
    prefix,
    ...(source.width ? { width: source.width } : {}),
    ...(source.height ? { height: source.height } : {}),
    icons: Object.fromEntries(Object.entries(icons).sort(([left], [right]) => left.localeCompare(right))),
    ...(Object.keys(aliases).length
      ? { aliases: Object.fromEntries(Object.entries(aliases).sort(([left], [right]) => left.localeCompare(right))) }
      : {})
  })
}

if (missing.length) {
  throw new Error(`Missing offline Iconify data: ${[...new Set(missing)].sort().join(', ')}`)
}

fs.mkdirSync(path.dirname(outputFile), { recursive: true })
fs.writeFileSync(outputFile, `${JSON.stringify(collections)}\n`, 'utf8')
const iconCount = collections.reduce(
  (total, collection) => total + Object.keys(collection.icons).length + Object.keys(collection.aliases || {}).length,
  0
)
console.log(`offline-icons: generated ${iconCount} icons across ${collections.length} collections`)
