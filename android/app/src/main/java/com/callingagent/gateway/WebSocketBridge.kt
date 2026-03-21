package com.callingagent.gateway

import android.util.Base64
import android.util.Log
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * WebSocketBridge — Maintains the OkHttp WebSocket connection to the Python backend.
 *
 * Message protocol (JSON over WebSocket):
 *   Backend → Android:
 *     { "type": "START_CALL",      "phone": "+91XXXXXXXXXX" }
 *     { "type": "END_CALL" }
 *     { "type": "CALL_CONNECTED" }
 *     { "type": "AUDIO_OUT",       "data": "<base64 PCM>" }
 *
 *   Android → Backend:
 *     { "type": "AUDIO_IN",        "data": "<base64 PCM>" }
 *     { "type": "RINGING" }
 *     { "type": "CONNECTED" }
 *     { "type": "DISCONNECTED" }
 *     { "type": "ERROR",           "message": "..." }
 */
class WebSocketBridge(
    private val serverUrl: String,
    private val onCommand: (GatewayCommand) -> Unit,
    private val onDisconnect: () -> Unit,
) {
    companion object {
        private const val TAG = "WebSocketBridge"
    }

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .connectTimeout(10, TimeUnit.SECONDS)
        .build()

    @Volatile private var ws: WebSocket? = null

    fun connect() {
        val request = Request.Builder().url(serverUrl).build()
        ws = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected to $serverUrl")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                parseAndDispatch(text)
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Binary frames treated as raw PCM audio-out
                onCommand(GatewayCommand.AudioOut(bytes.toByteArray()))
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket error: ${t.message}")
                onDisconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WebSocket closed: $code $reason")
                onDisconnect()
            }
        })
    }

    fun disconnect() {
        ws?.close(1000, "Service stopping")
        ws = null
    }

    /** Send raw PCM captured from mic to the backend. */
    fun sendAudioIn(pcm: ByteArray) {
        val payload = JSONObject().apply {
            put("data", Base64.encodeToString(pcm, Base64.NO_WRAP))
        }
        val json = JSONObject().apply {
            put("type", "AUDIO_IN")
            put("payload", payload)
        }
        ws?.send(json.toString())
    }

    /** Send a state-change event to the backend. */
    fun sendEvent(event: GatewayEvent) {
        val payload = JSONObject()
        val type = when (event) {
            is GatewayEvent.Ringing       -> "RINGING"
            is GatewayEvent.Connected     -> "CONNECTED"
            is GatewayEvent.Disconnected  -> "DISCONNECTED"
            is GatewayEvent.CallStateChanged -> {
                payload.put("state", event.state)
                "CALL_STATE"
            }
            is GatewayEvent.Error         -> {
                payload.put("message", event.message)
                "ERROR"
            }
        }
        val json = JSONObject().apply {
            put("type", type)
            put("payload", payload)
        }
        ws?.send(json.toString())
    }

    // ─── Internal ─────────────────────────────────────────────────────────────

    private fun parseAndDispatch(text: String) {
        runCatching {
            val json = JSONObject(text)
            val type = json.getString("type")
            val payload = json.optJSONObject("payload") ?: JSONObject()
            
            when (type) {
                "START_CALL"     -> onCommand(GatewayCommand.StartCall(payload.getString("phone")))
                "END_CALL"       -> onCommand(GatewayCommand.EndCall)
                "CALL_CONNECTED" -> onCommand(GatewayCommand.CallConnected)
                "AUDIO_OUT"      -> {
                    val raw = Base64.decode(payload.getString("data"), Base64.NO_WRAP)
                    onCommand(GatewayCommand.AudioOut(raw))
                }
                else -> Log.w(TAG, "Unknown command type: $type")
            }
        }.onFailure { Log.e(TAG, "Parse error: $text", it) }
    }
}
