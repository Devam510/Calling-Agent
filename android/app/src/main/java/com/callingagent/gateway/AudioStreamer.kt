package com.callingagent.gateway

import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.util.Log

/**
 * AudioStreamer — Captures speakerphone mic audio and streams raw PCM to the Python backend.
 *
 * Implementation notes (from design lessons):
 *   - We use speakerphone mode so the phone's mic picks up BOTH sides of the call.
 *     Modern Android (10+) blocks direct call audio capture — speakerphone is the
 *     only viable approach without root.
 *   - Format: 16 kHz, 16-bit, mono — matches Whisper's expected input.
 *   - A separate AudioTrack plays TTS chunks (AUDIO_OUT from backend).
 *
 * @param onPcmChunk Callback invoked for every captured PCM chunk (~20 ms).
 */
class AudioStreamer(private val onPcmChunk: (ByteArray) -> Unit) {

    companion object {
        private const val TAG = "AudioStreamer"
        const val SAMPLE_RATE = 16_000
        const val CHANNEL_IN = AudioFormat.CHANNEL_IN_MONO
        const val CHANNEL_OUT = AudioFormat.CHANNEL_OUT_MONO
        const val ENCODING = AudioFormat.ENCODING_PCM_16BIT
        // ~20 ms chunk: 16000 samples/s * 2 bytes * 0.02 s = 640 bytes
        private const val CHUNK_BYTES = 640
    }

    @Volatile private var running = false

    private val recordBufSize = maxOf(
        AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_IN, ENCODING),
        CHUNK_BYTES * 4
    )
    private val trackBufSize = maxOf(
        AudioTrack.getMinBufferSize(SAMPLE_RATE, CHANNEL_OUT, ENCODING),
        CHUNK_BYTES * 4
    )

    private val recorder = AudioRecord(
        MediaRecorder.AudioSource.MIC,
        SAMPLE_RATE, CHANNEL_IN, ENCODING, recordBufSize
    )

    private val player = AudioTrack(
        AudioManager.STREAM_VOICE_CALL,
        SAMPLE_RATE, CHANNEL_OUT, ENCODING, trackBufSize,
        AudioTrack.MODE_STREAM
    )

    private var captureThread: Thread? = null

    /** Start audio capture. Call after speakerphone is confirmed ON. */
    fun start() {
        if (running) return
        running = true
        recorder.startRecording()
        player.play()

        captureThread = Thread({
            Log.i(TAG, "Capture thread started")
            val buf = ByteArray(CHUNK_BYTES)
            while (running) {
                val read = recorder.read(buf, 0, buf.size)
                if (read > 0) {
                    onPcmChunk(buf.copyOf(read))
                }
            }
            Log.i(TAG, "Capture thread stopped")
        }, "audio-capture").apply { start() }
    }

    /** Stop capture and release resources. */
    fun stop() {
        running = false
        captureThread?.interrupt()
        captureThread = null
        runCatching { recorder.stop(); recorder.release() }
        runCatching { player.stop(); player.release() }
    }

    /** Play a PCM chunk received as TTS audio from the Python backend. */
    fun playTtsChunk(pcm: ByteArray) {
        if (!running) return
        player.write(pcm, 0, pcm.size)
    }
}
