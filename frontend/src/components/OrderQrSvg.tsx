import { useMemo } from 'react'

// GF(256) tables and math for Reed-Solomon QR Error Correction
const EXP = new Uint8Array(512)
const LOG = new Uint8Array(256)
let x = 1
for (let i = 0; i < 255; i++) {
  EXP[i] = x
  EXP[i + 255] = x
  LOG[x] = i
  x = (x << 1) ^ (x & 0x80 ? 0x11d : 0)
}

function gfMul(a: number, b: number): number {
  return a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]
}

function rsGen(n: number): number[] {
  let g = [1]
  for (let i = 0; i < n; i++) {
    const ng = new Array(g.length + 1).fill(0)
    for (let j = 0; j < g.length; j++) {
      ng[j] ^= gfMul(g[j], EXP[i])
      ng[j + 1] ^= g[j]
    }
    g = ng
  }
  return g
}

const RS_GEN_10 = rsGen(10)

function generateQrMatrix(text: string): number[][] {
  // QR Version 2 (25x25), Byte mode, ECC Level L (34 data bytes, 10 EC codewords)
  const encoder = new TextEncoder()
  const dataBytes = encoder.encode(text.slice(0, 32))
  const size = 25
  const matrix: (number | null)[][] = Array.from({ length: size }, () => Array(size).fill(null))
  const reserved: boolean[][] = Array.from({ length: size }, () => Array(size).fill(false))

  // 1. Finder patterns
  const addFinder = (r0: number, c0: number) => {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const isBlack =
          r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4)
        matrix[r0 + r][c0 + c] = isBlack ? 1 : 0
        reserved[r0 + r][c0 + c] = true
      }
    }
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        if (
          r0 + r >= 0 &&
          r0 + r < size &&
          c0 + c >= 0 &&
          c0 + c < size &&
          !reserved[r0 + r][c0 + c]
        ) {
          matrix[r0 + r][c0 + c] = 0
          reserved[r0 + r][c0 + c] = true
        }
      }
    }
  }

  addFinder(0, 0)
  addFinder(0, size - 7)
  addFinder(size - 7, 0)

  // 2. Alignment pattern at (18, 18)
  for (let r = -2; r <= 2; r++) {
    for (let c = -2; c <= 2; c++) {
      const isBlack = Math.abs(r) === 2 || Math.abs(c) === 2 || (r === 0 && c === 0)
      matrix[18 + r][18 + c] = isBlack ? 1 : 0
      reserved[18 + r][18 + c] = true
    }
  }

  // 3. Timing patterns
  for (let i = 8; i < size - 8; i++) {
    if (matrix[6][i] === null) {
      matrix[6][i] = i % 2 === 0 ? 1 : 0
      reserved[6][i] = true
    }
    if (matrix[i][6] === null) {
      matrix[i][6] = i % 2 === 0 ? 1 : 0
      reserved[i][6] = true
    }
  }

  // 4. Dark module
  matrix[17][8] = 1
  reserved[17][8] = true

  // 5. Reserve format info
  const coords1 = [
    [8, 0],
    [8, 1],
    [8, 2],
    [8, 3],
    [8, 4],
    [8, 5],
    [8, 7],
    [8, 8],
    [7, 8],
    [5, 8],
    [4, 8],
    [3, 8],
    [2, 8],
    [1, 8],
    [0, 8],
  ]
  const coords2 = [
    [8, size - 1],
    [8, size - 2],
    [8, size - 3],
    [8, size - 4],
    [8, size - 5],
    [8, size - 6],
    [8, size - 7],
    [8, size - 8],
    [size - 7, 8],
    [size - 6, 8],
    [size - 5, 8],
    [size - 4, 8],
    [size - 3, 8],
    [size - 2, 8],
    [size - 1, 8],
  ]
  for (const [r, c] of coords1) reserved[r][c] = true
  for (const [r, c] of coords2) reserved[r][c] = true

  // 6. Data stream
  let bitStr = '0100' + dataBytes.length.toString(2).padStart(8, '0')
  for (const b of dataBytes) {
    bitStr += b.toString(2).padStart(8, '0')
  }
  const totalDataBits = 34 * 8
  const termLen = Math.min(4, totalDataBits - bitStr.length)
  bitStr += '0'.repeat(termLen)
  if (bitStr.length % 8 !== 0) {
    bitStr += '0'.repeat(8 - (bitStr.length % 8))
  }
  const pad = [0xec, 0x11]
  let pi = 0
  while (bitStr.length < totalDataBits) {
    bitStr += pad[pi % 2].toString(2).padStart(8, '0')
    pi++
  }

  const data: number[] = []
  for (let i = 0; i < bitStr.length; i += 8) {
    data.push(parseInt(bitStr.slice(i, i + 8), 2))
  }

  // 7. Error correction codewords
  const ec = new Array(10).fill(0)
  for (const d of data) {
    const factor = d ^ ec[0]
    ec.shift()
    ec.push(0)
    for (let j = 0; j < 10; j++) {
      ec[j] ^= gfMul(RS_GEN_10[j], factor)
    }
  }

  const allCodewords = [...data, ...ec]
  let allBits = ''
  for (const c of allCodewords) {
    allBits += c.toString(2).padStart(8, '0')
  }
  allBits += '0000000'

  // 8. Place data bits in zig-zag
  let bitIdx = 0
  let up = true
  let col = size - 1
  while (col > 0) {
    if (col === 6) col -= 1
    const rowRange = up
      ? Array.from({ length: size }, (_, i) => size - 1 - i)
      : Array.from({ length: size }, (_, i) => i)

    for (const r of rowRange) {
      for (const c of [col, col - 1]) {
        if (!reserved[r][c]) {
          const b = bitIdx < allBits.length ? parseInt(allBits[bitIdx], 10) : 0
          bitIdx++
          const mask = (r + c) % 2 === 0 ? 1 : 0
          matrix[r][c] = b ^ mask
        }
      }
    }
    up = !up
    col -= 2
  }

  // 9. Format info (Level L, Mask 0 -> '111011111000100')
  const formatBits = '111011111000100'
  for (let i = 0; i < 15; i++) {
    const bit = parseInt(formatBits[i], 10)
    const [r1, c1] = coords1[i]
    matrix[r1][c1] = bit
    const [r2, c2] = coords2[i]
    matrix[r2][c2] = bit
  }

  return matrix.map((row) => row.map((cell) => cell ?? 0))
}

export function OrderQrSvg({
  text,
  size = 96,
  className = '',
}: {
  text: string
  size?: number
  className?: string
}) {
  const matrix = useMemo(() => generateQrMatrix(text), [text])
  const n = matrix.length
  let path = ''
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      if (matrix[r][c] === 1) {
        path += `M${c},${r}h1v1h-1z `
      }
    }
  }

  return (
    <svg
      viewBox={`-1 -1 ${n + 2} ${n + 2}`}
      width={size}
      height={size}
      className={`kfc-order-qr-svg ${className}`.trim()}
      role="img"
      aria-label="Order QR"
    >
      <rect x="-1" y="-1" width={n + 2} height={n + 2} fill="#ffffff" />
      <path d={path} fill="#111827" />
    </svg>
  )
}
