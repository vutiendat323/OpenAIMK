/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { expect, it } from 'vitest'

it('discards buffered microphone samples when the guest generation changes', () => {
  const packets: { generation: number; data: ArrayBuffer }[] = []
  let Capture: new () => {
    process(inputs: Float32Array[][]): boolean
    port: { onmessage: (event: { data: { generation: number } }) => void }
  }
  class Processor {
    port = {
      onmessage: () => {},
      postMessage: (packet: { generation: number; data: ArrayBuffer }) => packets.push(packet),
    }
  }
  runInNewContext(readFileSync(new URL('../public/voice-capture.js', import.meta.url), 'utf8'), {
    AudioWorkletProcessor: Processor,
    sampleRate: 16000,
    registerProcessor: (_name: string, constructor: typeof Capture) => {
      Capture = constructor
    },
  })
  const capture = new Capture!()
  capture.port.onmessage({ data: { generation: 1 } })
  capture.process([[new Float32Array(640).fill(0.9)]])
  capture.port.onmessage({ data: { generation: 2 } })
  capture.process([[new Float32Array(1280).fill(0.1)]])
  expect(packets).toHaveLength(1)
  expect(packets[0].generation).toBe(2)
  expect([...new Int16Array(packets[0].data)].every((value) => value === 3277)).toBe(true)
})
