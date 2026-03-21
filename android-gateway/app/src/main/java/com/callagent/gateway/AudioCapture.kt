// android-gateway/app/src/main/java/com/callagent/gateway/AudioCapture.kt
package com.callagent.gateway

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

object AudioCapture {
    private var isRecording = false
    private var audioRecord: AudioRecord? = null

    // For simplicity, we capture MIC. Real gateway uses VOICE_CALL if system signed
    // Standard phone calls 8kHz or 16kHz
    private const val SAMPLE_RATE = 16000
    private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
    private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT

    @SuppressLint("MissingPermission")
    fun startCapture() {
        if (isRecording) return

        val bufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.VOICE_COMMUNICATION,
            SAMPLE_RATE,
            CHANNEL_CONFIG,
            AUDIO_FORMAT,
            bufferSize
        )

        audioRecord?.startRecording()
        isRecording = true

        CoroutineScope(Dispatchers.IO).launch {
            val buffer = ByteArray(bufferSize)
            while (isRecording) {
                val readData = audioRecord?.read(buffer, 0, bufferSize) ?: 0
                if (readData > 0) {
                    // Send audio buffer to WebSocket server
                    GatewayServer.broadcastAudio(buffer.copyOf(readData))
                }
            }
        }
    }

    fun stopCapture() {
        isRecording = false
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
    }
}
