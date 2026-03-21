package com.callingagent.gateway

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.telecom.TelecomManager
import android.util.Log
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
        startForeground(NOTIFICATION_ID, buildNotification("Gateway idle"))
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
            }
            is GatewayCommand.EndCall -> {
                hangUp()
                audioStreamer?.stop()
                audioStreamer = null
                updateNotification("Gateway idle")
            }
            is GatewayCommand.CallConnected -> {
                // Backend confirmed call is connected — start audio capture
                updateNotification("Call active ▶ streaming")
                audioStreamer = AudioStreamer { pcmChunk ->
                    webSocketBridge.sendAudioIn(pcmChunk)
                }
                audioStreamer?.start()
            }
            is GatewayCommand.AudioOut -> {
                // PCM from TTS — play via speakerphone (raw track)
                audioStreamer?.playTtsChunk(cmd.pcmData)
            }
        }
    }

    // ─── Telephony helpers ────────────────────────────────────────────────────

    private fun dialNumber(number: String) {
        try {
            val telecom = getSystemService(TELECOM_SERVICE) as TelecomManager
            // Requires CALL_PHONE permission granted at runtime
            val uri = android.net.Uri.parse("tel:$number")
            val extras = android.os.Bundle()
            telecom.placeCall(uri, extras)
            Log.i(TAG, "placeCall($number) invoked")
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
