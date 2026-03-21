package com.callingagent.gateway

import android.content.Context
import android.media.*
import android.util.Log
import kotlinx.coroutines.channels.Channel
import java.nio.ByteBuffer

private const val TAG = "AudioCapture"

// PCM format: 16kHz, 16-bit, mono — matches Python backend expectations
private const val SAMPLE_RATE = 16_000
private const val CHANNEL_IN  = AudioFormat.CHANNEL_IN_MONO
private const val CHANNEL_OUT = AudioFormat.CHANNEL_OUT_MONO
private const val ENCODING    = AudioFormat.ENCODING_PCM_16BIT

/**
 * Captures mic audio (speakerphone strategy — L001).
 *
 * On Android 10+ direct call audio capture is blocked.
 * We put the call on speakerphone so both sides are captured via mic.
 *
 * Also handles playback of agent TTS audio through the earpiece/speaker.
 */
class AudioCapture(private val context: Context) {

    val audioChannel = Channel<ByteArray>(capacity = Channel.UNLIMITED)

    private var recorder: AudioRecord? = null
    private var player: AudioTrack? = null
    private var captureThread: Thread? = null
    private var isCapturing = false

    fun start() {
        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_IN, ENCODING)

        recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,   // L001: speakerphone + mic
            SAMPLE_RATE,
            CHANNEL_IN,
            ENCODING,
            bufferSize * 4,
        )

        player = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(SAMPLE_RATE)
                    .setChannelMask(CHANNEL_OUT)
                    .setEncoding(ENCODING)
                    .build()
            )
            .setBufferSizeInBytes(bufferSize * 4)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        player!!.play()
        recorder!!.startRecording()
        isCapturing = true

        captureThread = Thread {
            val buffer = ByteArray(bufferSize)
            while (isCapturing) {
                val read = recorder!!.read(buffer, 0, buffer.size)
                if (read > 0) {
                    audioChannel.trySend(buffer.copyOf(read))
                }
            }
        }.also { it.isDaemon = true; it.start() }

        Log.i(TAG, "AudioCapture started (speakerphone mode)")
    }

    /**
     * Play a PCM chunk received from the Python backend (agent TTS output).
     * Called from GatewayService when AUDIO_OUT message arrives.
     */
    fun playToSpeaker(pcm: ByteArray) {
        player?.write(pcm, 0, pcm.size)
    }

    fun stop() {
        isCapturing = false
        recorder?.stop()
        recorder?.release()
        recorder = null
        player?.stop()
        player?.release()
        player = null
        audioChannel.close()
        Log.i(TAG, "AudioCapture stopped")
    }
}
