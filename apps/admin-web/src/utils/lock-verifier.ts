const VERSION = 'v1'
const ITERATIONS = 210_000
const KEY_LENGTH = 32

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value)
  return Uint8Array.from(binary, character => character.charCodeAt(0))
}

async function derive(password: string, salt: Uint8Array, iterations: number): Promise<Uint8Array> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveBits']
  )
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: salt as BufferSource, iterations },
    keyMaterial,
    KEY_LENGTH * 8
  )
  return new Uint8Array(bits)
}

export async function createLockVerifier(password: string): Promise<string> {
  if (!password) throw new Error('锁屏口令不能为空')
  const salt = crypto.getRandomValues(new Uint8Array(16))
  const hash = await derive(password, salt, ITERATIONS)
  return [VERSION, ITERATIONS, bytesToBase64(salt), bytesToBase64(hash)].join('$')
}

export async function verifyLockPassword(password: string, verifier: string): Promise<boolean> {
  const [version, rawIterations, rawSalt, rawExpected, ...extra] = verifier.split('$')
  const iterations = Number(rawIterations)
  if (
    version !== VERSION
    || extra.length > 0
    || !Number.isSafeInteger(iterations)
    || iterations < 100_000
    || iterations > 1_000_000
  ) {
    return false
  }

  try {
    const salt = base64ToBytes(rawSalt)
    const expected = base64ToBytes(rawExpected)
    if (salt.length !== 16 || expected.length !== KEY_LENGTH) return false
    const actual = await derive(password, salt, iterations)
    let difference = 0
    for (let index = 0; index < expected.length; index += 1) {
      difference |= expected[index] ^ actual[index]
    }
    return difference === 0
  } catch {
    return false
  }
}
