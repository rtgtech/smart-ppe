class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.pending = []
    this.sourceSamplesPerFrame = Math.max(1, Math.round(sampleRate * 0.02))
  }

  process(inputs) {
    const input = inputs[0]?.[0]
    if (!input) return true

    for (let index = 0; index < input.length; index += 1) this.pending.push(input[index])

    while (this.pending.length >= this.sourceSamplesPerFrame) {
      const frame = this.pending.splice(0, this.sourceSamplesPerFrame)
      const targetLength = 320
      const pcm = new Int16Array(targetLength)
      const ratio = frame.length / targetLength

      for (let outputIndex = 0; outputIndex < targetLength; outputIndex += 1) {
        const start = Math.floor(outputIndex * ratio)
        const end = Math.max(start + 1, Math.floor((outputIndex + 1) * ratio))
        let total = 0
        for (let sourceIndex = start; sourceIndex < end && sourceIndex < frame.length; sourceIndex += 1) {
          total += frame[sourceIndex]
        }
        const sample = Math.max(-1, Math.min(1, total / (end - start)))
        pcm[outputIndex] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
      }

      this.port.postMessage(pcm.buffer, [pcm.buffer])
    }

    return true
  }
}

registerProcessor('pcm-capture', PcmCaptureProcessor)
