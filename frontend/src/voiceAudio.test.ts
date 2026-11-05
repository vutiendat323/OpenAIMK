import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { expect, it } from 'vitest'

function processor() {
  let Processor: new () => {
    port: { onmessage: (event: { data: unknown }) => void; postMessage: (event: unknown) => void }
    process: (inputs: unknown[], outputs: Float32Array[][]) => boolean
  }
  const events: { type: string; value?: boolean; epoch: number }[] = []
  runInNewContext(readFileSync(new URL('../public/voice-playback.js', import.meta.url), 'utf8'), {
    AudioWorkletProcessor: class {
      port = { postMessage: (data: (typeof events)[number]) => events.push(data) }
    },
    sampleRate: 48000,
    registerProcessor: (_name: string, type: typeof Processor) => (Processor = type),
  })
  const node = new Processor!()
  const push = (value: number, frames = 960, rate = 48000, epoch = 0) =>
    node.port.onmessage({ data: { epoch, samples: new Float32Array(frames).fill(value), rate } })
  const render = (blocks: number) => {
    const output = new Float32Array(blocks * 128)
    for (let i = 0; i < blocks; i++) {
      const block = new Float32Array(128)
      node.process([], [[block]])
      output.set(block, i * 128)
    }
    return output
  }
  return { node, push, render, events }
}

it('plays on the audio thread with an 80 ms startup buffer and keeps packet order', () => {
  const { push, render, events } = processor()
  push(0.1)
  expect(render(7).every((v) => v === 0)).toBe(true)
  push(0.2)
  push(0.3)
  push(0.4)
  const output = render(30)
  expect(output[500]).toBeCloseTo(0.1)
  expect(output[1500]).toBeCloseTo(0.2)
  expect(output[2500]).toBeCloseTo(0.3)
  expect(output[3500]).toBeCloseTo(0.4)
  expect(events.map((v) => v.value)).toEqual([true, false])
})

it('fades a starved stream to zero without an audible discontinuity', () => {
  const { push, render } = processor()
  push(0.4, 4800)
  const output = render(40)
  let jump = 0
  for (let i = 1; i < output.length; i++) jump = Math.max(jump, Math.abs(output[i] - output[i - 1]))
  expect(jump).toBeLessThan(0.003)
  push(0.2, 480)
  expect(render(100).some((v) => v > 0.1)).toBe(true)
})

it('drops previous guest audio on stop and ignores late old packets', () => {
  const { node, push, render } = processor()
  push(0.8, 4800)
  node.port.onmessage({ data: { type: 'stop', epoch: 1 } })
  push(0.8, 4800)
  expect(render(40).every((v) => v === 0)).toBe(true)
  push(0.2, 4800, 48000, 1)
  expect(Math.max(...render(40))).toBeCloseTo(0.2)
})

it('bounds queued playback instead of growing latency indefinitely', () => {
  const { push, render, events } = processor()
  push(0.8, 7 * 48000)
  expect(events).toContainEqual({ type: 'overflow', epoch: 0 })
  expect(render(40).every((v) => v === 0)).toBe(true)
})

it('does not mistake delayed opening packets for a complete short utterance', () => {
  const { push, render, events } = processor()
  push(0.1)
  push(0.2)
  expect(render(38).every((v) => v === 0)).toBe(true)
  expect(events).toEqual([])
  push(0.3)
  push(0.4)
  const output = render(30)
  expect(output[500]).toBeCloseTo(0.1)
  expect(output[1500]).toBeCloseTo(0.2)
  expect(output[2500]).toBeCloseTo(0.3)
  expect(output[3500]).toBeCloseTo(0.4)
})

it('recovers a short mid-speech packet gap without another full startup wait', () => {
  const { push, render } = processor()
  push(0.2, 4800)
  render(40) // consume the first 100 ms of speech
  render(8) // a short network/UI scheduling gap
  push(0.3, 960)
  // A resumed 20 ms packet must play within 50 ms, not wait another 240 ms.
  expect(render(19).some((sample) => sample > 0.15)).toBe(true)
})

it('keeps the startup buffer for a new utterance after a long silence', () => {
  const { push, render } = processor()
  push(0.2, 4800)
  render(40)
  render(200)
  push(0.3, 960)
  expect(render(19).every((sample) => sample === 0)).toBe(true)
  expect(render(100).some((sample) => sample > 0.15)).toBe(true)
})
