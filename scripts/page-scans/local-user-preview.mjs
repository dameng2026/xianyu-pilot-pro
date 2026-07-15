import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { Readable } from 'node:stream'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..', '..')
const configPath = path.join(repoRoot, '.deploy.prod.json')
const defaultDistDir = path.join(repoRoot, 'apps', 'user-web', 'dist')

function parseArgs(argv) {
  const options = {
    port: 4174,
    distDir: defaultDistDir,
    backendBase: ''
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--port' && argv[index + 1]) {
      options.port = Number(argv[index + 1]) || options.port
      index += 1
      continue
    }
    if (arg === '--dist-dir' && argv[index + 1]) {
      options.distDir = path.resolve(argv[index + 1])
      index += 1
      continue
    }
    if (arg === '--backend-base' && argv[index + 1]) {
      options.backendBase = String(argv[index + 1]).trim()
      index += 1
    }
  }

  return options
}

function mimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  switch (ext) {
    case '.html':
      return 'text/html; charset=utf-8'
    case '.js':
      return 'application/javascript; charset=utf-8'
    case '.css':
      return 'text/css; charset=utf-8'
    case '.json':
      return 'application/json; charset=utf-8'
    case '.svg':
      return 'image/svg+xml'
    case '.png':
      return 'image/png'
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg'
    case '.gif':
      return 'image/gif'
    case '.webp':
      return 'image/webp'
    case '.ico':
      return 'image/x-icon'
    default:
      return 'application/octet-stream'
  }
}

function isStaticAsset(pathname) {
  return pathname.startsWith('/assets/')
    || pathname.startsWith('/xya/')
    || pathname === '/favicon.ico'
}

function resolveFile(distDir, pathname) {
  const normalized = pathname === '/' ? '/index.html' : pathname
  const candidate = path.resolve(distDir, `.${decodeURIComponent(normalized)}`)
  if (!candidate.startsWith(path.resolve(distDir))) {
    return null
  }
  if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
    return candidate
  }
  return null
}

async function proxyRequest(req, res, backendBase) {
  const upstream = new URL(req.url || '/', backendBase)
  const headers = { ...req.headers }
  delete headers.host
  delete headers.connection
  delete headers['content-length']

  const response = await fetch(upstream, {
    method: req.method,
    headers,
    body: req.method === 'GET' || req.method === 'HEAD' ? undefined : req,
    duplex: req.method === 'GET' || req.method === 'HEAD' ? undefined : 'half'
  })

  const responseHeaders = {}
  response.headers.forEach((value, key) => {
    if (key.toLowerCase() === 'transfer-encoding') return
    responseHeaders[key] = value
  })

  res.writeHead(response.status, responseHeaders)
  if (!response.body) {
    res.end()
    return
  }
  Readable.fromWeb(response.body).pipe(res)
}

async function main() {
  if (!fs.existsSync(configPath)) {
    throw new Error(`deploy config not found: ${configPath}`)
  }

  const options = parseArgs(process.argv.slice(2))
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  const backendBase = new URL((options.backendBase || config.smoke.china_backend_base).replace(/\/$/, '') + '/')
  const distDir = options.distDir

  if (!fs.existsSync(distDir)) {
    throw new Error(`dist dir not found: ${distDir}`)
  }

  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url || '/', 'http://127.0.0.1')
      const pathname = url.pathname

      if (pathname.startsWith('/api/') || pathname.startsWith('/uploads/') || pathname.startsWith('/ai/')) {
        await proxyRequest(req, res, backendBase)
        return
      }

      const directFile = resolveFile(distDir, pathname)
      if (directFile) {
        res.writeHead(200, { 'Content-Type': mimeType(directFile) })
        fs.createReadStream(directFile).pipe(res)
        return
      }

      if (isStaticAsset(pathname)) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
        res.end('Not found')
        return
      }

      const indexFile = path.join(distDir, 'index.html')
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      fs.createReadStream(indexFile).pipe(res)
    } catch (error) {
      res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' })
      res.end(error?.stack || error?.message || String(error))
    }
  })

  server.listen(options.port, '127.0.0.1', () => {
    process.stdout.write(JSON.stringify({
      port: options.port,
      baseUrl: `http://127.0.0.1:${options.port}`,
      distDir,
      backendBase: backendBase.toString()
    }) + '\n')
  })
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error))
  process.exitCode = 1
})
