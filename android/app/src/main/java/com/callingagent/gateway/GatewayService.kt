package com.callingagent.gateway

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.telecom.TelecomManager
import android.util.Log
import android.Manifest
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*

/**
 * GatewayService — Foreground service that owns the WebSocket bridge and audio streamer.
 *
 * Lifecycle:
 *   1. MainActivity starts this service on "Connect" button press.
 *   2. Service opens a WebSocket to the Python backend (ws://PC_IP:8765).
 *   3. On START_CALL command → dials the phone number via TelecomManager.
 *   4. On call connected → AudioStreamer starts capturing speakerphone mic.
 *   5. On END_CALL command → hangs up.
 *   6. Service stops when MainActivity calls stopService() or on disconnect.
 */
class GatewayService : Service() {

    companion object {
        private const val TAG = "GatewayService"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "gateway_channel"
    }

    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private lateinit var webSocketBridge: WebSocketBridge
    private var audioStreamer: AudioStreamer? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        if (android.os.Build.VERSION.SDK_INT >= 34) {
            startForeground(
                NOTIFICATION_ID, 
                buildNotification("Gateway idle"), 
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            )
        } else {
            startForeground(NOTIFICATION_ID, buildNotification("Gateway idle"))
        }
        Log.i(TAG, "GatewayService created")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val serverUrl = intent?.getStringExtra("server_url") ?: "ws://192.168.1.100:8765"
        Log.i(TAG, "Connecting to backend at $serverUrl")

        webSocketBridge = WebSocketBridge(
            serverUrl = serverUrl,
            onCommand = ::handleCommand,
            onDisconnect = {
                Log.w(TAG, "WebSocket disconnected — stopping service")
                stopSelf()
            }
        )
        serviceScope.launch { webSocketBridge.connect() }

        return START_NOT_STICKY
    }

    /**
     * Handle a decoded command from the Python backend.
     * All commands arrive on the WebSocket receive thread; dispatch to main where needed.
     */
    private fun handleCommand(cmd: GatewayCommand) {
        Log.d(TAG, "Command: $cmd")
        when (cmd) {
            is GatewayCommand.StartCall -> {
                updateNotification("Dialing ${cmd.phoneNumber}…")
                dialNumber(cmd.phoneNumber)
                // Since we rely on ACTION_CALL, we can't detect when the call answers.
                // Start streaming immediately.
                startAudioStreaming()
            }
            is GatewayCommand.EndCall -> {
                hangUp()
                stopAudioStreaming()
                updateNotification("Gateway idle")
            }
            is GatewayCommand.CallConnected -> {
                // Not used with ACTION_CALL
            }
            is GatewayCommand.AudioOut -> {
                // PCM from TTS — play via speakerphone (raw track)
                audioStreamer?.playTtsChunk(cmd.pcmData)
            }
        }
    }

    private fun startAudioStreaming() {
        if (audioStreamer != null) return
        audioStreamer = AudioStreamer { pcmChunk ->
            webSocketBridge.sendAudioIn(pcmChunk)
        }
        audioStreamer?.start()
    }

    private fun stopAudioStreaming() {
        audioStreamer?.stop()
        audioStreamer = null
    }

    /** Send call state updates back to the Python backend */
    fun sendCallState(state: String) {
        serviceScope.launch {
            try {
                webSocketBridge.sendEvent(GatewayEvent.CallStateChanged(state))
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send call state", e)
            }
        }
    }

    // ─── Telephony helpers ────────────────────────────────────────────────────

    private fun dialNumber(number: String) {
        try {
            // Revert to ACTION_CALL because placeCall silently drops the request on some OSes
            val uri = android.net.Uri.parse("tel:$number")
            val intent = Intent(Intent.ACTION_CALL, uri)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            startActivity(intent)
            Log.i(TAG, "ACTION_CALL($number) invoked")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to dial: ${e.message}")
            webSocketBridge.sendEvent(GatewayEvent.Error("dial_failed: ${e.message}"))
        }
    }

    private fun hangUp() {
        try {
            val telecom = getSystemService(TELECOM_SERVICE) as TelecomManager
            @Suppress("DEPRECATION")
            telecom.endCall()
        } catch (e: Exception) {
            Log.w(TAG, "hangUp failed: ${e.message}")
        }
    }

    // ─── Notification helpers ─────────────────────────────────────────────────

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID, "Calling Agent Gateway",
            NotificationManager.IMPORTANCE_LOW
        ).apply { description = "Hindi calling agent gateway service" }
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
            .createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Calling Agent Gateway")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_call)
            .setOngoing(true)
            .build()

    private fun updateNotification(text: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(text))
    }

    override fun onDestroy() {
        serviceScope.cancel()
        audioStreamer?.stop()
        webSocketBridge.disconnect()
        Log.i(TAG, "GatewayService destroyed")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
